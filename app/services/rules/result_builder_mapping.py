from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from app.domain.catalog_types import StandardCatalogRow
from app.domain.models import LegislationItem, StandardItem

from .routing import (
    _confidence_from_score,
    _route_condition_hint,
    _standard_applicability_state,
    _standard_primary_directive,
)

StandardRowLike = StandardCatalogRow | Mapping[str, Any]


def _standard_row(row: StandardRowLike) -> StandardCatalogRow:
    if isinstance(row, StandardCatalogRow):
        return row
    return StandardCatalogRow.model_validate(dict(row))


def _standard_item_from_row(
    row: StandardRowLike,
    legislation_by_directive: dict[str, LegislationItem],
    traits: set[str],
) -> StandardItem:
    standard = _standard_row(row)
    primary_directive = _standard_primary_directive(standard, traits)
    legislation = legislation_by_directive.get(primary_directive)
    timing_status = legislation.timing_status if legislation else "current"

    raw_directives = [directive for directive in standard.directives if isinstance(directive, str)]
    native_dir = raw_directives[0] if raw_directives else None
    gate_dir = str(standard.get("directive") or "")
    original_is_lvd_emc = native_dir in {"LVD", "EMC"} or gate_dir in {"LVD", "EMC"}
    if "radio" in traits and primary_directive == "RED" and original_is_lvd_emc:
        effective_directives: list[str] = ["RED"]
    else:
        effective_directives = raw_directives or [primary_directive]
        if "radio" not in traits:
            effective_directives = [directive for directive in effective_directives if directive != "RED"]
        if primary_directive and primary_directive not in effective_directives:
            effective_directives.append(primary_directive)

    return StandardItem(
        code=standard.code,
        title=standard.title,
        directive=primary_directive,
        directives=effective_directives,
        legislation_key=standard.legislation_key,
        category=standard.category or "other",
        confidence=_confidence_from_score(int(standard.get("score", 0))),
        item_type=standard.get("item_type", standard.item_type),
        match_basis=standard.get("match_basis", "traits"),
        fact_basis=standard.get("fact_basis", "confirmed"),
        score=int(standard.get("score", 0)),
        reason=standard.get("reason"),
        notes=standard.get("notes"),
        regime_bucket=legislation.bucket if legislation else None,
        timing_status=timing_status,
        matched_traits_all=standard.get("matched_traits_all", []),
        matched_traits_any=standard.get("matched_traits_any", []),
        missing_required_traits=standard.get("missing_required_traits", []),
        excluded_by_traits=standard.get("excluded_by_traits", []),
        applies_if_products=list(standard.applies_if_products),
        exclude_if_products=list(standard.exclude_if_products),
        applies_if_genres=list(standard.applies_if_genres),
        product_match_type=standard.get("product_match_type"),
        standard_family=standard.standard_family,
        is_harmonized=standard.is_harmonized,
        harmonized_under=standard.harmonized_under,
        harmonization_status=standard.harmonization_status,
        harmonized_reference=standard.harmonized_reference,
        version=standard.version,
        dated_version=standard.dated_version,
        supersedes=standard.supersedes,
        test_focus=list(standard.test_focus),
        evidence_hint=list(standard.evidence_hint),
        keywords=list(standard.keywords),
        keyword_hits=standard.get("keyword_hits", []),
        selection_group=standard.get("selection_group", standard.selection_group),
        selection_priority=int(standard.get("selection_priority", standard.selection_priority)),
        required_fact_basis=standard.get("required_fact_basis", standard.required_fact_basis),
        jurisdiction=str(standard.get("region") or "EU"),
        applicability_state=_standard_applicability_state(standard, timing_status),
        applicability_hint=_route_condition_hint(standard),
    )


__all__ = [
    "_standard_item_from_row",
    "_standard_row",
]
