from __future__ import annotations

from typing import Any

from app.services.knowledge_base import get_knowledge_base_snapshot

from .matching import _hierarchical_product_match_v2
from .matching_legacy import _hierarchical_product_match
from .trait_inference_helpers import _expand_related_traits, _infer_baseline_traits, _infer_connected_traits
from .trait_negation_helpers import (
    _apply_explicit_trait_negations,
    _negation_suppression_items,
    _suppress_unmentioned_product_wireless_traits,
    _trait_is_negated,
)
from .trait_signal_helpers import _add_regex_trait, _collect_text_trait_signals, _has_cue_group
from .trait_state_helpers import _record_trait_state, _trait_evidence_items
from .normalization import normalize
from .scoring import ENGINE_VERSION, _contradiction_severity
from .traits_resolution import _apply_product_trait_signals, _compute_confirmed_traits, _detect_trait_contradictions


TRAIT_IDS_CACHE: set[str] | None = None


def extract_traits_v2(description: str, category: str = "") -> dict:
    text = normalize(f"{category} {description}")
    explicit_traits, inferred_traits, state_map, negations = _collect_text_trait_signals(text)
    diagnostics: list[str] = [f"normalized_text={text}"]

    match = _hierarchical_product_match_v2(text, explicit_traits | inferred_traits)
    match.audit.negations = list(negations)
    match.audit.negation_suppressions.extend(_negation_suppression_items(negations))

    weak_ambiguous_guess = (
        match.product_match_stage == "ambiguous"
        and match.product_match_confidence == "low"
        and bool(match.product_candidates)
        and bool(match.subtype_candidates)
        and not bool(match.subtype_candidates[0].matched_alias or match.subtype_candidates[0].family_keyword_hits)
    )
    if weak_ambiguous_guess:
        match.clear_weak_guess("suppressed weak ambiguous guess because no alias or family keyword support was present")
        diagnostics.append("product_guess_suppressed=weak_ambiguous_match")

    explicit_traits = _apply_explicit_trait_negations(explicit_traits, negations)
    inferred_traits = _apply_explicit_trait_negations(inferred_traits, negations)

    product_core_traits, product_default_traits, product_genres = _apply_product_trait_signals(
        text,
        match,
        explicit_traits,
        inferred_traits,
        negations,
        state_map,
    )
    functional_classes = set(match.functional_classes)
    confirmed_functional_classes = set(match.confirmed_functional_classes)

    confirmed_traits = _compute_confirmed_traits(
        explicit_traits,
        product_core_traits,
        product_default_traits,
        match,
    )

    engine_derived_traits = _expand_related_traits(
        _infer_connected_traits(
            text,
            explicit_traits | inferred_traits | product_core_traits | product_default_traits,
            has_cue_group=_has_cue_group,
        )
    ) - explicit_traits - inferred_traits
    engine_derived_traits = _apply_explicit_trait_negations(engine_derived_traits, negations)
    if engine_derived_traits:
        inferred_traits |= engine_derived_traits
        _record_trait_state(state_map, "engine_derived", engine_derived_traits, "engine:connectivity_inference")

    diagnostics.extend(match.diagnostics)
    if match.product_candidates:
        diagnostics.append(f"product_winner={match.product_candidates[0].id}")
        diagnostics.append(f"product_alias={match.product_candidates[0].matched_alias or ''}")
    else:
        diagnostics.append("product_winner=none")

    contradictions = _detect_trait_contradictions(explicit_traits, text, match.contradictions)

    known_traits = _known_trait_ids()
    explicit_traits = {trait for trait in _expand_related_traits(explicit_traits) if trait in known_traits}
    if "battery_powered" in explicit_traits and "mains_powered" not in explicit_traits:
        product_default_traits = product_default_traits - {"mains_power_likely"}
    product_core_traits = _apply_explicit_trait_negations(product_core_traits, negations)
    product_default_traits = _apply_explicit_trait_negations(product_default_traits, negations)
    inferred_traits = _apply_explicit_trait_negations(
        inferred_traits | product_core_traits | product_default_traits,
        negations,
    )
    inferred_traits = {trait for trait in _expand_related_traits(inferred_traits) if trait in known_traits}
    confirmed_traits = _apply_explicit_trait_negations(confirmed_traits, negations)
    confirmed_traits = {trait for trait in _expand_related_traits(confirmed_traits) if trait in known_traits}

    diagnostics.append("matched_products=" + ",".join(match.matched_products))
    diagnostics.append("routing_matched_products=" + ",".join(match.routing_matched_products))
    diagnostics.append("confirmed_products=" + ",".join(match.confirmed_products))
    diagnostics.append("product_genres=" + ",".join(sorted(product_genres)))
    diagnostics.append("preferred_standard_codes=" + ",".join(match.preferred_standard_codes))
    diagnostics.append("explicit_traits=" + ",".join(sorted(explicit_traits)))
    diagnostics.append("confirmed_traits=" + ",".join(sorted(confirmed_traits)))
    diagnostics.append("inferred_traits=" + ",".join(sorted(inferred_traits)))
    diagnostics.append("negations=" + ",".join(negations))
    diagnostics.append("contradiction_severity=" + _contradiction_severity(contradictions))

    product_candidates_payload = [candidate.to_dict() for candidate in match.product_candidates]
    return {
        "product_type": match.product_type,
        "product_family": match.product_family,
        "product_family_confidence": match.product_family_confidence,
        "product_subtype": match.product_subtype,
        "product_subtype_confidence": match.product_subtype_confidence,
        "product_match_stage": match.product_match_stage,
        "matched_products": match.matched_products,
        "routing_matched_products": match.routing_matched_products,
        "confirmed_products": match.confirmed_products,
        "product_genres": sorted(product_genres),
        "preferred_standard_codes": match.preferred_standard_codes,
        "product_match_confidence": match.product_match_confidence,
        "product_candidates": product_candidates_payload,
        "functional_classes": sorted(functional_classes),
        "confirmed_functional_classes": sorted(confirmed_functional_classes),
        "explicit_traits": sorted(explicit_traits),
        "confirmed_traits": sorted(confirmed_traits),
        "inferred_traits": sorted((explicit_traits | inferred_traits) - confirmed_traits),
        "all_traits": sorted(explicit_traits | inferred_traits),
        "text_explicit_traits": sorted(explicit_traits),
        "text_inferred_traits": sorted({trait for trait in state_map["text_inferred"] if trait in known_traits}),
        "product_core_traits": sorted(product_core_traits & known_traits),
        "product_default_traits": sorted(product_default_traits & known_traits),
        "contradictions": contradictions,
        "contradiction_severity": _contradiction_severity(contradictions),
        "diagnostics": diagnostics,
        "trait_state_map": state_map,
        "trait_evidence": _trait_evidence_items(state_map, confirmed_traits),
        "product_match_audit": match.audit.to_dict(),
        "engine_version": ENGINE_VERSION,
    }


