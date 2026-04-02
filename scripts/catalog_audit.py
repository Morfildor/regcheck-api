from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from collections.abc import Iterable, Iterator, Mapping
from contextlib import contextmanager
import os
from pathlib import Path
import sys
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from app.services.knowledge_base.loader import _load_yaml_raw
from app.services.knowledge_base.paths import (
    KnowledgeBaseError,
    _resolved_catalog_sources,
    clear_resolved_data_paths_cache,
)
from app.services.knowledge_base.validator import (
    _string_list,
    _validate_classifier_signal_catalog,
    _validate_genres,
    _validate_legislations,
    _validate_products,
    _validate_standards,
    _validate_traits,
)


TRAIT_FIELDS = (
    "traits",
    "default_traits",
    "implied_traits",
    "core_traits",
    "family_traits",
    "subtype_traits",
    "all_of_traits",
    "any_of_traits",
    "none_of_traits",
    "applies_if_all",
    "applies_if_any",
    "exclude_if",
)

ALIAS_FIELDS = ("aliases", "strong_aliases", "weak_aliases", "marketplace_aliases")
GENRE_ALIAS_WEIGHT = {"strong_aliases": 3, "aliases": 2, "weak_aliases": 1, "marketplace_aliases": 1}
GENERIC_ALIAS_TOKENS = {
    "adapter",
    "alarm",
    "box",
    "camera",
    "controller",
    "gateway",
    "hub",
    "lamp",
    "light",
    "mirror",
    "monitor",
    "sensor",
    "switch",
    "tool",
}


@contextmanager
def _temporary_data_dir(data_dir: str | None) -> Iterator[None]:
    previous = os.environ.get("REGCHECK_DATA_DIR")
    try:
        if data_dir:
            os.environ["REGCHECK_DATA_DIR"] = str(Path(data_dir).resolve())
        elif "REGCHECK_DATA_DIR" in os.environ:
            del os.environ["REGCHECK_DATA_DIR"]
        clear_resolved_data_paths_cache()
        yield
    finally:
        if previous is None:
            os.environ.pop("REGCHECK_DATA_DIR", None)
        else:
            os.environ["REGCHECK_DATA_DIR"] = previous
        clear_resolved_data_paths_cache()


def _load_validated_catalogs(*, data_dir: str | None = None) -> dict[str, Any]:
    with _temporary_data_dir(data_dir):
        traits = _validate_traits(_load_yaml_raw("traits.yaml"))
        trait_ids = {row["id"] for row in traits}

        genres = _validate_genres(_load_yaml_raw("product_genres.yaml"), trait_ids)
        genre_ids = {row["id"] for row in genres}

        products = _validate_products(_load_yaml_raw("products.yaml"), trait_ids, genre_ids)
        product_ids = {row["id"] for row in products}

        legislations = _validate_legislations(_load_yaml_raw("legislation_catalog.yaml"), product_ids, trait_ids, genre_ids)
        legislation_keys = {row["directive_key"] for row in legislations}

        standards = _validate_standards(_load_yaml_raw("standards.yaml"), product_ids, trait_ids, legislation_keys, genre_ids)

        classifier_signals = _load_yaml_raw("classifier_signals.yaml", required=False)
        _validate_classifier_signal_catalog(classifier_signals, trait_ids)

        resolved_sources = _resolved_catalog_sources()
        sources: dict[str, list[str]] = {}
        for name in ("traits.yaml", "product_genres.yaml", "products.yaml", "standards.yaml", "classifier_signals.yaml"):
            bundle = resolved_sources.get(name)
            sources[name] = [path.as_posix() for path in bundle.paths] if bundle is not None else []

    return {
        "traits": traits,
        "genres": genres,
        "products": products,
        "legislations": legislations,
        "standards": standards,
        "classifier_signals": classifier_signals,
        "sources": sources,
    }


def _normalize_token(value: str) -> str:
    return " ".join(str(value).strip().lower().split())


