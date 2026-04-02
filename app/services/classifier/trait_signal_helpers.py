from __future__ import annotations

from .trait_inference_helpers import _expand_related_traits, _infer_baseline_traits, _infer_connected_traits
from .trait_negation_helpers import _has_any_compiled, _signal_snapshot, _trait_is_negated
from .trait_state_helpers import _empty_trait_state_map, _record_trait_state


def _has_cue_group(text: str, cue_name: str) -> bool:
    return _has_any_compiled(text, _signal_snapshot().compiled_cue_groups.get(cue_name, ()))


def _add_regex_trait(text: str, explicit_traits: set[str]) -> None:
    for trait, patterns in _signal_snapshot().trait_patterns.items():
        if _trait_is_negated(text, trait):
            continue
        if _has_any_compiled(text, patterns):
            explicit_traits.add(trait)

    if {"wifi", "bluetooth", "zigbee", "thread", "matter", "nfc", "cellular", "dect", "gsm", "uwb", "lora", "lorawan", "sigfox"} & explicit_traits:
        explicit_traits.add("radio")
    if "wifi_5ghz" in explicit_traits:
        explicit_traits.add("wifi")

    if "cloud" in explicit_traits and "local_only" not in explicit_traits:
        explicit_traits.add("internet")
    if "ota" in explicit_traits and not _trait_is_negated(text, "internet"):
        explicit_traits.add("internet")
    if ("account" in explicit_traits or "authentication" in explicit_traits) and (
        {"cloud", "ota", "app_control", "wifi", "cellular", "internet"} & explicit_traits
    ):
        explicit_traits.add("internet")
    if "wearable" in explicit_traits:
        explicit_traits.add("body_worn_or_applied")
    if "biometric" in explicit_traits:
        explicit_traits.update({"health_related", "personal_data_likely"})
    if "health_data" in explicit_traits:
        explicit_traits.update({"health_related", "personal_data_likely"})
    if "wellness" in explicit_traits:
        explicit_traits.add("health_related")
    if "medical_adjacent" in explicit_traits:
        explicit_traits.update({"health_related", "possible_medical_boundary"})
    if {"medical_context", "possible_medical_boundary", "medical_claims"} & explicit_traits:
        explicit_traits.add("health_related")
    if {"home_security", "access_control", "locking"} & explicit_traits:
        explicit_traits.add("security_or_barrier")
    if "surveillance" in explicit_traits:
        explicit_traits.update({"camera_surveillance", "security_or_barrier"})
    if {"account", "authentication", "camera", "microphone", "location", "biometric"} & explicit_traits:
        explicit_traits.add("personal_data_likely")
    if "health_related" in explicit_traits and (
        {"app_control", "cloud", "account", "authentication", "data_storage", "wifi", "bluetooth", "internet"} & explicit_traits
    ):
        explicit_traits.add("personal_data_likely")


def _collect_text_trait_signals(text: str) -> tuple[set[str], set[str], dict[str, dict[str, list[str]]], list[str]]:
    explicit_direct: set[str] = set()
    negations = sorted(trait for trait in _signal_snapshot().negations if _trait_is_negated(text, trait))
    state_map = _empty_trait_state_map()

    for trait, patterns in _signal_snapshot().trait_patterns.items():
        if trait in negations:
            continue
        if _has_any_compiled(text, patterns):
            explicit_direct.add(trait)
            _record_trait_state(state_map, "text_explicit", {trait}, f"text:{trait}")

    explicit_traits = _expand_related_traits(explicit_direct)
    derived_explicit = explicit_traits - explicit_direct
    if derived_explicit:
        _record_trait_state(state_map, "text_explicit", derived_explicit, "text:derived")

    inferred_traits = _expand_related_traits(
        _infer_baseline_traits(text, explicit_traits, has_cue_group=_has_cue_group)
    )
    if inferred_traits:
        _record_trait_state(state_map, "text_inferred", inferred_traits, "text:baseline_inference")

    connected_inferred = (
        _expand_related_traits(
            _infer_connected_traits(text, explicit_traits | inferred_traits, has_cue_group=_has_cue_group)
        )
        - explicit_traits
        - inferred_traits
    )
    if connected_inferred:
        inferred_traits |= connected_inferred
        _record_trait_state(state_map, "text_inferred", connected_inferred, "text:connected_inference")

    return explicit_traits, inferred_traits, state_map, negations


__all__ = [
    "_add_regex_trait",
    "_collect_text_trait_signals",
    "_has_cue_group",
]