def extract_traits_v1(description: str, category: str = "") -> dict:
    """Legacy compatibility path kept for older tests and payload comparisons."""
    text = normalize(f"{category} {description}")
    explicit_traits: set[str] = set()
    inferred_traits: set[str] = set()
    confirmed_traits: set[str] = set()
    functional_classes: set[str] = set()
    confirmed_functional_classes: set[str] = set()
    contradictions: list[str] = []
    diagnostics: list[str] = []
    negations = sorted(trait for trait in _classifier_negations() if _trait_is_negated(text, trait))

    _add_regex_trait(text, explicit_traits)
    explicit_traits = _expand_related_traits(explicit_traits)
    explicit_traits = _apply_explicit_trait_negations(explicit_traits, negations)
    inferred_traits.update(_infer_baseline_traits(text, explicit_traits, has_cue_group=_has_cue_group))
    inferred_traits = _apply_explicit_trait_negations(inferred_traits, negations)
    diagnostics.append(f"normalized_text={text}")

    match = _hierarchical_product_match(text, explicit_traits | inferred_traits)
    product_type = match["product_type"]
    product_match_confidence = match["product_match_confidence"]
    product_candidates = match["product_candidates"]
    matched_products = match["matched_products"]
    routing_matched_products = match["routing_matched_products"]
    confirmed_products = match["confirmed_products"]
    preferred_standard_codes = match["preferred_standard_codes"]
    product_family = match["product_family"]
    product_family_confidence = match["product_family_confidence"]
    product_subtype = match["product_subtype"]
    product_subtype_confidence = match["product_subtype_confidence"]
    product_match_stage = match["product_match_stage"]
    matched_aliases = [candidate.get("matched_alias") for candidate in product_candidates if candidate.get("matched_alias")]

    inferred_traits.update(
        _suppress_unmentioned_product_wireless_traits(
            text,
            _expand_related_traits(set(match["family_traits"])),
            explicit_traits,
            matched_aliases,
            expand_related_traits=_expand_related_traits,
        )
    )
    inferred_traits = _apply_explicit_trait_negations(inferred_traits, negations)
    inferred_traits.update(
        _suppress_unmentioned_product_wireless_traits(
            text,
            _expand_related_traits(set(match["subtype_traits"])),
            explicit_traits,
            matched_aliases,
            expand_related_traits=_expand_related_traits,
        )
    )
    inferred_traits = _apply_explicit_trait_negations(inferred_traits, negations)
    functional_classes.update(match["functional_classes"])
    confirmed_functional_classes.update(match["confirmed_functional_classes"])
    if product_family_confidence == "high":
        confirmed_traits.update(
            _suppress_unmentioned_product_wireless_traits(
                text,
                _expand_related_traits(set(match["family_traits"])),
                explicit_traits,
                matched_aliases,
                expand_related_traits=_expand_related_traits,
            )
        )
        confirmed_traits = _apply_explicit_trait_negations(confirmed_traits, negations)
    if product_match_stage == "subtype" and product_subtype_confidence == "high":
        confirmed_traits.update(
            _suppress_unmentioned_product_wireless_traits(
                text,
                _expand_related_traits(set(match["subtype_traits"])),
                explicit_traits,
                matched_aliases,
                expand_related_traits=_expand_related_traits,
            )
        )
        confirmed_traits = _apply_explicit_trait_negations(confirmed_traits, negations)

    diagnostics.extend(match["diagnostics"])
    if product_candidates:
        diagnostics.append(f"product_winner={product_candidates[0]['id']}")
        diagnostics.append(f"product_alias={product_candidates[0].get('matched_alias') or ''}")
    else:
        diagnostics.append("product_winner=none")

    contradictions.extend(match["contradictions"])
    contradictions = _detect_trait_contradictions(explicit_traits, text, contradictions)

    known_traits = _known_trait_ids()
    explicit_traits = _apply_explicit_trait_negations(_expand_related_traits(explicit_traits), negations)
    inferred_traits = _apply_explicit_trait_negations(_expand_related_traits(inferred_traits), negations)
    confirmed_traits = _apply_explicit_trait_negations(_expand_related_traits(confirmed_traits), negations)
    explicit_traits = {t for t in explicit_traits if t in known_traits}
    inferred_traits = {t for t in inferred_traits if t in known_traits}
    confirmed_traits = {t for t in (confirmed_traits | explicit_traits) if t in known_traits}

    diagnostics.append("matched_products=" + ",".join(matched_products))
    diagnostics.append("routing_matched_products=" + ",".join(routing_matched_products))
    diagnostics.append("confirmed_products=" + ",".join(confirmed_products))
    diagnostics.append("preferred_standard_codes=" + ",".join(preferred_standard_codes))
    diagnostics.append("explicit_traits=" + ",".join(sorted(explicit_traits)))
    diagnostics.append("confirmed_traits=" + ",".join(sorted(confirmed_traits)))
    diagnostics.append("inferred_traits=" + ",".join(sorted(inferred_traits)))
    diagnostics.append("negations=" + ",".join(negations))
    diagnostics.append("contradiction_severity=" + _contradiction_severity(contradictions))

    return {
        "product_type": product_type,
        "product_family": product_family,
        "product_family_confidence": product_family_confidence,
        "product_subtype": product_subtype,
        "product_subtype_confidence": product_subtype_confidence,
        "product_match_stage": product_match_stage,
        "matched_products": matched_products,
        "routing_matched_products": routing_matched_products,
        "confirmed_products": confirmed_products,
        "preferred_standard_codes": preferred_standard_codes,
        "product_match_confidence": product_match_confidence,
        "product_candidates": product_candidates,
        "functional_classes": sorted(functional_classes),
        "confirmed_functional_classes": sorted(confirmed_functional_classes),
        "explicit_traits": sorted(explicit_traits),
        "confirmed_traits": sorted(confirmed_traits),
        "inferred_traits": sorted(inferred_traits),
        "all_traits": sorted(explicit_traits | inferred_traits),
        "contradictions": contradictions,
        "contradiction_severity": _contradiction_severity(contradictions),
        "diagnostics": diagnostics,
    }


