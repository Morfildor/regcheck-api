from __future__ import annotations

import logging
from time import perf_counter

from pydantic import ValidationError

from app.core.degradation import DegradationCollector, guarded_step
from app.core.settings import get_settings
from app.domain.models import (
    AnalysisResult,
    Finding,
    KnownFactItem,
    RiskLevel,
    RiskReason,
    RiskSummary,
    ShadowDiffItem,
    StandardMatchAudit,
    StandardSection,
    DecisionTraceEntry,
)
from app.services.classifier import ENGINE_VERSION as CLASSIFIER_ENGINE_VERSION
from app.services.standards_engine import find_applicable_items
from app.services.standards_engine.contracts import ItemsAudit
from app.services.standards_v3 import StandardsSelectionResult, run_standards_policy

from .contracts import ClassifierTraitsSnapshot
from .facts import _build_known_facts, _missing_information
from .findings import _build_findings
from .legacy import analyze_v1
from .result_builder import (
    _build_analysis_result,
    _build_standard_match_audit,
    _build_standard_sections,
    _safe_product_match_audit,
    _sort_standard_items,
    _standard_item_from_row,
    _trait_evidence_from_state_map,
)
from .risk import _current_risk, _future_risk, _make_risk_summary, _risk_reasons
from .routing import (
    AnalysisDepth,
    AnalysisTrace,
    LegislationSelection,
    OVERLAY_DIRECTIVE_KEYS,
    PreparedAnalysis,
    _analysis_depth,
    _confidence_level,
    _contradiction_severity,
    _prepare_analysis,
    _route_context_summary,
    _select_legislation_routes,
    _standard_context,
)
from .summary import _build_summary


ENGINE_VERSION = CLASSIFIER_ENGINE_VERSION

logger = logging.getLogger(__name__)


def _shadow_enabled() -> bool:
    return get_settings().enable_engine_v2_shadow


def _select_standards(
    prepared: PreparedAnalysis,
    routes: LegislationSelection,
    description: str,
) -> StandardsSelectionResult:
    collector = DegradationCollector(prepared.degraded_reasons, prepared.warnings)
    context = _standard_context(
        prepared.route_traits,
        prepared.routing_matched_products,
        prepared.routing_product_type,
        prepared.confirmed_traits,
        description,
        prepared.route_plan,
    )
    prepared.diagnostics.append("scope_route=" + context.scope_route)
    if context.scope_reasons:
        prepared.diagnostics.append("scope_route_reasons=" + ";".join(context.scope_reasons))
    prepared.diagnostics.append("standard_context_tags=" + ",".join(sorted(context.context_tags)))

    current_review_items = []
    missing_items = _missing_information(
        prepared.route_traits,
        prepared.routing_matched_products,
        description,
        product_type=prepared.product_type,
        product_match_stage=prepared.product_match_stage,
        route_plan=prepared.route_plan,
    )

    standard_sections: list[StandardSection] = guarded_step(
        logger=logger,
        collector=collector,
        step="standard_sections",
        reason="standard_sections_failed",
        warning="Standards sections could not be assembled; standards remain available as a flat list.",
        fallback=[],
        operation=lambda: _build_standard_sections(
            [],
            primary_standard_code=prepared.route_plan.primary_standard_code,
            supporting_standard_codes=prepared.route_plan.supporting_standard_codes,
        ),
    )
    standards = guarded_step(
        logger=logger,
        collector=collector,
        step="standards_enrichment",
        reason="standards_enrichment_failed",
        warning="Standards enrichment failed; returning classification and legislation without standards.",
        fallback=StandardsSelectionResult(
            context=context,
            standard_items=[],
            review_items=[],
            current_review_items=current_review_items,
            missing_items=missing_items,
            standard_sections=standard_sections,
            items_audit=ItemsAudit(),
            rejections=[],
        ),
        operation=lambda: run_standards_policy(
            prepared=prepared,
            routes=routes,
            description=description,
            context=context,
            missing_items=missing_items,
            standard_sections=standard_sections,
            standard_item_from_row=_standard_item_from_row,
            sort_standard_items=_sort_standard_items,
            standards_selector=find_applicable_items,
        ),
    )
    if not standards.standard_sections and (standards.standard_items or standards.review_items):
        standards.standard_sections = _build_standard_sections(
            _sort_standard_items(
                standards.standard_items + standards.review_items,
                primary_standard_code=prepared.route_plan.primary_standard_code,
                supporting_standard_codes=prepared.route_plan.supporting_standard_codes,
            ),
            primary_standard_code=prepared.route_plan.primary_standard_code,
            supporting_standard_codes=prepared.route_plan.supporting_standard_codes,
        )
    return standards


