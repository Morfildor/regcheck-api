from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Literal

from app.core.runtime_state import API_VERSION
from app.domain.models import (
    AnalysisAudit,
    AnalysisResult,
    AnalysisStats,
    ConfidencePanel,
    DecisionTraceEntry,
    Finding,
    HeroSummary,
    InputGapsPanel,
    KnownFactItem,
    LegislationItem,
    LegislationSection,
    MissingInformationItem,
    ProductMatchAudit,
    RiskLevel,
    RiskReason,
    RiskSummary,
    RouteContext,
    StandardItem,
    StandardMatchAudit,
    StandardSection,
    TraitEvidenceItem,
)

from .contracts import ClassifierTraitsSnapshot
from .facts import _build_quick_adds, _top_actions_from_missing
from .result_builder_audit import _safe_knowledge_base_meta
from .summary import _classification_summary, _primary_uncertainties
from .routing import ENGINE_VERSION, _confidence_level, _contradiction_severity, _product_match_stage

AnalysisDepth = Literal["quick", "standard", "deep"]


def _traits_snapshot(traits_data: ClassifierTraitsSnapshot | Mapping[str, Any]) -> ClassifierTraitsSnapshot:
    if isinstance(traits_data, ClassifierTraitsSnapshot):
        return traits_data
    return ClassifierTraitsSnapshot.from_mapping(traits_data)


