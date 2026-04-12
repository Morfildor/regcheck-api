from __future__ import annotations

from .contracts import NormalizedClassifierEvidence, RoutePolicyDecision


def build_classifier_evidence(prepared) -> NormalizedClassifierEvidence:
    return NormalizedClassifierEvidence(
        product_type=prepared.product_type,
        product_match_stage=prepared.product_match_stage,
        product_match_confidence=prepared.traits_data.product_match_confidence,
        route_traits=set(prepared.route_traits),
        confirmed_traits=set(prepared.confirmed_traits),
        matched_products=set(prepared.routing_matched_products),
        product_genres=set(prepared.product_genres),
        preferred_standard_codes=set(prepared.likely_standards),
    )


def decide_route_policy(prepared, detected_directives: list[str] | None = None) -> RoutePolicyDecision:
    detected_directives = detected_directives or []
    route_plan = prepared.route_plan
    rationale: list[str] = []
    if route_plan.primary_route_family:
        rationale.append(f"primary_route_family={route_plan.primary_route_family}")
    if route_plan.primary_standard_code:
        rationale.append(f"primary_standard_code={route_plan.primary_standard_code}")
    if route_plan.reason:
        rationale.append(route_plan.reason)
    return RoutePolicyDecision(
        primary_route_family=route_plan.primary_route_family,
        directive_overlays=list(detected_directives),
        route_confidence=route_plan.confidence,
        preferred_standard_codes=sorted({*prepared.likely_standards, *route_plan.supporting_standard_codes}),
        preferred_standard_families=[route_plan.primary_route_family] if route_plan.primary_route_family else [],
        primary_standard_code=route_plan.primary_standard_code,
        primary_directive=route_plan.primary_directive,
        rationale=rationale,
    )