def _compute_risk_profile(
    prepared: PreparedAnalysis,
    routes: LegislationSelection,
    standards: StandardsSelectionResult,
) -> tuple[RiskLevel, RiskLevel, RiskLevel, list[RiskReason], RiskSummary]:
    current_risk = _current_risk(
        product_confidence=_confidence_level(prepared.traits_data.product_match_confidence, default="low"),
        contradiction_severity=_contradiction_severity(prepared.traits_data.contradiction_severity),
        review_items=standards.current_review_items,
        missing_items=standards.missing_items,
    )
    future_risk = _future_risk(routes.detected_directives, prepared.route_traits)
    overall_risk: RiskLevel = "LOW"
    if current_risk == "HIGH" or future_risk == "HIGH":
        overall_risk = "HIGH"
    elif current_risk == "MEDIUM" or future_risk == "MEDIUM":
        overall_risk = "MEDIUM"

    risk_reasons = _risk_reasons(
        overall_risk=overall_risk,
        current_risk=current_risk,
        future_risk=future_risk,
        traits=prepared.route_traits,
        directives=routes.detected_directives,
        product_confidence=prepared.traits_data.product_match_confidence,
        contradictions=list(prepared.traits_data.contradictions),
        review_items=standards.review_items,
        missing_items=standards.missing_items,
    )
    return (
        overall_risk,
        current_risk,
        future_risk,
        risk_reasons,
        _make_risk_summary(
            overall_risk=overall_risk,
            current_risk=current_risk,
            future_risk=future_risk,
            risk_reasons=risk_reasons,
        ),
    )

def _shadow_diff(v1: AnalysisResult, v2: AnalysisResult) -> list[ShadowDiffItem]:
    v1_traits = set(v1.confirmed_traits)
    v2_traits = set(v2.confirmed_traits)
    v1_standards = {item.code for item in v1.standards}
    v2_standards = {item.code for item in v2.standards}
    trait_evidence = {item.trait for item in v2.trait_evidence if item.confirmed}
    audited_standard_codes = {item.code for item in v2.standard_match_audit.selected}
    audited_standard_codes.update(item.code for item in v2.standard_match_audit.review)

    diff: list[ShadowDiffItem] = []
    for trait in sorted(v2_traits - v1_traits):
        diff.append(ShadowDiffItem(kind="trait", key=trait, has_evidence=trait in trait_evidence))
    for code in sorted(v2_standards - v1_standards):
        diff.append(ShadowDiffItem(kind="standard", key=code, has_evidence=code in audited_standard_codes))
    return diff

def _maybe_attach_shadow_diff(
    result: AnalysisResult,
    *,
    description: str,
    category: str,
    directives: list[str] | None,
    depth: AnalysisDepth,
    prepared: PreparedAnalysis,
) -> AnalysisResult:
    if not _shadow_enabled():
        return result

    collector = DegradationCollector(prepared.degraded_reasons, prepared.warnings)
    shadow_diff = guarded_step(
        logger=logger,
        collector=collector,
        step="shadow_diff",
        reason="shadow_diff_failed",
        warning="Shadow comparison could not be computed; the primary analysis remains available.",
        fallback=None,
        operation=lambda: _shadow_diff(
            analyze_v1(description=description, category=category, directives=directives, depth=depth),
            result,
        ),
        handled_exceptions=(TypeError, ValueError, RuntimeError, ValidationError),
    )
    if shadow_diff is None:
        result.degraded_mode = True
        result.degraded_reasons = prepared.degraded_reasons
        result.warnings = prepared.warnings
        return result
    result.analysis_audit.shadow_diff = shadow_diff

    return result


