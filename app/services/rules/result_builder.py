from __future__ import annotations

from collections.abc import Mapping
from collections import defaultdict
import logging
from typing import Any, Literal

from pydantic import ValidationError

from app.core.degradation import DegradationCollector, guarded_step
from app.core.runtime_state import API_VERSION
from app.domain.catalog_types import StandardCatalogRow
from app.domain.models import (
    AnalysisAudit,
    AnalysisResult,
    AnalysisStats,
    ConfidencePanel,
    DecisionTraceEntry,
    FactBasis,
    Finding,
    HeroSummary,
    InputGapsPanel,
    KnowledgeBaseMeta,
    KnownFactItem,
    LegislationItem,
    LegislationSection,
    MissingInformationItem,
    ProductMatchAudit,
    RiskLevel,
    RiskReason,
    RiskSummary,
    RouteContext,
    StandardAuditItem,
    StandardItem,
    StandardMatchAudit,
    StandardSection,
    StandardSectionItem,
    TraitEvidenceItem,
    TraitEvidenceState,
)
from app.services.knowledge_base import load_meta

from .facts import _build_quick_adds, _top_actions_from_missing
from .routing import (
    DIRECTIVE_TITLES,
    ENGINE_VERSION,
    _confidence_from_score,
    _confidence_level,
    _contradiction_severity,
    _directive_rank,
    _product_match_stage,
    _route_condition_hint,
    _route_title,
    _standard_applicability_state,
    _standard_primary_directive,
)
from .summary import _classification_summary, _primary_uncertainties


AnalysisDepth = Literal["quick", "standard", "deep"]
logger = logging.getLogger(__name__)
StandardRowLike = StandardCatalogRow | Mapping[str, Any]


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

    # When a standard is surfaced through RED, do not also create stray LVD/EMC
    # sections from its multi-directive metadata. RED Art. 3.1(a)/(b) covers those
    # branches for radio products.
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
        route_keys = _standard_section_route_keys(item)
        for key in route_keys:
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


def _standard_item_from_row(
    row: StandardRowLike,
    legislation_by_directive: dict[str, LegislationItem],
    traits: set[str],
) -> StandardItem:
    primary_directive = _standard_primary_directive(row, traits)
    legislation = legislation_by_directive.get(primary_directive)
    timing_status = legislation.timing_status if legislation else "current"

    raw_directives = [str(item) for item in (row.get("directives") or []) if isinstance(item, str)]
    # Determine whether this standard originally belongs to LVD or EMC.
    # Check the raw KB directives list (not gating-modified) and the current
    # directive field (which may be gating-modified from LVD/EMC).
    native_dir = raw_directives[0] if raw_directives else None
    gate_dir = str(row.get("directive") or "")
    original_is_lvd_emc = native_dir in {"LVD", "EMC"} or gate_dir in {"LVD", "EMC"}
    # For radio products, standards remapped from LVD/EMC under RED must have
    # their directives list updated so standard sections group them under RED.
    if "radio" in traits and primary_directive == "RED" and original_is_lvd_emc:
        effective_directives: list[str] = ["RED"]
    else:
        effective_directives = raw_directives or [primary_directive]
        if "radio" not in traits:
            effective_directives = [directive for directive in effective_directives if directive != "RED"]
        if primary_directive and primary_directive not in effective_directives:
            effective_directives.append(primary_directive)

    return StandardItem(
        code=str(row["code"]),
        title=str(row["title"]),
        directive=primary_directive,
        directives=effective_directives,
        legislation_key=row.get("legislation_key"),
        category=str(row.get("category", "other")),
        confidence=_confidence_from_score(int(row.get("score", 0))),
        item_type=row.get("item_type", "standard"),
        match_basis=row.get("match_basis", "traits"),
        fact_basis=row.get("fact_basis", "confirmed"),
        score=int(row.get("score", 0)),
        reason=row.get("reason"),
        notes=row.get("notes"),
        regime_bucket=legislation.bucket if legislation else None,
        timing_status=timing_status,
        matched_traits_all=row.get("matched_traits_all", []),
        matched_traits_any=row.get("matched_traits_any", []),
        missing_required_traits=row.get("missing_required_traits", []),
        excluded_by_traits=row.get("excluded_by_traits", []),
        applies_if_products=row.get("applies_if_products", []),
        exclude_if_products=row.get("exclude_if_products", []),
        product_match_type=row.get("product_match_type"),
        standard_family=row.get("standard_family"),
        is_harmonized=row.get("is_harmonized"),
        harmonized_under=row.get("harmonized_under"),
        harmonization_status=row.get("harmonization_status", "unknown"),
        harmonized_reference=row.get("harmonized_reference"),
        version=row.get("version"),
        dated_version=row.get("dated_version"),
        supersedes=row.get("supersedes"),
        test_focus=row.get("test_focus", []),
        evidence_hint=row.get("evidence_hint", []),
        keywords=row.get("keywords", []),
        keyword_hits=row.get("keyword_hits", []),
        selection_group=row.get("selection_group"),
        selection_priority=int(row.get("selection_priority", 0)),
        required_fact_basis=row.get("required_fact_basis", "inferred"),
        jurisdiction=str(row.get("region") or "EU"),
        applicability_state=_standard_applicability_state(row, timing_status),
        applicability_hint=_route_condition_hint(row),
    )


