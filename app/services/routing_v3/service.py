from __future__ import annotations

from collections.abc import Mapping

from app.domain.engine_models import KnownFactItem, RouteContext
from app.services.standards_engine.contracts import SelectionContext

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


def build_route_context(
    selection_context: SelectionContext | Mapping[str, object],
    known_facts: list[KnownFactItem],
    policy: RoutePolicyDecision,
    overlay_routes: list[str] | None = None,
) -> RouteContext:
    context = SelectionContext.from_mapping(selection_context)
    return RouteContext(
        scope_route=context.scope_route,
        scope_reasons=list(context.scope_reasons),
        context_tags=sorted(context.context_tags),
        known_fact_keys=[item.key for item in known_facts],
        jurisdiction="EU",
        route_trigger_reasons=list(context.scope_reasons),
        primary_route_family=policy.primary_route_family,
        primary_route_standard_code=policy.primary_standard_code,
        primary_route_reason=context.primary_route_reason or (policy.rationale[0] if policy.rationale else ""),
        overlay_routes=list(overlay_routes or []),
        route_confidence=policy.route_confidence,
    )
