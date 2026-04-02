from __future__ import annotations

from typing import Any


def _empty_trait_state_map() -> dict[str, dict[str, list[str]]]:
    return {
        "text_explicit": {},
        "text_inferred": {},
        "product_core": {},
        "product_default": {},
        "engine_derived": {},
    }


def _record_trait_state(
    state_map: dict[str, dict[str, list[str]]],
    state: str,
    traits: set[str] | list[str],
    evidence: str,
) -> None:
    for trait in traits:
        state_map.setdefault(state, {}).setdefault(trait, [])
        if evidence not in state_map[state][trait]:
            state_map[state][trait].append(evidence)


def _trait_evidence_items(
    state_map: dict[str, dict[str, list[str]]],
    confirmed_traits: set[str],
) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    fact_basis_by_state = {
        "text_explicit": "confirmed",
        "product_core": "confirmed",
        "text_inferred": "inferred",
        "product_default": "inferred",
        "engine_derived": "inferred",
    }
    for state in ("text_explicit", "text_inferred", "product_core", "product_default", "engine_derived"):
        for trait in sorted(state_map.get(state, {})):
            items.append(
                {
                    "trait": trait,
                    "state": state,
                    "fact_basis": fact_basis_by_state[state],
                    "confirmed": trait in confirmed_traits,
                    "evidence": list(state_map[state][trait]),
                }
            )
    return items


__all__ = [
    "_empty_trait_state_map",
    "_record_trait_state",
    "_trait_evidence_items",
]
