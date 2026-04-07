from __future__ import annotations

from collections.abc import Callable
from typing import cast

from app.domain.catalog_types import ProductCatalogRow
from app.domain.models import ConfidenceLevel
from app.services.standard_codes import canonicalize_standard_code, normalized_standard_codes

from .contracts import ClassifierTraitsSnapshot
from .routing_models import RoutePlan


def _cap_confidence(current: ConfidenceLevel, requested_cap: object) -> ConfidenceLevel:
    if requested_cap not in {"low", "medium", "high"}:
        return current
    rank = {"low": 0, "medium": 1, "high": 2}
    cap = cast(ConfidenceLevel, requested_cap)
    return current if rank[current] <= rank[cap] else cap


def _products_by_id(products: tuple[ProductCatalogRow, ...]) -> dict[str, ProductCatalogRow]:
    return {row.id: row for row in products}


def _route_product_row(
    products_by_id: dict[str, ProductCatalogRow],
    product_type: str | None,
    matched_products: set[str] | None = None,
) -> ProductCatalogRow | None:
    candidate_ids: list[str] = []
    if product_type:
        candidate_ids.append(product_type)
    for candidate_id in sorted(matched_products or set()):
        if candidate_id not in candidate_ids:
            candidate_ids.append(candidate_id)
    for candidate_id in candidate_ids:
        row = products_by_id.get(candidate_id)
        if row and (row.route_family or row.primary_standard_code):
            return row
    return None


def _route_scope_from_family(route_family_scope: dict[str, str], route_family: str | None) -> str | None:
    if not route_family:
        return None
    return route_family_scope.get(route_family)


def _normalized_standard_codes(codes: set[str] | list[str] | None) -> list[str]:
    return normalized_standard_codes(codes)


def _family_from_standard_code(
    route_standard_family_rules: tuple[tuple[str, str, str], ...],
    code: str,
    prefer_wearable: bool,
) -> str | None:
    code = canonicalize_standard_code(code)
    for prefix, family, _label in route_standard_family_rules:
        if code.startswith(prefix):
            if family == "av_ict" and prefer_wearable:
                return "av_ict_wearable"
            return family
    return None


def _best_primary_standard_for_family(
    route_standard_family_rules: tuple[tuple[str, str, str], ...],
    route_family: str,
    preferred_codes: list[str],
) -> str | None:
    family_codes: list[str] = []
    for code in preferred_codes:
        generic_family = _family_from_standard_code(route_standard_family_rules, code, prefer_wearable=False)
        wearable_family = _family_from_standard_code(route_standard_family_rules, code, prefer_wearable=True)
        if route_family in {generic_family, wearable_family}:
            family_codes.append(code)
    if not family_codes:
        return None

    if route_family == "household_appliance":
        part2 = [code for code in family_codes if code.startswith("EN 60335-2-")]
        if part2:
            return sorted(part2)[0]
    if route_family == "machinery_power_tool":
        part2 = [code for code in family_codes if code.startswith("EN 62841-2-")]
        if part2:
            return sorted(part2)[0]
    if route_family == "lighting_device":
        for preferred in ("EN IEC 62560", "EN 60598-1"):
            if preferred in family_codes:
                return preferred
    if route_family == "ev_charging":
        for preferred in ("EN IEC 61851-1", "IEC 62752"):
            if preferred in family_codes:
                return preferred
    if route_family == "ev_connector_accessory" and "EN 62196-2" in family_codes:
        return "EN 62196-2"
    if route_family in {"av_ict", "av_ict_wearable"} and "EN 62368-1" in family_codes:
        return "EN 62368-1"
    return sorted(family_codes)[0]


