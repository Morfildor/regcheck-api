from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from collections.abc import Iterable, Iterator, Mapping
from contextlib import contextmanager
import json
import os
from pathlib import Path
import sys
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from app.services.knowledge_base.enricher import _enrich_products
from app.services.knowledge_base.loader import _as_genre_rows, _load_yaml_fragment, _load_yaml_raw
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
from app.services.rules.route_anchors import family_from_standard_code, route_anchor_definition


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


def _product_source_map() -> dict[str, str]:
    bundle = _resolved_catalog_sources().get("products.yaml")
    if bundle is None:
        return {}

    mapping: dict[str, str] = {}
    for path in bundle.paths:
        payload = _load_yaml_fragment(path)
        for row in payload.get("products", []):
            if not isinstance(row, dict):
                continue
            pid = str(row.get("id") or "").strip()
            if not pid:
                continue
            mapping[pid] = path.relative_to(REPO_ROOT).as_posix()
    return mapping


def _trait_source_map() -> dict[str, str]:
    bundle = _resolved_catalog_sources().get("traits.yaml")
    if bundle is None:
        return {}

    mapping: dict[str, str] = {}
    for path in bundle.paths:
        payload = _load_yaml_fragment(path)
        for row in payload.get("traits", []):
            if not isinstance(row, dict):
                continue
            trait_id = str(row.get("id") or "").strip()
            if not trait_id:
                continue
            mapping[trait_id] = path.relative_to(REPO_ROOT).as_posix()
    return mapping