def extract_traits(description: str, category: str = "") -> dict:
    """Primary classifier entrypoint. New routing and catalog work should use v2."""
    return extract_traits_v2(description=description, category=category)


def _classifier_negations() -> dict[str, tuple[Any, ...]]:
    snapshot = get_knowledge_base_snapshot().classifier_signal_runtime
    if snapshot is None:
        from .signal_config import get_classifier_signal_snapshot

        snapshot = get_classifier_signal_snapshot()
    return snapshot.negations


def _known_trait_ids() -> set[str]:
    global TRAIT_IDS_CACHE
    if TRAIT_IDS_CACHE is None:
        TRAIT_IDS_CACHE = {row["id"] for row in get_knowledge_base_snapshot().traits}
    return TRAIT_IDS_CACHE


def reset_classifier_cache() -> None:
    global TRAIT_IDS_CACHE
    TRAIT_IDS_CACHE = None
    from .matching import reset_matching_cache
    from .scoring import reset_scoring_cache

    reset_matching_cache()
    reset_scoring_cache()


__all__ = [
    "TRAIT_IDS_CACHE",
    "_expand_related_traits",
    "_known_trait_ids",
    "extract_traits",
    "extract_traits_v1",
    "extract_traits_v2",
    "reset_classifier_cache",
]
