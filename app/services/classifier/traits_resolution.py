from __future__ import annotations

from .models import ClassifierMatchOutcome, ProductImpliedTraitDecision
from .scoring import SERVICE_DEPENDENT_TRAITS
from .trait_contradiction_helpers import _detect_trait_contradictions as _build_trait_contradictions
from .trait_inference_helpers import _expand_related_traits
from .trait_negation_helpers import _apply_explicit_trait_negations, _suppress_unmentioned_product_wireless_traits
from .trait_state_helpers import _record_trait_state


def _apply_product_trait_signals(
    text: str,
    match: ClassifierMatchOutcome,
    explicit_traits: set[str],
    inferred_traits: set[str],
    negations: list[str],
    state_map: dict[str, dict[str, list[str]]],
) -> tuple[set[str], set[str], set[str]]:
    matched_aliases = [candidate.matched_alias for candidate in match.product_candidates if candidate.matched_alias]

    def _accept_product_traits(traits: set[str], *, source: str) -> tuple[set[str], set[str], str | None]:
        expanded = _expand_related_traits(set(traits))
        if not expanded:
            return set(), set(), None

        wireless_filtered = _suppress_unmentioned_product_wireless_traits(
            text,
            expanded,
            explicit_traits,
            matched_aliases,
            expand_related_traits=_expand_related_traits,
        )
        negation_filtered = _apply_explicit_trait_negations(wireless_filtered, negations)

        suppressed = expanded - negation_filtered
        reasons: list[str] = []
        if wireless_filtered != expanded:
            reasons.append("suppressed wireless defaults without wireless text support")
        if negation_filtered != wireless_filtered:
            reasons.append("suppressed traits that conflicted with explicit negations")
        return negation_filtered, suppressed, "; ".join(reasons) or None

    product_core_traits, suppressed_core_traits, core_reason = _accept_product_traits(
        set(match.product_core_traits),
        source="product_core",
    )
    product_default_traits, suppressed_default_traits, default_reason = _accept_product_traits(
        set(match.product_default_traits),
        source="product_default",
    )
    product_genres = set(match.product_genres)

    if match.product_match_stage == "ambiguous" and match.product_match_confidence == "low":
        suppressed_core_traits |= product_core_traits
        suppressed_default_traits |= product_default_traits
        product_core_traits = set()
        product_default_traits = set()
        product_genres = set()
        core_reason = core_reason or "suppressed product-implied traits because the product match remained weak and ambiguous"
        default_reason = default_reason or "suppressed product-implied traits because the product match remained weak and ambiguous"

    if product_core_traits:
        product_evidence = (
            f"product:{match.product_subtype}"
            if match.product_match_stage == "subtype" and match.product_subtype
            else f"family:{match.product_family}"
        )
        _record_trait_state(state_map, "product_core", product_core_traits, product_evidence)
    if product_default_traits:
        product_evidence = (
            f"product_default:{match.product_subtype}"
            if match.product_match_stage == "subtype" and match.product_subtype
            else f"family_default:{match.product_family}"
        )
        _record_trait_state(state_map, "product_default", product_default_traits, product_evidence)

    match.audit.product_implied_traits.extend(
        [
            ProductImpliedTraitDecision(
                source="product_core",
                accepted_traits=tuple(sorted(product_core_traits)),
                suppressed_traits=tuple(sorted(suppressed_core_traits)),
                reason=core_reason,
            ),
            ProductImpliedTraitDecision(
                source="product_default",
                accepted_traits=tuple(sorted(product_default_traits)),
                suppressed_traits=tuple(sorted(suppressed_default_traits)),
                reason=default_reason,
            ),
        ]
    )

    return product_core_traits, product_default_traits, product_genres


def _compute_confirmed_traits(
    explicit_traits: set[str],
    product_core_traits: set[str],
    product_default_traits: set[str],
    match: ClassifierMatchOutcome,
) -> set[str]:
    confirmed = set(explicit_traits)
    top_candidate = match.subtype_candidates[0] if match.subtype_candidates else None

    decisive_medium = (
        match.product_match_stage == "subtype"
        and match.product_subtype_confidence == "medium"
        and bool(top_candidate and (top_candidate.matched_alias or top_candidate.positive_clues))
    )
    decisive_subtype = (
        match.product_match_stage == "subtype"
        and bool(
            top_candidate
            and (
                top_candidate.matched_alias
                or top_candidate.positive_clues
                or top_candidate.family_keyword_hits
            )
        )
    )
    if match.product_family_confidence == "high":
        confirmed.update(product_core_traits - SERVICE_DEPENDENT_TRAITS)
    if match.product_match_stage == "subtype" and (
        match.product_subtype_confidence == "high" or decisive_medium or decisive_subtype
    ):
        confirmed.update(product_core_traits - SERVICE_DEPENDENT_TRAITS)

    corroborated_default = {trait for trait in product_default_traits if trait in explicit_traits}
    confirmed.update(corroborated_default - SERVICE_DEPENDENT_TRAITS)

    return confirmed


def _detect_trait_contradictions(
    explicit_traits: set[str],
    text: str,
    match_contradictions: list[str],
) -> list[str]:
    return _build_trait_contradictions(explicit_traits, text, match_contradictions)


__all__ = [
    "_apply_product_trait_signals",
    "_compute_confirmed_traits",
    "_detect_trait_contradictions",
]
