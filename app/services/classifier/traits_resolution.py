from __future__ import annotations

from typing import Any

from .scoring import SERVICE_DEPENDENT_TRAITS


def _apply_product_trait_signals(
    text: str,
    match: dict[str, Any],
    explicit_traits: set[str],
    inferred_traits: set[str],
    negations: list[str],
    state_map: dict[str, dict[str, list[str]]],
) -> tuple[set[str], set[str], set[str]]:
    from .traits import (
        _apply_explicit_trait_negations,
        _expand_related_traits,
        _record_trait_state,
        _suppress_unmentioned_product_wireless_traits,
    )

    product_match_stage = match["product_match_stage"]
    product_match_confidence = str(match.get("product_match_confidence") or "low")
    matched_aliases = [
        candidate.get("matched_alias")
        for candidate in match["product_candidates"]
        if candidate.get("matched_alias")
    ]
    product_core_traits = _suppress_unmentioned_product_wireless_traits(
        text,
        _expand_related_traits(set(match.get("product_core_traits") or set())),
        explicit_traits,
        matched_aliases,
    )
    product_default_traits = _suppress_unmentioned_product_wireless_traits(
        text,
        _expand_related_traits(set(match.get("product_default_traits") or set())),
        explicit_traits,
        matched_aliases,
    )
    product_core_traits = _apply_explicit_trait_negations(product_core_traits, negations)
    product_default_traits = _apply_explicit_trait_negations(product_default_traits, negations)
    product_genres = {item for item in (match.get("product_genres") or set()) if isinstance(item, str) and item}

    if product_match_stage == "ambiguous" and product_match_confidence == "low":
        product_core_traits = set()
        product_default_traits = set()
        product_genres = set()

    if product_core_traits:
        product_evidence = (
            f"product:{match['product_subtype']}"
            if product_match_stage == "subtype" and match.get("product_subtype")
            else f"family:{match['product_family']}"
        )
        _record_trait_state(state_map, "product_core", product_core_traits, product_evidence)
    if product_default_traits:
        product_evidence = (
            f"product_default:{match['product_subtype']}"
            if product_match_stage == "subtype" and match.get("product_subtype")
            else f"family_default:{match['product_family']}"
        )
        _record_trait_state(state_map, "product_default", product_default_traits, product_evidence)

    return product_core_traits, product_default_traits, product_genres


def _compute_confirmed_traits(
    explicit_traits: set[str],
    product_core_traits: set[str],
    product_default_traits: set[str],
    product_match_stage: str,
    product_family_confidence: str,
    product_subtype_confidence: str,
    product_candidates: list[dict[str, Any]],
) -> set[str]:
    confirmed = set(explicit_traits)
    top_candidate = product_candidates[0] if product_candidates else {}

    decisive_medium = (
        product_match_stage == "subtype"
        and product_subtype_confidence == "medium"
        and bool(top_candidate.get("matched_alias") or top_candidate.get("positive_clues"))
    )
    decisive_subtype = (
        product_match_stage == "subtype"
        and bool(
            top_candidate.get("matched_alias")
            or top_candidate.get("positive_clues")
            or top_candidate.get("family_keyword_hits")
        )
    )
    if product_family_confidence == "high":
        confirmed.update(product_core_traits - SERVICE_DEPENDENT_TRAITS)
    if product_match_stage == "subtype" and (product_subtype_confidence == "high" or decisive_medium or decisive_subtype):
        confirmed.update(product_core_traits - SERVICE_DEPENDENT_TRAITS)

    corroborated_default = {trait for trait in product_default_traits if trait in explicit_traits}
    confirmed.update(corroborated_default - SERVICE_DEPENDENT_TRAITS)

    return confirmed


def _detect_trait_contradictions(
    explicit_traits: set[str],
    text: str,
    match_contradictions: list[str],
) -> list[str]:
    from .traits import _trait_is_negated

    contradictions = list(match_contradictions)
    if "battery_powered" in explicit_traits and "mains_powered" in explicit_traits:
        contradictions.append("Both battery-powered and mains-powered signals were detected.")
    if "cloud" in explicit_traits and "local_only" in explicit_traits:
        contradictions.append("Both cloud-connected and local-only signals were detected.")
    if "professional" in explicit_traits and "household" in explicit_traits:
        contradictions.append("Both professional/commercial and household-use signals were detected.")
    if "wifi" in explicit_traits and _trait_is_negated(text, "internet") and {"cloud", "ota", "account"} & explicit_traits:
        contradictions.append("Wi-Fi is present while the text also says no internet, but cloud or OTA features were also detected.")
    return contradictions


__all__ = [
    "_apply_product_trait_signals",
    "_compute_confirmed_traits",
    "_detect_trait_contradictions",
]