def _build_analysis_result(
    *,
    description: str,
    depth: AnalysisDepth,
    normalized_description: str,
    traits_data: ClassifierTraitsSnapshot | Mapping[str, Any],
    diagnostics: list[str],
    matched_products: set[str],
    routing_matched_products: set[str],
    product_genres: set[str],
    likely_standards: set[str],
    trait_set: set[str],
    confirmed_traits: set[str],
    detected_directives: list[str],
    forced_directives: list[str],
    legislation_items: list[LegislationItem],
    legislation_sections: list[LegislationSection],
    standard_items: list[StandardItem],
    review_items: list[StandardItem],
    missing_items: list[MissingInformationItem],
    standard_sections: list[StandardSection],
    risk_reasons: list[RiskReason],
    risk_summary: RiskSummary,
    summary: str,
    findings: list[Finding],
    known_facts: list[KnownFactItem],
    trait_evidence: list[TraitEvidenceItem],
    product_match_audit: ProductMatchAudit,
    standard_match_audit: StandardMatchAudit,
    route_context: RouteContext,
    decision_trace: list[DecisionTraceEntry] | None = None,
    overall_risk: RiskLevel,
    current_risk: RiskLevel,
    future_risk: RiskLevel,
    degraded_reasons: list[str],
    warnings: list[str],
) -> AnalysisResult:
    traits_snapshot = _traits_snapshot(traits_data)
    product_match_stage = _product_match_stage(traits_snapshot.product_match_stage)
    product_match_confidence = _confidence_level(traits_snapshot.product_match_confidence, default="low")
    classification_confidence_below_threshold = product_match_confidence == "low"
    classification_is_ambiguous = classification_confidence_below_threshold or product_match_stage != "subtype"
    contradictions = list(traits_snapshot.contradictions)
    contradiction_severity = _contradiction_severity(traits_snapshot.contradiction_severity)
    inferred_traits = sorted(set(traits_snapshot.inferred_traits) | (trait_set - set(traits_snapshot.explicit_traits)))
    top_actions_limit = {"quick": 2, "standard": 3, "deep": 5}[depth]
    suggested_questions_limit = {"quick": 2, "standard": 6, "deep": 8}[depth]
    quick_adds_limit = {"quick": 4, "standard": 8, "deep": 10}[depth]
    top_actions = _top_actions_from_missing(missing_items, top_actions_limit)
    knowledge_base_meta = _safe_knowledge_base_meta(degraded_reasons, warnings)
    primary_regimes = [section.key for section in standard_sections[:4]]

    stats = AnalysisStats(
        legislation_count=len(legislation_items),
        current_legislation_count=len([x for x in legislation_items if x.timing_status == "current"]),
        future_legislation_count=len([x for x in legislation_items if x.timing_status == "future"]),
        standards_count=len(standard_items),
        review_items_count=len(review_items),
        current_review_items_count=len([x for x in review_items if x.timing_status == "current"]),
        future_review_items_count=len([x for x in review_items if x.timing_status == "future"]),
        harmonized_standards_count=len([x for x in standard_items if x.harmonization_status == "harmonized"]),
        state_of_the_art_standards_count=len([x for x in standard_items if x.harmonization_status == "state_of_the_art"]),
        product_gated_standards_count=len([x for x in standard_items if x.applies_if_products]),
        ambiguity_flag_count=1 if (contradictions or classification_is_ambiguous) else 0,
        missing_information_count=len(missing_items),
    )

    analysis_audit = AnalysisAudit(
        allowed_directives=detected_directives,
        matched_products=sorted(matched_products),
        routing_matched_products=sorted(routing_matched_products),
        preferred_standards=sorted(likely_standards),
        product_genres=sorted(product_genres),
        product_family=traits_snapshot.product_family,
        product_subtype=traits_snapshot.product_subtype,
        product_match_stage=product_match_stage,
        classification_is_ambiguous=classification_is_ambiguous,
        classification_confidence_below_threshold=classification_confidence_below_threshold,
        depth=depth,
        engine_version=ENGINE_VERSION,
        normalized_description=normalized_description,
        context_tags=route_context.context_tags,
        decision_trace=decision_trace or [],
    )

    return AnalysisResult(
        product_summary=description.strip(),
        overall_risk=overall_risk,
        current_compliance_risk=current_risk,
        future_watchlist_risk=future_risk,
        summary=summary,
        analyzed_description=description.strip(),
        normalized_description=normalized_description,
        product_type=traits_snapshot.product_type,
        product_family=traits_snapshot.product_family,
        product_family_confidence=traits_snapshot.product_family_confidence,
        product_subtype=traits_snapshot.product_subtype,
        product_subtype_confidence=traits_snapshot.product_subtype_confidence,
        product_match_stage=product_match_stage,
        product_match_confidence=product_match_confidence,
        classification_is_ambiguous=classification_is_ambiguous,
        classification_confidence_below_threshold=classification_confidence_below_threshold,
        classification_summary=_classification_summary(
            product_type=traits_snapshot.product_type,
            product_family=traits_snapshot.product_family,
            product_subtype=traits_snapshot.product_subtype,
            product_match_stage=product_match_stage,
            product_match_confidence=product_match_confidence,
            classification_is_ambiguous=classification_is_ambiguous,
        ),
        primary_uncertainties=_primary_uncertainties(contradictions, missing_items, degraded_reasons, warnings),
        route_trigger_reasons=route_context.route_trigger_reasons,
        triggered_routes=detected_directives,
        primary_route_standard_code=route_context.primary_route_standard_code,
        primary_route_reason=route_context.primary_route_reason,
        overlay_routes=route_context.overlay_routes,
        route_confidence=route_context.route_confidence,
        product_candidates=traits_snapshot.product_candidates,
        functional_classes=list(traits_snapshot.functional_classes),
        confirmed_functional_classes=list(traits_snapshot.confirmed_functional_classes),
        explicit_traits=list(traits_snapshot.explicit_traits),
        confirmed_traits=sorted(confirmed_traits),
        inferred_traits=inferred_traits,
        assumptions_or_inferred_traits=inferred_traits,
        all_traits=sorted(trait_set),
        directives=detected_directives,
        forced_directives=forced_directives,
        legislations=legislation_items,
        ce_legislations=[x for x in legislation_items if x.bucket == "ce"],
        non_ce_obligations=[x for x in legislation_items if x.bucket == "non_ce"],
        framework_regimes=[x for x in legislation_items if x.bucket == "framework"],
        future_regimes=[x for x in legislation_items if x.bucket == "future"],
        informational_items=[x for x in legislation_items if x.bucket == "informational"],
        standards=standard_items,
        review_items=review_items,
        missing_information=[item.message for item in missing_items],
        missing_information_items=missing_items,
        contradictions=contradictions,
        contradiction_severity=contradiction_severity,
        diagnostics=diagnostics,
        warnings=warnings,
        degraded_mode=bool(degraded_reasons),
        degraded_reasons=degraded_reasons,
        stats=stats,
        knowledge_base_meta=knowledge_base_meta,
        analysis_audit=analysis_audit,
        api_version=API_VERSION,
        engine_version=ENGINE_VERSION,
        catalog_version=knowledge_base_meta.version,
        trait_evidence=trait_evidence,
        product_match_audit=product_match_audit,
        standard_match_audit=standard_match_audit,
        standard_sections=standard_sections,
        standards_by_directive=standard_sections,
        legislation_sections=legislation_sections,
        risk_reasons=risk_reasons,
        risk_summary=risk_summary,
        hero_summary=HeroSummary(
            title="RuleGrid Regulatory Scoping",
            subtitle="Describe the product clearly to generate the standards route and the applicable legislation path.",
            primary_regimes=primary_regimes,
            confidence=product_match_confidence,
            depth=depth,
        ),
        confidence_panel=ConfidencePanel(
            confidence=product_match_confidence,
            classification_is_ambiguous=classification_is_ambiguous,
            classification_confidence_below_threshold=classification_confidence_below_threshold,
            matched_products=sorted(matched_products),
            product_family=traits_snapshot.product_family,
            product_genres=sorted(product_genres),
            product_subtype=traits_snapshot.product_subtype,
            product_match_stage=product_match_stage,
        ),
        input_gaps_panel=InputGapsPanel(
            items=missing_items,
            next_actions=top_actions,
            high_importance_count=len([item for item in missing_items if item.importance == "high"]),
        ),
        top_actions=top_actions,
        next_actions=top_actions,
        current_path=[section.title for section in standard_sections],
        future_watchlist=[item.title for item in legislation_items if item.bucket == "future"],
        suggested_questions=[item.message for item in missing_items[:suggested_questions_limit]],
        suggested_quick_adds=_build_quick_adds(missing_items)[:quick_adds_limit],
        known_facts=known_facts,
        known_fact_keys=[item.key for item in known_facts],
        route_context=route_context,
        primary_jurisdiction="EU",
        supported_jurisdictions=["EU"],
        findings=findings,
    )


__all__ = [
    "_build_analysis_result",
    "AnalysisDepth",
]
