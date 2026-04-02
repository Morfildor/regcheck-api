from __future__ import annotations

from app.domain.models import FactBasis, TraitEvidenceItem, TraitEvidenceState

from .contracts import NormalizedTraitStateMap


def _normalize_trait_state_map(raw: object) -> NormalizedTraitStateMap:
    states: NormalizedTraitStateMap = {
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
    state_map: NormalizedTraitStateMap,
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


__all__ = [
    "_normalize_trait_state_map",
    "_trait_evidence_from_state_map",
]
