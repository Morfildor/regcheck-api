from __future__ import annotations

from collections.abc import Callable
from datetime import date

from app.domain.catalog_types import LegislationCatalogRow, StandardCatalogRow
from app.domain.models import LegislationItem, LegislationSection, RedArticleRoute


def _timing_status(row: LegislationCatalogRow, today: date, parse_date: Callable[[object], date | None]) -> str:
    if row.bucket == "informational":
        return "informational"

    applicable_from = parse_date(row.applicable_from)
    applicable_until = parse_date(row.applicable_until)

    if applicable_from and today < applicable_from:
        return "future"
    if applicable_until and today > applicable_until:
        return "legacy"
    return "current"


def _fact_basis_for_legislation(
    row: LegislationCatalogRow,
    traits: set[str],
    confirmed_traits: set[str],
) -> str:
    relevant = (
        set(row.all_of_traits)
        | (set(row.any_of_traits) & traits)
        | (set(row.none_of_traits) & traits)
    )
    if not relevant:
        return "confirmed"
    if relevant.issubset(confirmed_traits):
        return "confirmed"
    if relevant & confirmed_traits:
        return "mixed"
    return "inferred"


def _legislation_matches(
    row: LegislationCatalogRow,
    traits: set[str],
    functional_classes: set[str],
    product_type: str | None,
    matched_products: set[str],
    product_genres: set[str],
) -> bool:
    all_of_traits = set(row.all_of_traits)
    any_of_traits = set(row.any_of_traits)
    none_of_traits = set(row.none_of_traits)
    all_of_classes = set(row.all_of_functional_classes)
    any_of_classes = set(row.any_of_functional_classes)
    none_of_classes = set(row.none_of_functional_classes)
    any_of_products = set(row.any_of_product_types)
    exclude_products = set(row.exclude_product_types)
    any_of_genres = set(row.any_of_genres)
    exclude_genres = set(row.exclude_genres)

    if all_of_traits and not all_of_traits.issubset(traits):
        return False
    if any_of_traits and not (any_of_traits & traits):
        return False
    if none_of_traits & traits:
        return False

    if all_of_classes and not all_of_classes.issubset(functional_classes):
        return False
    if any_of_classes and not (any_of_classes & functional_classes):
        return False
    if none_of_classes & functional_classes:
        return False

    candidate_products = set(matched_products)
    if product_type:
        candidate_products.add(product_type)

    product_hit = bool(candidate_products & any_of_products)
    genre_hit = bool(product_genres & any_of_genres)

    if candidate_products & exclude_products:
        return False
    if product_genres & exclude_genres:
        return False
    if any_of_products and any_of_genres:
        if row.bucket == "informational":
            if not (product_hit and genre_hit):
                return False
        elif not (product_hit or genre_hit):
            return False
    elif any_of_products and not product_hit:
        return False
    elif any_of_genres and not genre_hit:
        return False

    return True


def _directive_keys(items: list[LegislationItem]) -> list[str]:
    keys: list[str] = []
    has_non_informational = {item.directive_key for item in items if item.bucket != "informational"}
    for item in items:
        if item.directive_key not in has_non_informational:
            continue
        if item.directive_key not in keys:
            keys.append(item.directive_key)
    return keys


def _legislation_sort_key(row: LegislationCatalogRow, directive_rank: Callable[[str], int]) -> tuple[int, int, str]:
    timing_rank = {"current": 0, "future": 1, "legacy": 2, "informational": 3}
    return (
        directive_rank(str(row.get("directive_key") or "OTHER")),
        timing_rank.get(str(row.get("timing_status") or "current"), 9),
        row.code,
    )


