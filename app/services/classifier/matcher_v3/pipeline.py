from __future__ import annotations

from dataclasses import replace

from app.domain.engine_models import ConfidenceLevel
from app.services.classifier.models import ClassifierMatchAudit, ClassifierMatchOutcome, FamilySeedCandidate

from .contracts import CandidateEvidence, MatcherPhaseSnapshot


def _common_strings(rows: list, field: str) -> list[str]:
    if not rows:
        return []
    common = set(getattr(rows[0], field))
    for row in rows[1:]:
        common &= set(getattr(row, field))
    return sorted(common)


def _common_sets(rows: list, field: str) -> set[str]:
    if not rows:
        return set()
    common = set(getattr(rows[0], field))
    for row in rows[1:]:
        common &= set(getattr(row, field))
    return common


def run_matcher_v3(text: str, signal_traits: set[str]) -> ClassifierMatchOutcome:
    # Imported locally so matching.py can delegate here.
    from app.services.classifier.matching import (
        ENGINE_VERSION,
        _apply_domain_disambiguation,
        _build_empty_match_outcome,
        _build_matching_context,
        _build_product_candidate_v2,
        _candidate_confidence_v2,
        _companion_device_decision,
        _confidence_limiter,
        _family_level_limiter,
        _filter_candidates,
        _hybrid_detection_reason,
        _negative_guard_activations,
        _normalized_text_summary,
        _product_matching_snapshot,
        _rejected_confusable_candidates,
        _rerank_candidates,
        _resolve_stage,
        _shortlist_basis,
        _shortlist_product_matchers_v2,
        _top_unique,
        _why_not_reasons,
        parse_product_roles,
    )

    phase_snapshot = MatcherPhaseSnapshot()
    role_parse = parse_product_roles(text)
    context = _build_matching_context(text, signal_traits, role_parse)
    shortlisted_matchers, shortlist_scoring, shortlist_reasons = _shortlist_product_matchers_v2(
        text,
        signal_traits,
        include_reasons=True,
    )
    phase_snapshot.retrieval = [
        CandidateEvidence(
            matcher=matcher,
            shortlist_score=shortlist_scoring.get(matcher.id, 0),
            shortlist_reasons=shortlist_reasons.get(matcher.id, ()),
        )
        for matcher in shortlisted_matchers
    ]

    generated = []
    for evidence in phase_snapshot.retrieval:
        candidate = _build_product_candidate_v2(
            context,
            evidence.matcher,
            evidence.shortlist_score,
            evidence.shortlist_reasons,
        )
        phase_snapshot.candidate_features.append(
            CandidateEvidence(
                matcher=evidence.matcher,
                shortlist_score=evidence.shortlist_score,
                shortlist_reasons=evidence.shortlist_reasons,
                candidate=candidate,
            )
        )
        if candidate is not None:
            generated.append(candidate)
    phase_snapshot.scoring = list(generated)

    filtered_candidates, filtered_out = _filter_candidates(generated, context)
    disambiguated_candidates, domain_role_reasons, confusable_domain_reasons = _apply_domain_disambiguation(
        filtered_candidates,
        context,
    )
    candidates, rerank_reasons, accessory_reasons, generic_penalties, group_confusable_reasons = _rerank_candidates(
        disambiguated_candidates,
        context,
    )
    phase_snapshot.confusable_rerank = list(candidates)
    confusable_domain_reasons = confusable_domain_reasons + group_confusable_reasons

    if not candidates:
        outcome = _build_empty_match_outcome(text, role_parse)
        outcome.audit.shortlist_basis = _shortlist_basis(shortlist_scoring, shortlist_reasons)
        outcome.audit.filtered_out = filtered_out[:8]
        outcome.audit.final_match_reason = "no viable candidates remained after explicit matcher_v3 phases"
        return outcome

    family_map: dict[str, FamilySeedCandidate] = {}
    for candidate in candidates:
        existing = family_map.get(candidate.family)
        if existing is None or candidate.score > existing.score:
            family_map[candidate.family] = FamilySeedCandidate(candidate.family, candidate, candidate.score)

    ordered_family_candidates = sorted(family_map.values(), key=lambda row: (-row.score, row.family))
    family_candidates = [
        replace(
            row,
            confidence=_candidate_confidence_v2(
                row,
                ordered_family_candidates[idx + 1] if idx + 1 < len(ordered_family_candidates) else None,
            ),
        )
        for idx, row in enumerate(ordered_family_candidates)
    ]
    top_family = family_candidates[0]
    next_family = family_candidates[1] if len(family_candidates) > 1 else None
    family_rows = [row for row in candidates if row.family == top_family.family]
    top_subtype = family_rows[0]
    next_subtype = family_rows[1] if len(family_rows) > 1 else None
    family_confidence: ConfidenceLevel = top_family.confidence
    subtype_confidence: ConfidenceLevel = _candidate_confidence_v2(top_subtype, next_subtype)
    family_level_limiter = _family_level_limiter(context, top_subtype, next_subtype)
    confidence_limiter = _confidence_limiter(context, top_subtype, next_subtype)
    family_stage, stage_reason, contradictions, ambiguity_reason = _resolve_stage(
        top_family=top_family,
        next_family=next_family,
        top_subtype=top_subtype,
        next_subtype=next_subtype,
        family_confidence=family_confidence,
        subtype_confidence=subtype_confidence,
        family_level_limiter=family_level_limiter,
    )
    phase_snapshot.stop_policy_reason = family_level_limiter or confidence_limiter or ambiguity_reason or stage_reason

    subtype_band = [row for row in family_rows if top_subtype.score - row.score <= 12][:3]
    if family_stage == "family" and next_subtype and next_subtype.id not in {row.id for row in subtype_band}:
        subtype_band = [top_subtype, next_subtype]

    common_classes = _common_strings(subtype_band, "functional_classes")
    common_standards = _common_strings(subtype_band, "likely_standards")
    common_core_traits = _common_sets(subtype_band, "core_traits")
    common_default_traits = _common_sets(subtype_band, "default_traits")
    common_genres = _common_sets(subtype_band, "genres")

    product_core_traits = set(top_subtype.core_traits)
    product_default_traits = set(top_subtype.default_traits)
    product_genres = set(top_subtype.genres)
    functional_classes = set(top_subtype.functional_classes)
    confirmed_functional_classes: set[str] = set()
    preferred_standard_codes: list[str] = []
    confirmed_products: list[str] = []
    matched_products = [row.id for row in subtype_band]
    routing_matched_products: list[str] = []
    product_subtype = top_subtype.id if family_stage == "subtype" else None
    product_type = top_subtype.id
    product_match_confidence: ConfidenceLevel = subtype_confidence

    if family_stage == "ambiguous" and next_family is not None:
        matched_products = [top_family.id, next_family.id]
        functional_classes = set()
        product_core_traits = set()
        product_default_traits = set()
        product_genres = set()
        product_match_confidence = "low"
    elif family_stage == "family":
        functional_classes = set(common_classes)
        product_core_traits = set(common_core_traits)
        product_default_traits = set(common_default_traits)
        product_genres = set(common_genres)
        preferred_standard_codes = common_standards
        product_match_confidence = "medium" if family_confidence == "high" else family_confidence
        if family_confidence == "high":
            confirmed_functional_classes.update(common_classes)
    else:
        routing_matched_products = [top_subtype.id]
        preferred_standard_codes = list(top_subtype.likely_standards)
        if subtype_confidence == "high":
            confirmed_products = [top_subtype.id]
            confirmed_functional_classes.update(top_subtype.functional_classes)
        elif common_classes:
            confirmed_functional_classes.update(common_classes)

    if confidence_limiter and product_match_confidence == "high":
        product_match_confidence = "medium"
    public_rows = family_rows[:5]
    close_family_competition = bool(next_family and top_family.score - next_family.score < 8 and next_family.family != top_family.family)
    if close_family_competition and next_family is not None and next_family.representative not in public_rows:
        public_rows = public_rows + [next_family.representative]

    product_candidates = [
        candidate.to_public_candidate(
            confidence=_candidate_confidence_v2(candidate, public_rows[idx + 1] if idx + 1 < len(public_rows) else None),
            family_score=family_map[candidate.family].score if candidate.family in family_map else candidate.score,
        )
        for idx, candidate in enumerate(public_rows[:5])
    ]
    audit_rows = subtype_band if family_stage == "family" else [top_subtype]
    alias_hits = _top_unique([hit for row in audit_rows for hit in row.alias_hits], limit=5)
    family_keyword_hits = _top_unique([hit for row in audit_rows for hit in row.family_keyword_hits], limit=5)
    clue_hits = _top_unique([hit for row in audit_rows for hit in row.positive_clues], limit=5)
    strongest_negative_clues = _top_unique([hit for row in audit_rows for hit in row.negative_clues], limit=5)
    top_family_audit = [row.to_audit_candidate() for row in family_candidates[:3]]
    top_subtype_audit = [
        row.to_audit_candidate(
            confidence=_candidate_confidence_v2(row, candidates[idx + 1] if idx + 1 < len(candidates) else None),
            why_not_reasons=() if row.id == top_subtype.id else _why_not_reasons(row, top_subtype, family_level_limiter=family_level_limiter),
            final_stop_reason=family_level_limiter if row.id == top_subtype.id else None,
        )
        for idx, row in enumerate(candidates[:5])
    ]

    all_domain_reasons = [*domain_role_reasons, *confusable_domain_reasons]
    diagnostics = [
        f"product_shortlist_candidates={len(shortlisted_matchers)}",
        f"product_shortlist_catalog={len(_product_matching_snapshot().products)}",
        f"product_family={top_family.family}",
        f"product_family_confidence={family_confidence}",
        f"product_subtype_candidate={top_subtype.id}",
        f"product_subtype_confidence={subtype_confidence}",
        f"product_match_stage={family_stage}",
        "matcher_v3_phases=retrieval,candidate_features,scoring,confusable_rerank,stop_policy,audit_assembly",
    ]
    if top_subtype.boundary_tags:
        diagnostics.append("product_boundary_tags=" + ",".join(sorted(top_subtype.boundary_tags)))
    if family_level_limiter:
        diagnostics.append(f"product_family_limiter={family_level_limiter}")
    if confidence_limiter:
        diagnostics.append(f"product_confidence_limiter={confidence_limiter}")

    audit = ClassifierMatchAudit(
        engine_version=ENGINE_VERSION,
        normalized_text=text,
        normalized_text_summary=_normalized_text_summary(text),
        resolved_head_candidate=role_parse.primary_product_head or role_parse.primary_product_phrase,
        companion_device_decision=_companion_device_decision(context, top_subtype, all_domain_reasons),
        hybrid_detection_reason=_hybrid_detection_reason(context, all_domain_reasons),
        domain_disambiguation_reason=domain_role_reasons[0] if domain_role_reasons else None,
        retrieval_basis=list(top_subtype.reasons[:8]),
        shortlist_basis=_shortlist_basis(shortlist_scoring, shortlist_reasons),
        filtered_out=filtered_out[:8],
        alias_hits=alias_hits,
        matched_aliases=alias_hits,
        family_keyword_hits=family_keyword_hits,
        clue_hits=clue_hits,
        strongest_positive_clues=clue_hits,
        strongest_negative_clues=strongest_negative_clues,
        rerank_reasons=_top_unique(rerank_reasons, limit=8),
        domain_role_disambiguation_reasons=_top_unique(domain_role_reasons, limit=8),
        confusable_domain_reasons=_top_unique(confusable_domain_reasons, limit=8),
        negative_guard_activations=_negative_guard_activations(
            top_subtype,
            all_domain_reasons,
            accessory_reasons,
            generic_penalties,
            strongest_negative_clues,
        ),
        accessory_gate_reasons=_top_unique(accessory_reasons, limit=8),
        generic_alias_penalties=_top_unique(generic_penalties, limit=8),
        top_family_candidates=top_family_audit,
        top_subtype_candidates=top_subtype_audit,
        role_parse=role_parse.to_audit(),
        final_match_stage=family_stage,
        final_match_reason=stage_reason,
        ambiguity_reason=ambiguity_reason,
        family_level_limiter=family_level_limiter,
        confidence_limiter=confidence_limiter,
        subtype_stop_reason=family_level_limiter or confidence_limiter or ambiguity_reason,
        rejected_confusable_candidates=_rejected_confusable_candidates(
            candidates[1:],
            top_subtype,
            family_level_limiter=family_level_limiter,
        ),
    )

    return ClassifierMatchOutcome(
        product_family=top_family.family,
        product_family_confidence=family_confidence,
        product_subtype=product_subtype,
        product_subtype_confidence=subtype_confidence,
        product_match_stage=family_stage,
        product_type=product_type,
        product_match_confidence=product_match_confidence,
        product_candidates=product_candidates,
        matched_products=matched_products,
        routing_matched_products=routing_matched_products,
        confirmed_products=confirmed_products,
        product_core_traits=product_core_traits,
        product_default_traits=product_default_traits,
        product_genres=product_genres,
        preferred_standard_codes=preferred_standard_codes,
        functional_classes=functional_classes,
        confirmed_functional_classes=confirmed_functional_classes,
        diagnostics=diagnostics,
        contradictions=contradictions,
        audit=audit,
        family_seed_candidates=family_candidates,
        subtype_candidates=candidates,
    )