def _fallback_route_plan_from_preferred_standards(
    preferred_standard_codes: set[str] | list[str] | None,
    traits: set[str],
    confidence: ConfidenceLevel,
    *,
    route_standard_family_rules: tuple[tuple[str, str, str], ...],
    route_family_scope: dict[str, str],
    route_family_primary_directive: dict[str, str],
) -> RoutePlan | None:
    normalized_codes = _normalized_standard_codes(preferred_standard_codes)
    if not normalized_codes:
        return None

    prefer_wearable = bool({"wearable", "body_worn_or_applied"} & traits)
    route_family: str | None = None
    label = "product"
    for code in normalized_codes:
        route_family = _family_from_standard_code(route_standard_family_rules, code, prefer_wearable)
        if route_family:
            for prefix, family, candidate_label in route_standard_family_rules:
                if family == route_family and code.startswith(prefix):
                    label = candidate_label
                    break
            break

    if not route_family:
        return None

    primary_standard_code = _best_primary_standard_for_family(route_standard_family_rules, route_family, normalized_codes)
    supporting_standard_codes = [
        code
        for code in normalized_codes
        if code != primary_standard_code and _family_from_standard_code(route_standard_family_rules, code, prefer_wearable) == route_family
    ]
    if primary_standard_code:
        reason = f"{label} calibration prefers {primary_standard_code} as the primary product-safety route."
    else:
        reason = f"{label} calibration prefers the {route_family.replace('_', ' ')} product-safety route."

    return RoutePlan(
        primary_route_family=route_family,
        primary_standard_code=primary_standard_code,
        supporting_standard_codes=supporting_standard_codes[:4],
        primary_directive=route_family_primary_directive.get(route_family),
        reason=reason,
        confidence=confidence,
        scope_route=_route_scope_from_family(route_family_scope, route_family) or "generic",
    )


def _build_route_plan(
    traits_data: ClassifierTraitsSnapshot,
    traits: set[str],
    matched_products: set[str],
    product_type: str | None,
    *,
    route_product_row: Callable[[str | None, set[str]], ProductCatalogRow | None],
    route_family_scope: dict[str, str],
    route_family_primary_directive: dict[str, str],
    route_standard_family_rules: tuple[tuple[str, str, str], ...],
) -> RoutePlan:
    product_match_confidence = traits_data.product_match_confidence
    route_row = route_product_row(product_type, matched_products) if callable(route_product_row) else None
    if route_row:
        route_family = route_row.route_family
        primary_standard_code = route_row.primary_standard_code
        supporting_standard_codes = list(route_row.supporting_standard_codes)
        scope_route = _route_scope_from_family(route_family_scope, route_family) or "generic"
        label = route_row.label or route_row.id or product_type or "product"
        confidence = _cap_confidence(product_match_confidence, route_row.get("route_confidence_cap"))
        if primary_standard_code:
            reason = f"{label} maps to {primary_standard_code} as the primary product-safety route."
        elif route_family:
            reason = f"{label} maps to the {route_family.replace('_', ' ')} product-safety route."
        else:
            reason = f"{label} maps to a product-specific safety route."
        if route_row.get("route_confidence_cap") in {"low", "medium"}:
            reason += " The route remains conservative because the product sits near a catalog boundary."
        return RoutePlan(
            primary_route_family=route_family,
            primary_standard_code=primary_standard_code,
            supporting_standard_codes=supporting_standard_codes,
            primary_directive=route_family_primary_directive.get(route_family or ""),
            reason=reason,
            confidence=confidence,
            scope_route=scope_route,
        )

    if "toy" in traits:
        return RoutePlan(
            primary_route_family="toy",
            primary_directive="TOY",
            reason="Toy intent is explicit in the description.",
            confidence=product_match_confidence,
            scope_route="toy",
        )

    if product_match_confidence != "low":
        fallback = _fallback_route_plan_from_preferred_standards(
            traits_data.preferred_standard_codes,
            traits,
            product_match_confidence,
            route_standard_family_rules=route_standard_family_rules,
            route_family_scope=route_family_scope,
            route_family_primary_directive=route_family_primary_directive,
        )
        if fallback is not None:
            return fallback

    return RoutePlan(confidence=product_match_confidence)


__all__ = [
    "_build_route_plan",
    "_products_by_id",
    "_route_product_row",
    "_route_scope_from_family",
]
