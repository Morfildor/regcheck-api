from __future__ import annotations

from app.domain.catalog_types import StandardCatalogRow
from app.domain.models import AnalysisResult, RiskLevel, RouteContext, StandardItem, StandardMatchAudit
from app.services.classifier import extract_traits_v1, normalize
from app.services.standards_engine import find_applicable_items_v1
from app.services.standards_engine.gating import ApplicableItems

from .facts import _build_known_facts, _missing_information
from .findings import _build_findings
from .result_builder import (
    _build_analysis_result,
    _build_standard_sections,
    _primary_legislation_by_directive,
    _safe_product_match_audit,
    _sort_standard_items,
    _standard_item_from_row,
)
from .risk import _current_risk, _future_risk, _make_risk_summary, _risk_reasons
from .routing import (
    ENGINE_VERSION,
    _analysis_depth,
    _apply_post_selection_gates_v1,
    _build_legislation_sections,
    _collect_preferred_standard_codes,
    _confidence_level,
    _contradiction_severity,
    _derive_engine_traits,
    _infer_forced_directives,
    _product_match_stage,
)
from .summary import _build_summary


def analyze_v1(
    description: str,
    category: str = "",
    directives: list[str] | None = None,
    depth: str = "standard",
) -> AnalysisResult:
    analysis_depth = _analysis_depth(depth)
    traits_data = extract_traits_v1(description=description, category=category)
    diagnostics = list(traits_data.get("diagnostics") or [])
    matched_products = set(traits_data.get("matched_products") or [])
    routing_matched_products = set(traits_data.get("routing_matched_products") or [])
    product_genres = set(traits_data.get("product_genres") or [])
    product_type = traits_data.get("product_type")
    product_match_stage = _product_match_stage(traits_data.get("product_match_stage"))
    routing_product_type = product_type if product_match_stage == "subtype" else None
    likely_standards = _collect_preferred_standard_codes(traits_data)

    trait_set = set(traits_data.get("all_traits") or [])
    confirmed_traits = set(traits_data.get("confirmed_traits") or [])
    functional_classes = set(traits_data.get("functional_classes") or [])
    trait_set, confirmed_engine_traits, extra_diag = _derive_engine_traits(description, trait_set, routing_matched_products)
    confirmed_traits.update(confirmed_engine_traits)
    diagnostics.extend(extra_diag)

    legislation_items, legislation_sections, detected_directives = _build_legislation_sections(
        traits=trait_set,
        functional_classes=functional_classes,
        product_type=routing_product_type,
        matched_products=routing_matched_products,
        product_genres=product_genres,
        confirmed_traits=confirmed_traits,
        forced_directives=directives,
    )
    inferred_directive_hints = _infer_forced_directives(
        trait_set,
        routing_matched_products,
        routing_product_type,
        confirmed_traits,
        likely_standards,
    )
    if inferred_directive_hints - set(detected_directives):
        diagnostics.append("directive_hints=" + ",".join(sorted(inferred_directive_hints - set(detected_directives))))
        legislation_items, legislation_sections, detected_directives = _build_legislation_sections(
            traits=trait_set,
            functional_classes=functional_classes,
            product_type=routing_product_type,
            matched_products=routing_matched_products,
            product_genres=product_genres,
            confirmed_traits=confirmed_traits,
            forced_directives=sorted({item for item in (directives or []) if item} | inferred_directive_hints),
        )
    legislation_by_directive = _primary_legislation_by_directive(legislation_items)
    allowed_directives = set(detected_directives)

    items: ApplicableItems = find_applicable_items_v1(
        traits=trait_set,
        directives=detected_directives,
        product_type=routing_product_type,
        matched_products=sorted(routing_matched_products),
        product_genres=sorted(product_genres),
        preferred_standard_codes=sorted(likely_standards),
        explicit_traits=set(traits_data.get("explicit_traits") or []),
        confirmed_traits=confirmed_traits,
    )
    selected_rows: list[StandardCatalogRow] = list(items["standards"]) + list(items["review_items"])
    selected_rows = _apply_post_selection_gates_v1(
        selected_rows,
        trait_set,
        routing_matched_products,
        diagnostics,
        allowed_directives,
        product_type=routing_product_type,
        confirmed_traits=confirmed_traits,
        description=description,
    )

    dedup: dict[str, StandardCatalogRow] = {}
    for row in selected_rows:
        key = str(row.get("code") or "")
        if key not in dedup or int(row.get("score", 0)) > int(dedup[key].get("score", 0)):
            dedup[key] = row

    standard_items: list[StandardItem] = []
    review_items: list[StandardItem] = []
    for row in dedup.values():
        item = _standard_item_from_row(row, legislation_by_directive, trait_set)
        if item.item_type == "review":
            review_items.append(item)
        else:
            standard_items.append(item)

    standard_items = _sort_standard_items(standard_items)
    review_items = _sort_standard_items(review_items)
    all_standard_items = _sort_standard_items(standard_items + review_items)
    current_review_items = [item for item in review_items if item.timing_status == "current"]
    missing_items = _missing_information(
        trait_set,
        routing_matched_products,
        description,
        product_type=product_type,
        product_match_stage=product_match_stage,
    )
    standard_sections = _build_standard_sections(all_standard_items)

    current_risk = _current_risk(
        product_confidence=_confidence_level(traits_data.get("product_match_confidence"), default="low"),
        contradiction_severity=_contradiction_severity(traits_data.get("contradiction_severity")),
        review_items=current_review_items,
        missing_items=missing_items,
    )
    future_risk = _future_risk(detected_directives, trait_set)
    overall_risk: RiskLevel = "LOW"
    if current_risk == "HIGH" or future_risk == "HIGH":
        overall_risk = "HIGH"
    elif current_risk == "MEDIUM" or future_risk == "MEDIUM":
        overall_risk = "MEDIUM"
    risk_reasons = _risk_reasons(
        overall_risk=overall_risk,
        current_risk=current_risk,
        future_risk=future_risk,
        traits=trait_set,
        directives=detected_directives,
        product_confidence=str(traits_data.get("product_match_confidence") or "low"),
        contradictions=traits_data.get("contradictions") or [],
        review_items=review_items,
        missing_items=missing_items,
    )
    risk_summary = _make_risk_summary(
        overall_risk=overall_risk,
        current_risk=current_risk,
        future_risk=future_risk,
        risk_reasons=risk_reasons,
    )

    summary = _build_summary(detected_directives, standard_items, review_items, trait_set, description)
    findings = _build_findings(
        depth=analysis_depth,
        legislation_items=legislation_items,
        standards=standard_items,
        review_items=review_items,
        missing_items=missing_items,
        contradictions=traits_data.get("contradictions") or [],
        contradiction_severity=_contradiction_severity(traits_data.get("contradiction_severity")),
    )
    known_facts = _build_known_facts(description)
    return _build_analysis_result(
        description=description,
        depth=analysis_depth,
        normalized_description=normalize(f"{category} {description}"),
        traits_data=traits_data,
        diagnostics=diagnostics,
        matched_products=matched_products,
        routing_matched_products=routing_matched_products,
        product_genres=product_genres,
        likely_standards=likely_standards,
        trait_set=trait_set,
        confirmed_traits=confirmed_traits,
        detected_directives=detected_directives,
        forced_directives=[item for item in dict.fromkeys(directives or []) if item],
        legislation_items=legislation_items,
        legislation_sections=legislation_sections,
        standard_items=standard_items,
        review_items=review_items,
        missing_items=missing_items,
        standard_sections=standard_sections,
        risk_reasons=risk_reasons,
        risk_summary=risk_summary,
        summary=summary,
        findings=findings,
        known_facts=known_facts,
        trait_evidence=[],
        product_match_audit=_safe_product_match_audit(traits_data, normalize(f"{category} {description}")),
        standard_match_audit=StandardMatchAudit(engine_version=ENGINE_VERSION),
        route_context=RouteContext(known_fact_keys=[item.key for item in known_facts], jurisdiction="EU"),
        overall_risk=overall_risk,
        current_risk=current_risk,
        future_risk=future_risk,
        degraded_reasons=[],
        warnings=[],
    )


__all__ = ["analyze_v1"]
