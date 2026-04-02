from __future__ import annotations

from collections import defaultdict

from app.domain.models import LegislationItem, StandardItem, StandardSection, StandardSectionItem

from .routing import DIRECTIVE_TITLES, _directive_rank, _route_title


def _sort_standard_items(
    items: list[StandardItem],
    *,
    primary_standard_code: str | None = None,
    supporting_standard_codes: list[str] | None = None,
) -> list[StandardItem]:
    support_codes = set(supporting_standard_codes or [])

    def route_bucket(item: StandardItem) -> int:
        if primary_standard_code and item.code == primary_standard_code:
            return 0
        if item.code in support_codes:
            return 1
        if item.category == "safety":
            return 2
        return 3

    def key(item: StandardItem) -> tuple[int, int, int, int, str]:
        code = item.code or ""
        if item.directive == "LVD":
            if code.startswith("EN 60335-2-"):
                bucket = 0
            elif code == "EN 60335-1":
                bucket = 1
            elif code in {"EN 62233", "EN 62311", "EN 62479"}:
                bucket = 2
            else:
                bucket = 3
        elif item.directive == "MD":
            if code.startswith("EN 62841-2-"):
                bucket = 0
            elif code == "EN 62841-1":
                bucket = 1
            else:
                bucket = 2
        elif item.directive == "EMC":
            if code.startswith("EN 55014-"):
                bucket = 0
            elif code.startswith("EN 61000-3-"):
                bucket = 1
            else:
                bucket = 2
        elif item.directive == "RED":
            if item.category == "safety":
                bucket = 0
            elif item.category in {"emc", "radio_emc"}:
                bucket = 1
            elif item.category == "radio":
                bucket = 2
            elif code in {"EN 62479", "EN 62311", "EN 50364"} or code.startswith("EN 62209"):
                bucket = 3
            elif item.category == "cybersecurity":
                bucket = 4
            else:
                bucket = 5
        else:
            bucket = 9
        return (route_bucket(item), _directive_rank(item.directive), bucket, -int(item.selection_priority or 0), code)

    return sorted(items, key=key)


def _standard_section_route_keys(item: StandardItem) -> list[str]:
    route_keys = (
        [item.directive]
        if item.category in {"safety", "radio_emc"}
        else ([key for key in item.directives if key] or [item.directive])
    )

    if item.directive == "RED" or "RED" in item.directives:
        route_keys = [key for key in route_keys if key not in {"LVD", "EMC"}]
        if item.directive == "RED" and "RED" not in route_keys:
            route_keys.append("RED")

    deduped: list[str] = []
    for key in route_keys:
        if key and key not in deduped:
            deduped.append(key)
    return deduped


def _standard_section_category(item: StandardItem, route_key: str) -> str:
    if route_key != "RED":
        return item.category
    if item.category in {"safety", "battery", "emf", "power"}:
        return "safety"
    if item.category in {"emc", "radio_emc"}:
        return "emc"
    return item.category


def _section_item_from_standard(
    item: StandardItem,
    *,
    route_key: str,
    directive_label: str,
    directive_title: str,
) -> StandardSectionItem:
    return StandardSectionItem(
        code=item.code,
        title=item.title,
        directive=item.directive,
        directives=list(item.directives),
        legislation_key=item.legislation_key,
        category=_standard_section_category(item, route_key),
        confidence=item.confidence,
        item_type=item.item_type,
        match_basis=item.match_basis,
        fact_basis=item.fact_basis,
        score=item.score,
        reason=item.reason,
        notes=item.notes,
        regime_bucket=item.regime_bucket,
        timing_status=item.timing_status,
        matched_traits_all=list(item.matched_traits_all),
        matched_traits_any=list(item.matched_traits_any),
        missing_required_traits=list(item.missing_required_traits),
        excluded_by_traits=list(item.excluded_by_traits),
        applies_if_products=list(item.applies_if_products),
        exclude_if_products=list(item.exclude_if_products),
        applies_if_genres=list(item.applies_if_genres),
        product_match_type=item.product_match_type,
        standard_family=item.standard_family,
        is_harmonized=item.is_harmonized,
        harmonized_under=item.harmonized_under,
        harmonization_status=item.harmonization_status,
        harmonized_reference=item.harmonized_reference,
        version=item.version,
        dated_version=item.dated_version,
        supersedes=item.supersedes,
        test_focus=list(item.test_focus),
        evidence_hint=list(item.evidence_hint),
        keywords=list(item.keywords),
        keyword_hits=list(item.keyword_hits),
        selection_group=item.selection_group,
        selection_priority=item.selection_priority,
        required_fact_basis=item.required_fact_basis,
        jurisdiction=item.jurisdiction,
        applicability_state=item.applicability_state,
        applicability_hint=item.applicability_hint,
        triggered_by_directive=route_key,
        triggered_by_label=directive_label,
        triggered_by_title=directive_title,
    )


def _build_standard_sections(
    items: list[StandardItem],
    *,
    primary_standard_code: str | None = None,
    supporting_standard_codes: list[str] | None = None,
) -> list[StandardSection]:
    grouped: dict[str, list[StandardItem]] = defaultdict(list)
    for item in items:
        for key in _standard_section_route_keys(item):
            grouped[key].append(item)
    sections: list[StandardSection] = []
    for key in sorted(grouped.keys(), key=_directive_rank):
        route_items = _sort_standard_items(
            grouped[key],
            primary_standard_code=primary_standard_code,
            supporting_standard_codes=supporting_standard_codes,
        )
        directive_label, directive_title = DIRECTIVE_TITLES.get(key, (key, key))
        section_items = [
            _section_item_from_standard(
                item,
                route_key=key,
                directive_label=directive_label,
                directive_title=directive_title,
            )
            for item in route_items
        ]
        sections.append(
            StandardSection(
                key=key,
                directive_key=key,
                directive_label=directive_label,
                directive_title=directive_title,
                title=_route_title(key),
                count=len(section_items),
                items=section_items,
            )
        )
    return sections


def _primary_legislation_by_directive(items: list[LegislationItem]) -> dict[str, LegislationItem]:
    by_directive: dict[str, LegislationItem] = {}
    for item in items:
        existing = by_directive.get(item.directive_key)
        if existing is None:
            by_directive[item.directive_key] = item
            continue
        existing_rank = 1 if existing.bucket == "informational" else 0
        current_rank = 1 if item.bucket == "informational" else 0
        if current_rank < existing_rank:
            by_directive[item.directive_key] = item
    return by_directive


__all__ = [
    "_build_standard_sections",
    "_primary_legislation_by_directive",
    "_sort_standard_items",
]
