from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from collections.abc import Iterable, Mapping
from typing import Any

from app.services.knowledge_base.loader import _load_yaml_raw
from app.services.knowledge_base.validator import (
    _string_list,
    _validate_classifier_signal_catalog,
    _validate_genres,
    _validate_legislations,
    _validate_products,
    _validate_standards,
    _validate_traits,
)
from app.services.knowledge_base.paths import KnowledgeBaseError


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


def _load_validated_catalogs() -> dict[str, Any]:
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

    return {
        "traits": traits,
        "genres": genres,
        "products": products,
        "legislations": legislations,
        "standards": standards,
        "classifier_signals": classifier_signals,
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


def _shared_aliases(products: list[Mapping[str, Any]], minimum_products: int) -> list[str]:
    owners_by_alias: dict[str, set[str]] = defaultdict(set)
    for product in products:
        pid = str(product["id"])
        for field in ALIAS_FIELDS:
            for alias in _string_list(product.get(field)):
                normalized = _normalize_token(alias)
                if normalized:
                    owners_by_alias[normalized].add(pid)

    findings: list[str] = []
    for alias, owners in sorted(owners_by_alias.items()):
        if len(owners) >= minimum_products:
            findings.append(f"{alias!r}: {', '.join(sorted(owners))}")
    return findings


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
        if not str(product.get("route_family") or "").strip():
            issues.append("no route_family")
        if not str(product.get("primary_standard_code") or "").strip():
            issues.append("no primary_standard_code")
        if issues:
            findings.append(f"{pid}: {', '.join(issues)}")
    return findings


def _family_summary(products: list[Mapping[str, Any]]) -> list[str]:
    family_counts = Counter(str(product.get("product_family") or "unknown") for product in products)
    return [f"{family}: {count}" for family, count in family_counts.most_common()]


def _genre_summary(products: list[Mapping[str, Any]]) -> list[str]:
    genre_counts = Counter()
    for product in products:
        genre_counts.update(_string_list(product.get("genres")))
    return [f"{genre}: {count}" for genre, count in genre_counts.most_common()]


def _trait_density_summary(products: list[Mapping[str, Any]]) -> list[str]:
    density: list[tuple[int, str]] = []
    for product in products:
        trait_count = 0
        for field in ("implied_traits", "core_traits", "default_traits", "family_traits", "subtype_traits"):
            trait_count += len(_string_list(product.get(field)))
        density.append((trait_count, str(product["id"])))
    density.sort(reverse=True)
    return [f"{pid}: {count} trait entries" for count, pid in density[:15]]


def _print_section(title: str, items: Iterable[str]) -> None:
    rows = list(items)
    print(f"\n{title}")
    if not rows:
        print("  none")
        return
    for row in rows:
        print(f"  - {row}")


def run(command: str, *, minimum_aliases: int, broad_alias_threshold: int) -> int:
    try:
        catalogs = _load_validated_catalogs()
    except KnowledgeBaseError as exc:
        print(f"Validation failed: {exc}")
        return 1

    if command in {"validate", "all"}:
        counts = {key: len(value) for key, value in catalogs.items() if isinstance(value, list)}
        print("Catalog validation passed.")
        print("Counts:", ", ".join(f"{key}={value}" for key, value in sorted(counts.items())))

    if command in {"summary", "all"}:
        _print_section("Product Families", _family_summary(catalogs["products"])[:20])
        _print_section("Product Genres", _genre_summary(catalogs["products"])[:20])
        _print_section("Trait Density", _trait_density_summary(catalogs["products"]))

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
            f"Aliases Shared By {broad_alias_threshold}+ Products",
            _shared_aliases(catalogs["products"], broad_alias_threshold),
        )
        _print_section("Products Missing Structure", _products_missing_structure(catalogs["products"]))

    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate and audit RuleGrid catalog integrity.")
    parser.add_argument("command", nargs="?", choices=("validate", "summary", "report", "all"), default="all")
    parser.add_argument("--minimum-aliases", type=int, default=4)
    parser.add_argument("--broad-alias-threshold", type=int, default=3)
    args = parser.parse_args()
    return run(args.command, minimum_aliases=args.minimum_aliases, broad_alias_threshold=args.broad_alias_threshold)


if __name__ == "__main__":
    raise SystemExit(main())