def _trace_items(values: list[str] | set[str], limit: int = 6) -> list[str]:
    ordered = [item for item in values if isinstance(item, str) and item]
    return ordered[:limit]


def _build_decision_trace(
    prepared: PreparedAnalysis,
    routes: LegislationSelection,
    standards: StandardsSelectionResult,
    known_facts: list[KnownFactItem],
) -> list[DecisionTraceEntry]:
    traits_data: ClassifierTraitsSnapshot = prepared.traits_data
    product_type = traits_data.product_type
    product_family = traits_data.product_family
    product_stage = traits_data.product_match_stage
    product_confidence = traits_data.product_match_confidence
    candidate_ids = [item.id for item in traits_data.product_candidates if item.id]
    explicit_traits = list(traits_data.explicit_traits)
    assumed_traits = sorted(set(prepared.route_traits) - set(prepared.confirmed_traits))
    suppressed_traits: list[str] = []
    for diagnostic in prepared.diagnostics:
        if diagnostic.startswith("route_trait_suppressed="):
            suppressed_traits.extend([part for part in diagnostic.split("=", 1)[1].split(",") if part])

    route_items = [f"{item.directive_key}:{item.bucket}" for item in routes.items if item.directive_key != "OTHER"]
    if "radio" in prepared.route_traits and "RED" in routes.detected_directives:
        route_items.append("LVD/EMC merged into RED Art. 3.1(a)/(b)")
    if prepared.route_plan.primary_standard_code:
        route_items.append("primary_standard=" + prepared.route_plan.primary_standard_code)

    selected_standards = [
        f"{item.code} ({item.directive}, {item.category})"
        for item in standards.standard_items[:5]
    ]
    if standards.review_items:
        selected_standards.extend(
            f"review:{item.code} ({item.directive}, {item.category})"
            for item in standards.review_items[:2]
        )
    rejected_rows = [
        f"{row.code or ''}: {row.reason.strip()}"
        for row in standards.rejections[:5]
        if row.code
    ]
    missing_items = [
        f"{item.key} ({item.importance})"
        for item in standards.missing_items
        if item.importance == "high"
    ] or [item.key for item in standards.missing_items[:4]]

    classification_summary = (
        f"Resolved to {product_type} ({product_stage}, {product_confidence} confidence)."
        if product_type and product_stage == "subtype"
        else f"Tentative classification remains {product_stage} ({product_confidence} confidence)."
    )
    assumption_summary = (
        "Safe assumptions remain in use for routing."
        if assumed_traits or suppressed_traits
        else "No additional routing assumptions were needed."
    )
    rejection_summary = (
        "Some candidate standards or routes were intentionally rejected to keep the output coherent."
        if rejected_rows or suppressed_traits
        else "No material route or standard rejections were needed."
    )

    return [
        DecisionTraceEntry(
            step="classification",
            summary=classification_summary,
            items=_trace_items(
                [
                    *(["product_type=" + product_type] if product_type else []),
                    *(["product_family=" + product_family] if product_family else []),
                    "match_stage=" + product_stage,
                    "match_confidence=" + product_confidence,
                    *(["candidates=" + ",".join(candidate_ids[:3])] if candidate_ids else []),
                ]
            ),
        ),
        DecisionTraceEntry(
            step="traits",
            summary="Confirmed traits and explicit facts that shaped routing.",
            items=_trace_items(
                [
                    *(["explicit=" + ",".join(explicit_traits[:6])] if explicit_traits else []),
                    *(["confirmed=" + ",".join(sorted(prepared.confirmed_traits)[:8])] if prepared.confirmed_traits else []),
                    *(["known_facts=" + ",".join(item.key for item in known_facts[:4])] if known_facts else []),
                ]
            ),
        ),
        DecisionTraceEntry(
            step="assumptions",
            summary=assumption_summary,
            items=_trace_items(
                [
                    *(["assumed=" + ",".join(assumed_traits[:8])] if assumed_traits else []),
                    *(["suppressed=" + ",".join(sorted(set(suppressed_traits))[:8])] if suppressed_traits else []),
                ]
            ),
        ),
        DecisionTraceEntry(
            step="missing_facts",
            summary="Missing facts are limited to route-changing questions.",
            items=_trace_items(missing_items),
        ),
        DecisionTraceEntry(
            step="legislation",
            summary="Selected legislation routes after route separation and overlays.",
            items=_trace_items(route_items),
        ),
        DecisionTraceEntry(
            step="standards",
            summary="Primary and supporting standards are ordered ahead of secondary routes.",
            items=_trace_items(selected_standards),
        ),
        DecisionTraceEntry(
            step="rejections",
            summary=rejection_summary,
            items=_trace_items(rejected_rows or [f"suppressed_traits={','.join(sorted(set(suppressed_traits))[:8])}"] if suppressed_traits else []),
        ),
    ]