def _collect_signal_traits(signal_data: Mapping[str, Any]) -> tuple[set[str], set[str]]:
    referenced: set[str] = set()
    suppressed: set[str] = set()

    for section_name in ("trait_detection", "negations"):
        section = signal_data.get(section_name, {})
        if not isinstance(section, Mapping):
            continue
        for group in section.values():
            if not isinstance(group, Mapping):
                continue
            referenced.update(str(key) for key in group.keys())

    suppression = signal_data.get("suppression_mappings", {})
    if isinstance(suppression, Mapping):
        for group in suppression.values():
            if not isinstance(group, Mapping):
                continue
            referenced.update(str(key) for key in group.keys())
            for traits in group.values():
                if isinstance(traits, list):
                    suppressed.update(str(item) for item in traits if isinstance(item, str))

    return referenced, suppressed


def _collect_referenced_traits(catalogs: Mapping[str, Any]) -> set[str]:
    referenced: set[str] = set()

    for genre in catalogs["genres"]:
        for field in ("traits", "default_traits"):
            referenced.update(_string_list(genre.get(field)))

    for product in catalogs["products"]:
        for field in ("implied_traits", "core_traits", "default_traits", "family_traits", "subtype_traits"):
            referenced.update(_string_list(product.get(field)))

    for row in catalogs["legislations"]:
        for field in ("all_of_traits", "any_of_traits", "none_of_traits"):
            referenced.update(_string_list(row.get(field)))

    for row in catalogs["standards"]:
        for field in ("applies_if_all", "applies_if_any", "exclude_if"):
            referenced.update(_string_list(row.get(field)))

    signal_traits, suppressed_traits = _collect_signal_traits(catalogs["classifier_signals"])
    referenced.update(signal_traits)
    referenced.update(suppressed_traits)
    return referenced


def _products_with_thin_aliases(products: list[Mapping[str, Any]], minimum_aliases: int) -> list[str]:
    thin: list[str] = []
    for product in products:
        aliases: set[str] = set()
        for field in ALIAS_FIELDS:
            aliases.update(_normalize_token(item) for item in _string_list(product.get(field)))
        if len(aliases) < minimum_aliases:
            thin.append(f"{product['id']} ({len(aliases)} aliases)")
    return thin


def _alias_collision_rows(products: list[Mapping[str, Any]], minimum_products: int) -> list[str]:
    owners_by_alias: dict[str, set[str]] = defaultdict(set)
    strongest_field_by_alias: dict[str, int] = defaultdict(int)

    for product in products:
        pid = str(product["id"])
        for field in ALIAS_FIELDS:
            weight = GENRE_ALIAS_WEIGHT.get(field, 1)
            for alias in _string_list(product.get(field)):
                normalized = _normalize_token(alias)
                if not normalized:
                    continue
                owners_by_alias[normalized].add(pid)
                strongest_field_by_alias[normalized] = max(strongest_field_by_alias[normalized], weight)

    findings: list[tuple[int, str]] = []
    for alias, owners in owners_by_alias.items():
        if len(owners) < minimum_products:
            continue
        tokens = alias.split()
        severity = "LOW"
        score = 1
        if len(tokens) == 1 or alias in GENERIC_ALIAS_TOKENS:
            severity = "HIGH"
            score = 3
        elif len(owners) >= 3 or strongest_field_by_alias[alias] >= 2:
            severity = "MEDIUM"
            score = 2
        findings.append((score, f"{severity}: {alias!r}: {', '.join(sorted(owners))}"))

    return [row for _score, row in sorted(findings, key=lambda item: (-item[0], item[1]))]


def _products_missing_structure(products: list[Mapping[str, Any]]) -> list[str]:
    findings: list[str] = []
    for product in products:
        pid = str(product["id"])
        issues: list[str] = []
        if not _string_list(product.get("genres")):
            issues.append("no genres")
        if not str(product.get("product_family") or "").strip():
            issues.append("no product_family")
        if not str(product.get("product_subfamily") or "").strip():
            issues.append("no product_subfamily")
        trait_coverage = set()
        for field in ("implied_traits", "core_traits", "default_traits", "family_traits", "subtype_traits"):
            trait_coverage.update(_string_list(product.get(field)))
        if not trait_coverage:
            issues.append("no trait structure")
        if not str(product.get("route_family") or "").strip() and not str(product.get("primary_standard_code") or "").strip():
            issues.append("no route anchor")
        if issues:
            findings.append(f"{pid}: {', '.join(issues)}")
    return findings


