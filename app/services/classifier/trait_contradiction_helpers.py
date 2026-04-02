from __future__ import annotations

from .trait_negation_helpers import _trait_is_negated


def _detect_trait_contradictions(
    explicit_traits: set[str],
    text: str,
    match_contradictions: list[str],
) -> list[str]:
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


__all__ = ["_detect_trait_contradictions"]