def _normalize_trait_state_map(raw: Any) -> dict[str, dict[str, list[str]]]:
    states: dict[str, dict[str, list[str]]] = {
        "text_explicit": {},
        "text_inferred": {},
        "product_core": {},
        "product_default": {},
        "engine_derived": {},
    }
    if not isinstance(raw, dict):
        return states

    for state in states:
        value = raw.get(state, {})
        if not isinstance(value, dict):
            continue
        for trait, evidence in value.items():
            if not isinstance(trait, str):
                continue
            if isinstance(evidence, list):
                states[state][trait] = [item for item in evidence if isinstance(item, str)]
            elif isinstance(evidence, str):
                states[state][trait] = [evidence]
    return states


def _trait_evidence_from_state_map(
    state_map: dict[str, dict[str, list[str]]],
    confirmed_traits: set[str],
) -> list[TraitEvidenceItem]:
    states: tuple[TraitEvidenceState, ...] = (
        "text_explicit",
        "text_inferred",
        "product_core",
        "product_default",
        "engine_derived",
    )
    fact_basis_by_state: dict[TraitEvidenceState, FactBasis] = {
        "text_explicit": "confirmed",
        "product_core": "confirmed",
        "text_inferred": "inferred",
        "product_default": "inferred",
        "engine_derived": "inferred",
    }
    items: list[TraitEvidenceItem] = []
    for state in states:
        for trait in sorted(state_map.get(state, {})):
            items.append(
                TraitEvidenceItem(
                    trait=trait,
                    state=state,
                    fact_basis=fact_basis_by_state[state],
                    confirmed=trait in confirmed_traits,
                    evidence=state_map[state][trait],
                )
            )
    return items

def _build_standard_match_audit(items_audit: dict[str, Any], context_tags: set[str]) -> StandardMatchAudit:
    return StandardMatchAudit(
        engine_version=ENGINE_VERSION,
        context_tags=sorted(context_tags),
        selected=[StandardAuditItem.model_validate(item) for item in items_audit.get("selected", [])],
        review=[StandardAuditItem.model_validate(item) for item in items_audit.get("review", [])],
        rejected=[StandardAuditItem.model_validate(item) for item in items_audit.get("rejected", [])],
    )


def _safe_product_match_audit(traits_data: dict[str, Any], normalized_description: str) -> ProductMatchAudit:
    raw = traits_data.get("product_match_audit") or traits_data.get("audit")
    if isinstance(raw, dict):
        try:
            return ProductMatchAudit.model_validate(raw)
        except (ValidationError, TypeError, ValueError):
            logger.exception("analysis_degraded step=product_match_audit")
    return ProductMatchAudit(engine_version=ENGINE_VERSION, normalized_text=normalized_description)

def _safe_knowledge_base_meta(
    degraded_reasons: list[str],
    warnings: list[str],
) -> KnowledgeBaseMeta:
    collector = DegradationCollector(degraded_reasons, warnings)
    return guarded_step(
        logger=logger,
        collector=collector,
        step="knowledge_base_meta",
        reason="knowledge_base_meta_unavailable",
        warning="Catalog metadata could not be loaded during result assembly; core analysis remains available.",
        fallback=KnowledgeBaseMeta(),
        operation=lambda: KnowledgeBaseMeta(**load_meta()),
        handled_exceptions=(ValidationError, TypeError, ValueError, RuntimeError),
    )


def _build_analysis_result(
    *,
    description: str,
    depth: AnalysisDepth,
    normalized_description: str,
    traits_data: dict[str, Any],
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
    product_match_stage = _product_match_stage(traits_data.get("product_match_stage"))
    product_match_confidence = _confidence_level(traits_data.get("product_match_confidence"), default="low")
    classification_confidence_below_threshold = product_match_confidence == "low"
    classification_is_ambiguous = classification_confidence_below_threshold or product_match_stage != "subtype"
    contradictions = list(traits_data.get("contradictions") or [])
    contradiction_severity = _contradiction_severity(traits_data.get("contradiction_severity"))
    inferred_traits = sorted(set(traits_data.get("inferred_traits") or []) | (trait_set - set(traits_data.get("explicit_traits") or [])))
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
        product_family=traits_data.get("product_family"),
        product_subtype=traits_data.get("product_subtype"),
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
        product_type=traits_data.get("product_type"),
        product_family=traits_data.get("product_family"),
        product_family_confidence=traits_data.get("product_family_confidence", "low"),
        product_subtype=traits_data.get("product_subtype"),
        product_subtype_confidence=traits_data.get("product_subtype_confidence", "low"),
        product_match_stage=product_match_stage,
        product_match_confidence=product_match_confidence,
        classification_is_ambiguous=classification_is_ambiguous,
        classification_confidence_below_threshold=classification_confidence_below_threshold,
        classification_summary=_classification_summary(
            product_type=traits_data.get("product_type"),
            product_family=traits_data.get("product_family"),
            product_subtype=traits_data.get("product_subtype"),
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
        product_candidates=traits_data.get("product_candidates") or [],
        functional_classes=traits_data.get("functional_classes") or [],
        confirmed_functional_classes=traits_data.get("confirmed_functional_classes") or [],
        explicit_traits=traits_data.get("explicit_traits") or [],
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
            product_family=traits_data.get("product_family"),
            product_genres=sorted(product_genres),
            product_subtype=traits_data.get("product_subtype"),
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
    "AnalysisDepth",
    "_build_analysis_result",
    "_build_standard_match_audit",
    "_build_standard_sections",
    "_normalize_trait_state_map",
    "_primary_legislation_by_directive",
    "_safe_knowledge_base_meta",
    "_safe_product_match_audit",
    "_sort_standard_items",
    "_standard_item_from_row",
    "_trait_evidence_from_state_map",
]