def _products_lacking_decisive_clues(products: list[Mapping[str, Any]]) -> list[str]:
    findings: list[str] = []
    for product in products:
        alias_count = sum(len(_string_list(product.get(field))) for field in ALIAS_FIELDS)
        decisive = (
            alias_count
            + len(_string_list(product.get("preferred_clues")))
            + len(_string_list(product.get("required_clues")))
            + len(_string_list(product.get("family_keywords")))
        )
        if decisive >= 4:
            continue
        findings.append(f"{product['id']}: decisive_signals={decisive}")
    return findings


def _products_likely_to_overmatch(products: list[Mapping[str, Any]]) -> list[str]:
    findings: list[str] = []
    for product in products:
        aliases = {_normalize_token(item) for field in ALIAS_FIELDS for item in _string_list(product.get(field))}
        generic_aliases = sorted(alias for alias in aliases if len(alias.split()) == 1 and alias in GENERIC_ALIAS_TOKENS)
        if not generic_aliases:
            continue
        exclude_count = len(_string_list(product.get("exclude_clues"))) + len(_string_list(product.get("not_when_text_contains")))
        if exclude_count >= 2:
            continue
        findings.append(f"{product['id']}: generic_aliases={', '.join(generic_aliases)}; exclude_guards={exclude_count}")
    return findings


def _boundary_product_report(products: list[Mapping[str, Any]]) -> list[str]:
    findings: list[str] = []
    for product in products:
        tags = _string_list(product.get("boundary_tags"))
        max_stage = str(product.get("max_match_stage") or "").strip()
        cap = str(product.get("route_confidence_cap") or "").strip()
        if not tags and not max_stage and not cap:
            continue
        parts: list[str] = []
        if tags:
            parts.append("boundary_tags=" + ",".join(tags))
        if max_stage:
            parts.append("max_match_stage=" + max_stage)
        if cap:
            parts.append("route_confidence_cap=" + cap)
        findings.append(f"{product['id']}: " + "; ".join(parts))
    return findings


def _family_summary(products: list[Mapping[str, Any]]) -> list[str]:
    family_counts = Counter(str(product.get("product_family") or "unknown") for product in products)
    return [f"{family}: {count}" for family, count in family_counts.most_common()]


def _genre_summary(products: list[Mapping[str, Any]]) -> list[str]:
    genre_counts: Counter[str] = Counter()
    for product in products:
        genre_counts.update(_string_list(product.get("genres")))
    return [f"{genre}: {count}" for genre, count in genre_counts.most_common()]


def _route_family_summary(products: list[Mapping[str, Any]]) -> list[str]:
    counter = Counter(str(product.get("route_family") or "unanchored") for product in products)
    return [f"{route_family}: {count}" for route_family, count in counter.most_common()]


def _trait_density_summary(products: list[Mapping[str, Any]]) -> list[str]:
    density: list[tuple[int, str]] = []
    for product in products:
        trait_count = 0
        for field in ("implied_traits", "core_traits", "default_traits", "family_traits", "subtype_traits"):
            trait_count += len(_string_list(product.get(field)))
        density.append((trait_count, str(product["id"])))
    density.sort(reverse=True)
    return [f"{pid}: {count} trait entries" for count, pid in density[:15]]


def _traits_per_product_distribution(products: list[Mapping[str, Any]]) -> list[str]:
    buckets: Counter[str] = Counter()
    for product in products:
        trait_count = len(
            {
                trait
                for field in ("implied_traits", "core_traits", "default_traits", "family_traits", "subtype_traits")
                for trait in _string_list(product.get(field))
            }
        )
        if trait_count <= 4:
            buckets["0-4"] += 1
        elif trait_count <= 8:
            buckets["5-8"] += 1
        elif trait_count <= 12:
            buckets["9-12"] += 1
        else:
            buckets["13+"] += 1
    return [f"{bucket}: {buckets[bucket]}" for bucket in ("0-4", "5-8", "9-12", "13+")]


def _source_summary(catalogs: Mapping[str, Any]) -> list[str]:
    rows: list[str] = []
    for logical_name, paths in catalogs["sources"].items():
        label = logical_name.replace(".yaml", "")
        rows.append(f"{label}: {len(paths)} file(s)")
    return rows