def _build_red_sub_articles(traits: set[str], red_art_33_traits: set[str]) -> list[dict[str, object]]:
    has_art_33 = bool(red_art_33_traits & traits)
    return [
        RedArticleRoute(
            article="Art. 3.1(a)",
            label="Safety",
            description="Safety and health - LVD safety objectives apply without voltage limit",
            applicable=True,
        ).model_dump(),
        RedArticleRoute(
            article="Art. 3.1(b)",
            label="EMC",
            description="Electromagnetic compatibility",
            applicable=True,
        ).model_dump(),
        RedArticleRoute(
            article="Art. 3.2",
            label="Radio",
            description="Radio / spectrum efficiency",
            applicable=True,
        ).model_dump(),
        RedArticleRoute(
            article="Art. 3.3",
            label="Conditional",
            description="Privacy / fraud / network / emergency / software / charging routes",
            applicable=has_art_33,
        ).model_dump(),
    ]


def _remove_standalone_lvd_emc_for_radio(items: list[LegislationItem]) -> list[LegislationItem]:
    return [item for item in items if not (item.directive_key in {"LVD", "EMC"} and item.bucket == "ce")]


def _attach_red_sub_articles(items: list[LegislationItem], traits: set[str], red_art_33_traits: set[str]) -> list[LegislationItem]:
    sub_articles = [RedArticleRoute.model_validate(item) for item in _build_red_sub_articles(traits, red_art_33_traits)]
    return [
        item.model_copy(update={"sub_articles": sub_articles})
        if item.directive_key == "RED" and item.bucket == "ce"
        else item
        for item in items
    ]


def _route_condition_hint(row: LegislationCatalogRow | StandardCatalogRow) -> str | None:
    route_traits = set(row.all_of_traits if isinstance(row, LegislationCatalogRow) else row.applies_if_all) | set(
        row.any_of_traits if isinstance(row, LegislationCatalogRow) else row.applies_if_any
    )
    if {"medical_claims", "medical_context", "possible_medical_boundary"} & route_traits:
        return "conditional on claim / medical-use context"
    if {"personal_data_likely", "health_related", "account", "authentication", "camera", "microphone", "location"} & route_traits:
        return "conditional on data handling"
    if route_traits:
        return "conditional on product function"
    return None


def _legislation_applicability_state(row: LegislationCatalogRow) -> str:
    if row.get("timing_status") == "future":
        return "upcoming"
    if row.applicability == "conditional":
        return "conditional"
    return "current"


def _standard_applicability_state(row: StandardCatalogRow, timing_status: str) -> str:
    if timing_status == "future":
        return "upcoming"
    if row.get("item_type") == "review":
        return "review-dependent"
    return "current"


def _legislation_sections_from_items(items: list[LegislationItem]) -> list[LegislationSection]:
    section_titles = {
        "ce": "CE routes",
        "non_ce": "Parallel obligations",
        "framework": "Additional framework checks",
        "future": "Future / lifecycle watchlist",
        "informational": "Informational notices",
    }
    sections_dict: dict[str, list[LegislationItem]] = {
        "ce": [],
        "non_ce": [],
        "framework": [],
        "future": [],
        "informational": [],
    }
    for item in items:
        sections_dict[item.bucket].append(item)
    return [
        LegislationSection(
            key=key,
            title=section_titles[key],
            count=len(value),
            items=value,
        )
        for key, value in sections_dict.items()
        if value
    ]


def _filter_legislation_items_for_route_plan(items: list[LegislationItem], primary_directive: str | None, exclusions: dict[str, set[str]]) -> list[LegislationItem]:
    if not primary_directive:
        return items
    excluded = exclusions.get(primary_directive, set())
    if not excluded:
        return items
    return [item for item in items if item.directive_key not in excluded]


__all__ = [
    "_attach_red_sub_articles",
    "_directive_keys",
    "_fact_basis_for_legislation",
    "_filter_legislation_items_for_route_plan",
    "_legislation_sort_key",
    "_legislation_applicability_state",
    "_legislation_matches",
    "_legislation_sections_from_items",
    "_remove_standalone_lvd_emc_for_radio",
    "_route_condition_hint",
    "_standard_applicability_state",
    "_timing_status",
]