def analyze(
    description: str,
    category: str = "",
    directives: list[str] | None = None,
    depth: str = "standard",
    trace: AnalysisTrace | None = None,
) -> AnalysisResult:
    analysis_depth = _analysis_depth(depth)
    stage_started = perf_counter()
    prepared = _prepare_analysis(description, category, analysis_depth)
    collector = DegradationCollector(prepared.degraded_reasons, prepared.warnings)
    if trace is not None:
        trace.record_stage("classification", stage_started)

    stage_started = perf_counter()
    routes = _select_legislation_routes(prepared, directives)
    if trace is not None:
        trace.record_stage("legislation_routing", stage_started)

    stage_started = perf_counter()
    standards = _select_standards(prepared, routes, description)
    if trace is not None:
        trace.record_stage("standards_selection", stage_started)

    overall_risk, current_risk, future_risk, risk_reasons, risk_summary = _compute_risk_profile(prepared, routes, standards)

    stage_started = perf_counter()
    summary = guarded_step(
        logger=logger,
        collector=collector,
        step="summary",
        reason="summary_failed",
        warning="The narrative summary could not be assembled; returning a compact fallback summary.",
        fallback=(
            f"{len(routes.detected_directives)} legislation routes, {len(standards.standard_items)} standards, "
            f"and {len(standards.review_items)} review items identified."
        ),
        operation=lambda: _build_summary(
            routes.detected_directives,
            standards.standard_items,
            standards.review_items,
            prepared.route_traits,
            description,
        ),
    )

    findings: list[Finding] = guarded_step(
        logger=logger,
        collector=collector,
        step="findings",
        reason="findings_failed",
        warning="Actionable findings could not be assembled; the route output remains available.",
        fallback=[],
        operation=lambda: _build_findings(
            depth=analysis_depth,
            legislation_items=routes.items,
            standards=standards.standard_items,
            review_items=standards.review_items,
            missing_items=standards.missing_items,
            contradictions=list(prepared.traits_data.contradictions),
            contradiction_severity=_contradiction_severity(prepared.traits_data.contradiction_severity),
        ),
    )

    known_facts: list[KnownFactItem] = guarded_step(
        logger=logger,
        collector=collector,
        step="known_facts",
        reason="known_facts_failed",
        warning="Known-fact extraction could not be completed; the core analysis remains available.",
        fallback=[],
        operation=lambda: _build_known_facts(description),
    )

    trait_evidence = _trait_evidence_from_state_map(prepared.raw_state_map, prepared.confirmed_traits)
    product_match_audit = _safe_product_match_audit(prepared.traits_data, prepared.normalized_description)
    rejected_audit_rows = [item.model_dump() for item in standards.items_audit.rejected]
    selected_audit_rows = [item.model_dump() for item in standards.items_audit.selected]
    review_audit_rows = [item.model_dump() for item in standards.items_audit.review]
    audited_rejected_codes = {str(row.get("code") or "") for row in rejected_audit_rows}
    rejected_audit_rows.extend(
        {
            "code": row.code,
            "title": row.title or row.code,
            "outcome": "rejected",
            "score": 0,
            "confidence": "low",
            "fact_basis": "inferred",
            "selection_group": None,
            "selection_priority": 0,
            "keyword_hits": [],
            "reason": row.reason,
        }
        for row in standards.rejections
        if (row.code or "") not in audited_rejected_codes
    )
    standard_match_audit = guarded_step(
        logger=logger,
        collector=collector,
        step="standard_match_audit",
        reason="standard_match_audit_failed",
        warning="Standard audit details could not be assembled; returning the selected routes without full audit detail.",
        fallback=StandardMatchAudit(
            engine_version=ENGINE_VERSION,
            context_tags=sorted(standards.context.context_tags),
        ),
        operation=lambda: _build_standard_match_audit(
            {
                "selected": selected_audit_rows
                or [
                    {
                        "code": item.code,
                        "title": item.title,
                        "outcome": "selected",
                        "score": item.score,
                        "confidence": item.confidence,
                        "fact_basis": item.fact_basis,
                        "selection_group": item.selection_group,
                        "selection_priority": item.selection_priority,
                        "keyword_hits": item.keyword_hits,
                        "reason": item.reason,
                    }
                    for item in standards.standard_items
                ],
                "review": review_audit_rows
                or [
                    {
                        "code": item.code,
                        "title": item.title,
                        "outcome": "review",
                        "score": item.score,
                        "confidence": item.confidence,
                        "fact_basis": item.fact_basis,
                        "selection_group": item.selection_group,
                        "selection_priority": item.selection_priority,
                        "keyword_hits": item.keyword_hits,
                        "reason": item.reason,
                    }
                    for item in standards.review_items
                ],
                "rejected": rejected_audit_rows,
            },
            standards.context.context_tags,
        ),
        handled_exceptions=(ValidationError, TypeError, ValueError, RuntimeError),
    )
    decision_trace = _build_decision_trace(prepared, routes, standards, known_facts)

    result = _build_analysis_result(
        description=description,
        depth=analysis_depth,
        normalized_description=prepared.normalized_description,
        traits_data=prepared.traits_data,
        diagnostics=prepared.diagnostics,
        matched_products=prepared.matched_products,
        routing_matched_products=prepared.routing_matched_products,
        product_genres=prepared.product_genres,
        likely_standards=prepared.likely_standards,
        trait_set=prepared.trait_set,
        confirmed_traits=prepared.confirmed_traits,
        detected_directives=routes.detected_directives,
        forced_directives=routes.forced_directives,
        legislation_items=routes.items,
        legislation_sections=routes.sections,
        standard_items=standards.standard_items,
        review_items=standards.review_items,
        missing_items=standards.missing_items,
        standard_sections=standards.standard_sections,
        risk_reasons=risk_reasons,
        risk_summary=risk_summary,
        summary=summary,
        findings=findings,
        known_facts=known_facts,
        trait_evidence=trait_evidence,
        product_match_audit=product_match_audit,
        standard_match_audit=standard_match_audit,
        route_context=_route_context_summary(
            standards.context,
            known_facts,
            [directive for directive in routes.detected_directives if directive in OVERLAY_DIRECTIVE_KEYS],
        ),
        decision_trace=decision_trace,
        overall_risk=overall_risk,
        current_risk=current_risk,
        future_risk=future_risk,
        degraded_reasons=prepared.degraded_reasons,
        warnings=prepared.warnings,
    )
    if trace is not None:
        trace.record_stage("response_assembly", stage_started)

    return _maybe_attach_shadow_diff(
        result,
        description=description,
        category=category,
        directives=directives,
        depth=analysis_depth,
        prepared=prepared,
    )


__all__ = [
    "AnalysisTrace",
    "ENGINE_VERSION",
    "StandardsSelectionResult",
    "analyze",
]