def _diff_summary(current: Mapping[str, Any], compare: Mapping[str, Any]) -> list[str]:
    sections = (
        ("products", "id"),
        ("traits", "id"),
        ("standards", "code"),
        ("genres", "id"),
    )
    rows: list[str] = []
    for section, key in sections:
        current_ids = {str(item[key]) for item in current[section]}
        compare_ids = {str(item[key]) for item in compare[section]}
        added = sorted(current_ids - compare_ids)
        removed = sorted(compare_ids - current_ids)
        rows.append(f"{section}: +{len(added)} / -{len(removed)}")
        if added:
            rows.append(f"{section} added: {', '.join(added[:10])}")
        if removed:
            rows.append(f"{section} removed: {', '.join(removed[:10])}")
    return rows


def _print_section(title: str, items: Iterable[str]) -> None:
    rows = list(items)
    print(f"\n{title}")
    if not rows:
        print("  none")
        return
    for row in rows:
        print(f"  - {row}")


def run(
    command: str,
    *,
    minimum_aliases: int,
    broad_alias_threshold: int,
    compare_dir: str | None = None,
    data_dir: str | None = None,
) -> int:
    try:
        catalogs = _load_validated_catalogs(data_dir=data_dir)
        comparison = _load_validated_catalogs(data_dir=compare_dir) if compare_dir else None
    except KnowledgeBaseError as exc:
        print(f"Validation failed: {exc}")
        return 1

    if command in {"validate", "all"}:
        counts = {key: len(value) for key, value in catalogs.items() if isinstance(value, list)}
        print("Catalog validation passed.")
        print("Counts:", ", ".join(f"{key}={value}" for key, value in sorted(counts.items())))
        _print_section("Catalog Sources", _source_summary(catalogs))

    if command in {"summary", "all"}:
        _print_section("Product Families", _family_summary(catalogs["products"])[:20])
        _print_section("Product Genres", _genre_summary(catalogs["products"])[:20])
        _print_section("Route Families", _route_family_summary(catalogs["products"]))
        _print_section("Trait Density", _trait_density_summary(catalogs["products"]))
        _print_section("Traits Per Product", _traits_per_product_distribution(catalogs["products"]))

    if command in {"report", "all"}:
        trait_ids = {row["id"] for row in catalogs["traits"]}
        referenced_traits = _collect_referenced_traits(catalogs)
        unused_traits = sorted(trait_ids - referenced_traits)

        _print_section("Unused Traits", unused_traits)
        _print_section(
            f"Products With Fewer Than {minimum_aliases} Aliases",
            _products_with_thin_aliases(catalogs["products"], minimum_aliases),
        )
        _print_section(
            f"Alias Collisions Shared By {broad_alias_threshold}+ Products",
            _alias_collision_rows(catalogs["products"], broad_alias_threshold),
        )
        _print_section("Products Missing Structure", _products_missing_structure(catalogs["products"]))
        _print_section("Products Lacking Decisive Clues", _products_lacking_decisive_clues(catalogs["products"]))
        _print_section("Products Likely To Overmatch", _products_likely_to_overmatch(catalogs["products"]))
        _print_section("Boundary Product Report", _boundary_product_report(catalogs["products"]))

    if comparison is not None and command in {"summary", "report", "all"}:
        _print_section("Catalog Diff Summary", _diff_summary(catalogs, comparison))

    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate and audit RuleGrid catalog integrity.")
    parser.add_argument("command", nargs="?", choices=("validate", "summary", "report", "all"), default="all")
    parser.add_argument("--minimum-aliases", type=int, default=4)
    parser.add_argument("--broad-alias-threshold", type=int, default=3)
    parser.add_argument("--compare-dir", type=str, default=None, help="Optional alternate data directory for an added/removed catalog diff summary.")
    parser.add_argument("--data-dir", type=str, default=None, help="Explicit data directory to validate instead of the default repo catalog.")
    args = parser.parse_args()
    return run(
        args.command,
        minimum_aliases=args.minimum_aliases,
        broad_alias_threshold=args.broad_alias_threshold,
        compare_dir=args.compare_dir,
        data_dir=args.data_dir,
    )


if __name__ == "__main__":
    raise SystemExit(main())