def _load_validated_catalogs(*, data_dir: str | None = None) -> dict[str, Any]:
    with _temporary_data_dir(data_dir):
        traits_raw = _validate_traits(_load_yaml_raw("traits.yaml"))
        trait_ids = {row["id"] for row in traits_raw}

        genres_raw = _validate_genres(_load_yaml_raw("product_genres.yaml"), trait_ids)
        genre_ids = {row["id"] for row in genres_raw}

        products_raw = _validate_products(_load_yaml_raw("products.yaml"), trait_ids, genre_ids)
        product_ids = {row["id"] for row in products_raw}

        legislations = _validate_legislations(_load_yaml_raw("legislation_catalog.yaml"), product_ids, trait_ids, genre_ids)
        legislation_keys = {row["directive_key"] for row in legislations}

        standards = _validate_standards(_load_yaml_raw("standards.yaml"), product_ids, trait_ids, legislation_keys, genre_ids)

        classifier_signals = _load_yaml_raw("classifier_signals.yaml", required=False)
        _validate_classifier_signal_catalog(classifier_signals, trait_ids)

        products = _enrich_products(products_raw, _as_genre_rows(genres_raw))
        product_sources = _product_source_map()
        trait_sources = _trait_source_map()

        resolved_sources = _resolved_catalog_sources()
        sources: dict[str, list[str]] = {}
        for name in ("traits.yaml", "product_genres.yaml", "products.yaml", "standards.yaml", "classifier_signals.yaml"):
            bundle = resolved_sources.get(name)
            sources[name] = [path.as_posix() for path in bundle.paths] if bundle is not None else []

    return {
        "traits": traits_raw,
        "genres": genres_raw,
        "products": products,
        "products_raw": products_raw,
        "legislations": legislations,
        "standards": standards,
        "classifier_signals": classifier_signals,
        "sources": sources,
        "product_sources": product_sources,
        "trait_sources": trait_sources,
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


def _structure_issues(product: Mapping[str, Any]) -> list[str]:
    issues: list[str] = []
    if not _string_list(product.get("genres")):
        issues.append("genres")
    family = str(product.get("product_family") or "").strip()
    if not family or family == "unknown":
        issues.append("product_family")
    subfamily = str(product.get("product_subfamily") or "").strip()
    if not subfamily or subfamily == "unknown":
        issues.append("product_subfamily")
    route_anchor = str(product.get("route_anchor") or "").strip()
    if not route_anchor:
        issues.append("route_anchor")
    route_family = str(product.get("route_family") or "").strip()
    if not route_family or route_family == "unanchored":
        issues.append("route_family")
    trait_coverage = {
        trait
        for field in ("implied_traits", "core_traits", "default_traits", "family_traits", "subtype_traits")
        for trait in _string_list(product.get(field))
    }
    if not trait_coverage:
        issues.append("trait_structure")
    return issues


def _structure_metrics(products: list[Mapping[str, Any]]) -> dict[str, Any]:
    missing_field_counts: Counter[str] = Counter()
    weak_boundary_only = 0
    weak_route_governance = 0
    missing_products: list[str] = []

    for product in products:
        issues = _structure_issues(product)
        if issues:
            missing_products.append(str(product["id"]))
            missing_field_counts.update(issues)

        route_anchor = str(product.get("route_anchor") or "").strip()
        route_family = str(product.get("route_family") or "").strip()
        boundary_tags = _string_list(product.get("boundary_tags"))
        family_level_reason = str(product.get("family_level_reason") or "").strip()

        if boundary_tags and not family_level_reason and str(product.get("max_match_stage") or "").strip() == "family":
            weak_boundary_only += 1

        if route_anchor and route_family:
            definition = route_anchor_definition(route_anchor)
            if definition is not None and definition.route_family != route_family:
                weak_route_governance += 1
            primary = str(product.get("primary_standard_code") or "").strip()
            if primary and not route_family.endswith("_boundary"):
                derived_family = family_from_standard_code(primary, prefer_wearable=(route_family == "av_ict_wearable"))
                if derived_family and derived_family != route_family:
                    weak_route_governance += 1

    return {
        "product_count": len(products),
        "missing_structure_products": len(missing_products),
        "unknown_family": sum(1 for product in products if str(product.get("product_family") or "").strip() in {"", "unknown"}),
        "unanchored_route": sum(
            1 for product in products if str(product.get("route_family") or "").strip() in {"", "unanchored"}
        ),
        "missing_field_counts": dict(sorted(missing_field_counts.items())),
        "weak_boundary_only_products": weak_boundary_only,
        "weak_route_governance_products": weak_route_governance,
    }


def _unused_trait_report(unused_traits: list[str], trait_sources: Mapping[str, str]) -> list[str]:
    rows: list[str] = []
    for trait_id in unused_traits:
        source = trait_sources.get(trait_id, "<unknown source>")
        rows.append(f"MEDIUM: {trait_id} (defined but not referenced; source: {source})")
    return rows


def _products_missing_structure(products: list[Mapping[str, Any]]) -> list[str]:
    findings: list[str] = []
    for product in products:
        issues = _structure_issues(product)
        if issues:
            findings.append(f"{product['id']}: missing {', '.join(issues)}")
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
        route_anchor = str(product.get("route_anchor") or "").strip()
        if not tags and not max_stage and not cap:
            continue
        parts: list[str] = []
        if route_anchor:
            parts.append("route_anchor=" + route_anchor)
        if tags:
            parts.append("boundary_tags=" + ",".join(tags))
        if max_stage:
            parts.append("max_match_stage=" + max_stage)
        if cap:
            parts.append("route_confidence_cap=" + cap)
        findings.append(f"{product['id']}: " + "; ".join(parts))
    return findings


def _weak_route_governance_report(products: list[Mapping[str, Any]]) -> list[str]:
    findings: list[str] = []
    for product in products:
        route_anchor = str(product.get("route_anchor") or "").strip()
        route_family = str(product.get("route_family") or "").strip()
        if not route_anchor or not route_family:
            continue

        definition = route_anchor_definition(route_anchor)
        if definition is not None and definition.route_family != route_family:
            findings.append(
                f"{product['id']}: route_anchor={route_anchor} expects {definition.route_family}, found {route_family}"
            )
            continue

        primary = str(product.get("primary_standard_code") or "").strip()
        if not primary or route_family.endswith("_boundary"):
            continue
        derived_family = family_from_standard_code(primary, prefer_wearable=(route_family == "av_ict_wearable"))
        if derived_family and derived_family != route_family:
            findings.append(f"{product['id']}: primary_standard={primary} aligns with {derived_family}, found {route_family}")
    return findings


def _boundary_heavy_report(products: list[Mapping[str, Any]]) -> list[str]:
    findings: list[str] = []
    for product in products:
        tags = _string_list(product.get("boundary_tags"))
        if not tags:
            continue
        if str(product.get("max_match_stage") or "").strip() != "family":
            continue
        if str(product.get("route_confidence_cap") or "").strip() not in {"low", "medium"}:
            continue
        reason = str(product.get("family_level_reason") or "").strip() or "no family_level_reason"
        findings.append(f"{product['id']}: boundary-heavy family-only handling ({reason})")
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


def _counts_by_file(
    products: list[Mapping[str, Any]],
    product_sources: Mapping[str, str],
    *,
    issue_key: str,
    predicate,
) -> list[str]:
    counts: Counter[str] = Counter()
    for product in products:
        if predicate(product):
            counts[product_sources.get(str(product["id"]), "<unknown source>")] += 1
    return [f"{source}: {count} {issue_key}" for source, count in counts.most_common()]


def _print_section(title: str, items: Iterable[str]) -> None:
    rows = list(items)
    print(f"\n{title}")
    if not rows:
        print("  none")
        return
    for row in rows:
        print(f"  - {row}")


def _report_payload(
    catalogs: Mapping[str, Any],
    *,
    minimum_aliases: int,
    broad_alias_threshold: int,
    compare: Mapping[str, Any] | None,
) -> dict[str, Any]:
    trait_ids = {row["id"] for row in catalogs["traits"]}
    referenced_traits = _collect_referenced_traits(catalogs)
    unused_traits = sorted(trait_ids - referenced_traits)
    raw_products = catalogs["products_raw"]
    normalized_products = catalogs["products"]

    return {
        "counts": {key: len(value) for key, value in catalogs.items() if isinstance(value, list)},
        "structure": {
            "raw": _structure_metrics(raw_products),
            "normalized": _structure_metrics(normalized_products),
        },
        "unused_traits": _unused_trait_report(unused_traits, catalogs["trait_sources"]),
        "thin_alias_products": _products_with_thin_aliases(normalized_products, minimum_aliases),
        "alias_collisions": _alias_collision_rows(normalized_products, broad_alias_threshold),
        "missing_structure_products": _products_missing_structure(normalized_products),
        "weak_route_governance": _weak_route_governance_report(normalized_products),
        "boundary_heavy_products": _boundary_heavy_report(normalized_products),
        "products_lacking_decisive_clues": _products_lacking_decisive_clues(normalized_products),
        "products_likely_to_overmatch": _products_likely_to_overmatch(normalized_products),
        "boundary_product_report": _boundary_product_report(normalized_products),
        "summaries": {
            "families": _family_summary(normalized_products),
            "genres": _genre_summary(normalized_products),
            "route_families": _route_family_summary(normalized_products),
            "trait_density": _trait_density_summary(normalized_products),
            "traits_per_product": _traits_per_product_distribution(normalized_products),
        },
        "by_file": {
            "raw_unknown_family": _counts_by_file(
                raw_products,
                catalogs["product_sources"],
                issue_key="unknown family rows",
                predicate=lambda product: str(product.get("product_family") or "").strip() in {"", "unknown"},
            ),
            "raw_unanchored_route": _counts_by_file(
                raw_products,
                catalogs["product_sources"],
                issue_key="unanchored route rows",
                predicate=lambda product: str(product.get("route_family") or "").strip() in {"", "unanchored"},
            ),
            "raw_missing_structure": _counts_by_file(
                raw_products,
                catalogs["product_sources"],
                issue_key="missing structure rows",
                predicate=lambda product: bool(_structure_issues(product)),
            ),
            "normalized_boundary_heavy": _counts_by_file(
                normalized_products,
                catalogs["product_sources"],
                issue_key="boundary-heavy rows",
                predicate=lambda product: bool(_string_list(product.get("boundary_tags"))),
            ),
        },
        "diff": _diff_summary(catalogs, compare) if compare is not None else None,
    }


def run(
    command: str,
    *,
    minimum_aliases: int,
    broad_alias_threshold: int,
    compare_dir: str | None = None,
    data_dir: str | None = None,
    strict_structure: bool = False,
    by_file: bool = False,
    json_output: bool = False,
) -> int:
    try:
        catalogs = _load_validated_catalogs(data_dir=data_dir)
        comparison = _load_validated_catalogs(data_dir=compare_dir) if compare_dir else None
    except KnowledgeBaseError as exc:
        if json_output:
            print(json.dumps({"ok": False, "error": str(exc)}, indent=2))
        else:
            print(f"Validation failed: {exc}")
        return 1

    payload = _report_payload(
        catalogs,
        minimum_aliases=minimum_aliases,
        broad_alias_threshold=broad_alias_threshold,
        compare=comparison,
    )

    if json_output:
        out: dict[str, Any] = {"ok": True, "command": command, **payload}
        print(json.dumps(out, indent=2, sort_keys=True))
    else:
        if command in {"validate", "all"}:
            counts = payload["counts"]
            print("Catalog validation passed.")
            print("Counts:", ", ".join(f"{key}={value}" for key, value in sorted(counts.items())))
            _print_section("Catalog Sources", _source_summary(catalogs))

        if command in {"summary", "all"}:
            raw_metrics = payload["structure"]["raw"]
            normalized_metrics = payload["structure"]["normalized"]
            _print_section(
                "Structure Metrics",
                [
                    f"raw unknown family: {raw_metrics['unknown_family']}",
                    f"normalized unknown family: {normalized_metrics['unknown_family']}",
                    f"raw unanchored route: {raw_metrics['unanchored_route']}",
                    f"normalized unanchored route: {normalized_metrics['unanchored_route']}",
                    f"raw missing structure rows: {raw_metrics['missing_structure_products']}",
                    f"normalized missing structure rows: {normalized_metrics['missing_structure_products']}",
                ],
            )
            _print_section("Product Families", payload["summaries"]["families"][:20])
            _print_section("Product Genres", payload["summaries"]["genres"][:20])
            _print_section("Route Families", payload["summaries"]["route_families"])
            _print_section("Trait Density", payload["summaries"]["trait_density"])
            _print_section("Traits Per Product", payload["summaries"]["traits_per_product"])

        if command in {"report", "all"}:
            raw_metrics = payload["structure"]["raw"]
            normalized_metrics = payload["structure"]["normalized"]
            _print_section(
                "Structure Counts",
                [
                    f"raw missing fields: {raw_metrics['missing_field_counts']}",
                    f"normalized missing fields: {normalized_metrics['missing_field_counts']}",
                    f"normalized weak boundary-only rows: {normalized_metrics['weak_boundary_only_products']}",
                    f"normalized weak route-governance rows: {normalized_metrics['weak_route_governance_products']}",
                ],
            )
            _print_section("Unused Traits", payload["unused_traits"])
            _print_section(
                f"Products With Fewer Than {minimum_aliases} Aliases",
                payload["thin_alias_products"],
            )
            _print_section(
                f"Alias Collisions Shared By {broad_alias_threshold}+ Products",
                payload["alias_collisions"],
            )
            _print_section("Products Missing Structure", payload["missing_structure_products"])
            _print_section("Weak Route Governance", payload["weak_route_governance"])
            _print_section("Boundary-Heavy Products", payload["boundary_heavy_products"])
            _print_section("Products Lacking Decisive Clues", payload["products_lacking_decisive_clues"])
            _print_section("Products Likely To Overmatch", payload["products_likely_to_overmatch"])
            _print_section("Boundary Product Report", payload["boundary_product_report"])

        if by_file and command in {"summary", "report", "all"}:
            _print_section("By-File Raw Unknown Family", payload["by_file"]["raw_unknown_family"])
            _print_section("By-File Raw Unanchored Route", payload["by_file"]["raw_unanchored_route"])
            _print_section("By-File Raw Missing Structure", payload["by_file"]["raw_missing_structure"])
            _print_section("By-File Normalized Boundary Load", payload["by_file"]["normalized_boundary_heavy"])

        if payload["diff"] is not None and command in {"summary", "report", "all"}:
            _print_section("Catalog Diff Summary", payload["diff"])

    if command in {"report", "all"} and strict_structure:
        if payload["structure"]["normalized"]["missing_structure_products"] > 0:
            return 1
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate and audit RuleGrid catalog integrity.")
    parser.add_argument("command", nargs="?", choices=("validate", "summary", "report", "all"), default="all")
    parser.add_argument("--minimum-aliases", type=int, default=4)
    parser.add_argument("--broad-alias-threshold", type=int, default=3)
    parser.add_argument("--compare-dir", type=str, default=None, help="Optional alternate data directory for an added/removed catalog diff summary.")
    parser.add_argument("--data-dir", type=str, default=None, help="Explicit data directory to validate instead of the default repo catalog.")
    parser.add_argument("--strict-structure", action="store_true", help="Fail report/all mode when normalized products still miss required structure.")
    parser.add_argument("--by-file", action="store_true", help="Show file-level hotspot summaries for raw catalog structure issues.")
    parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON instead of human-readable sections.")
    args = parser.parse_args()
    return run(
        args.command,
        minimum_aliases=args.minimum_aliases,
        broad_alias_threshold=args.broad_alias_threshold,
        compare_dir=args.compare_dir,
        data_dir=args.data_dir,
        strict_structure=args.strict_structure,
        by_file=args.by_file,
        json_output=args.json,
    )


if __name__ == "__main__":
    raise SystemExit(main())
