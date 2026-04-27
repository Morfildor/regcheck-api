from __future__ import annotations

from typing import Any

from .models import SignalSuppression
from .scoring import RADIO_TRAITS
from .signal_config import get_classifier_signal_snapshot


def _signal_snapshot():
    return get_classifier_signal_snapshot()


def _has_any_compiled(text: str, patterns: tuple[Any, ...] | list[Any]) -> bool:
    return any(pattern.search(text) for pattern in patterns)


def _trait_is_negated(text: str, trait: str) -> bool:
    return _has_any_compiled(text, _signal_snapshot().negations.get(trait, ()))


def _strip_wireless_protected_phrases(text: str) -> str:
    protected = _signal_snapshot().wireless_protected_phrases
    if not protected:
        return text
    cleaned = text
    for pattern in protected:
        cleaned = pattern.sub(" ", cleaned)
    return cleaned


def _has_wireless_mention(text: str, matched_aliases: list[str] | None = None) -> bool:
    snapshot = _signal_snapshot()
    candidates = [_strip_wireless_protected_phrases(text)]
    candidates.extend(
        _strip_wireless_protected_phrases(alias)
        for alias in (matched_aliases or [])
        if isinstance(alias, str) and alias
    )
    patterns = snapshot.wireless_mentions
    return any(_has_any_compiled(candidate, patterns) for candidate in candidates)


def _suppress_unmentioned_product_wireless_traits(
    text: str,
    traits: set[str],
    explicit_traits: set[str],
    matched_aliases: list[str] | None,
    *,
    expand_related_traits,
) -> set[str]:
    explicit_radio_traits = explicit_traits & RADIO_TRAITS
    if explicit_radio_traits:
        allowed = expand_related_traits(set(explicit_radio_traits))
        return set(traits) - ((RADIO_TRAITS | {"radio"}) - allowed)
    if "radio" in explicit_traits:
        return set(traits)
    if _has_wireless_mention(text, matched_aliases):
        return set(traits)
    return set(traits) - (RADIO_TRAITS | {"radio"})


def _suppressed_traits_for_negations(negations: list[str]) -> set[str]:
    suppressed: set[str] = set()
    suppressions = _signal_snapshot().negated_trait_suppressions
    for trait in negations:
        suppressed.update(suppressions.get(trait, frozenset({trait})))
    return suppressed


def _negation_suppression_items(negations: list[str]) -> list[SignalSuppression]:
    items: list[SignalSuppression] = []
    suppressions = _signal_snapshot().negated_trait_suppressions
    for trait in negations:
        suppressed_traits = tuple(sorted(suppressions.get(trait, frozenset({trait}))))
        items.append(
            SignalSuppression(
                source="text_negation",
                reason=f"explicit text negation for '{trait}'",
                traits=suppressed_traits,
            )
        )
    return items


def _apply_explicit_trait_negations(traits: set[str], negations: list[str]) -> set[str]:
    if not traits or not negations:
        return set(traits)
    return set(traits) - _suppressed_traits_for_negations(negations)


__all__ = [
    "_apply_explicit_trait_negations",
    "_has_any_compiled",
    "_has_wireless_mention",
    "_negation_suppression_items",
    "_signal_snapshot",
    "_suppress_unmentioned_product_wireless_traits",
    "_suppressed_traits_for_negations",
    "_trait_is_negated",
]
