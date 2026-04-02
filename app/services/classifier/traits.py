from __future__ import annotations

from typing import Any

from app.services.knowledge_base import get_knowledge_base_snapshot

from .matching import _hierarchical_product_match, _hierarchical_product_match_v2
from .models import SignalSuppression
from .normalization import normalize
from .scoring import (
    ELECTRONIC_SIGNAL_TRAITS,
    ENGINE_VERSION,
    POWER_TRAITS,
    RADIO_TRAITS,
    _contradiction_severity,
)
from .signal_config import get_classifier_signal_snapshot
from .traits_resolution import _apply_product_trait_signals, _compute_confirmed_traits, _detect_trait_contradictions


TRAIT_IDS_CACHE: set[str] | None = None


def _signal_snapshot():
    return get_classifier_signal_snapshot()


def _has_any_compiled(text: str, patterns: tuple[Any, ...] | list[Any]) -> bool:
    return any(pattern.search(text) for pattern in patterns)


def _trait_is_negated(text: str, trait: str) -> bool:
    return _has_any_compiled(text, _signal_snapshot().negations.get(trait, ()))


def _has_cue_group(text: str, cue_name: str) -> bool:
    return _has_any_compiled(text, _signal_snapshot().compiled_cue_groups.get(cue_name, ()))


def _add_regex_trait(text: str, explicit_traits: set[str]) -> None:
    for trait, patterns in _signal_snapshot().trait_patterns.items():
        if _trait_is_negated(text, trait):
            continue
        if _has_any_compiled(text, patterns):
            explicit_traits.add(trait)

    if RADIO_TRAITS & explicit_traits:
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


def _infer_baseline_traits(text: str, explicit_traits: set[str]) -> set[str]:
    inferred: set[str] = set()

    electrical_signals = POWER_TRAITS | {
        "av_ict",
        "heating",
        "motorized",
        "radio",
        "camera",
        "display",
        "microphone",
        "speaker",
    }
    electronic_signals = ELECTRONIC_SIGNAL_TRAITS | {"radio", "electronic"}

    if (electrical_signals & explicit_traits) or _has_cue_group(text, "electrical"):
        inferred.add("electrical")
    if (electronic_signals & explicit_traits) or _has_cue_group(text, "electronic"):
        inferred.add("electronic")
    if "electronic" in inferred and "electrical" not in (explicit_traits | inferred):
        inferred.add("electrical")

    if "wifi" in explicit_traits and {"cloud", "ota"} & explicit_traits:
        inferred.add("internet")
    if "cellular" in explicit_traits:
        inferred.add("internet")
    if "battery_powered" in explicit_traits and "portable" not in explicit_traits:
        inferred.add("portable")
    if {"rechargeable", "removable_battery", "lithium_ion_battery", "energy_storage"} & explicit_traits:
        inferred.update({"battery_powered", "electrical"})
    if "food_contact" in explicit_traits and "consumer" not in explicit_traits:
        inferred.add("consumer")
    if "wearable" in explicit_traits and "body_worn_or_applied" not in explicit_traits:
        inferred.add("body_worn_or_applied")
    if "biometric" in explicit_traits and "health_related" not in explicit_traits:
        inferred.add("health_related")
    if {"health_data", "wellness"} & explicit_traits:
        inferred.add("health_related")
    if "medical_adjacent" in explicit_traits:
        inferred.add("possible_medical_boundary")
    if "health_related" in explicit_traits and (
        {"app_control", "cloud", "account", "authentication", "data_storage", "wifi", "bluetooth", "internet"} & explicit_traits
    ):
        inferred.add("personal_data_likely")

    return inferred


def _infer_connected_traits(text: str, signal_traits: set[str]) -> set[str]:
    inferred: set[str] = set()

    local_only = "local_only" in signal_traits or _has_cue_group(text, "local_only")
    smartish = _has_cue_group(text, "smart_connected")
    consumerish = bool({"consumer", "household", "personal_care", "wearable", "pet_use"} & signal_traits) or _has_cue_group(
        text,
        "consumerish",
    )
    voiceish = "voice_assistant" in signal_traits

    if voiceish:
        inferred.add("app_control")

    if "subscription_dependency" in signal_traits:
        inferred.add("monetary_transaction")
    if "offline_capable" in signal_traits:
        inferred.add("local_only")
    if "account_required" in signal_traits:
        inferred.add("account")
    if "cloud_dependent" in signal_traits:
        inferred.update({"cloud", "internet", "internet_connected"})

    if local_only:
        if {"wifi", "bluetooth", "zigbee", "thread", "matter", "cellular"} & signal_traits:
            inferred.add("radio")
        return inferred

    if "ota" in signal_traits:
        inferred.update({"internet", "internet_connected"})

    if smartish or voiceish:
        inferred.add("app_control")

    if {"cloud", "account", "authentication", "remote_management", "subscription_dependency"} & signal_traits:
        inferred.update({"internet", "internet_connected"})
        if {"cloud", "remote_management", "subscription_dependency"} & signal_traits and consumerish:
            inferred.add("cloud")

    if "cloud" in signal_traits:
        inferred.update({"internet", "internet_connected"})

    if {"wifi", "cloud", "internet", "ota"} & (signal_traits | inferred):
        inferred.add("internet_connected")
    if {"account", "authentication"} & (signal_traits | inferred):
        inferred.add("personal_data_likely")

    return inferred


def _has_wireless_mention(text: str, matched_aliases: list[str] | None = None) -> bool:
    candidates = [text]
    candidates.extend(alias for alias in (matched_aliases or []) if isinstance(alias, str) and alias)
    patterns = _signal_snapshot().wireless_mentions
    return any(_has_any_compiled(candidate, patterns) for candidate in candidates)


def _suppress_unmentioned_product_wireless_traits(
    text: str,
    traits: set[str],
    explicit_traits: set[str],
    matched_aliases: list[str] | None = None,
) -> set[str]:
    explicit_radio_traits = explicit_traits & RADIO_TRAITS
    if explicit_radio_traits:
        allowed = _expand_related_traits(set(explicit_radio_traits))
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


def _expand_related_traits(traits: set[str]) -> set[str]:
    expanded = set(traits)

    if expanded & RADIO_TRAITS:
        expanded.add("radio")
    if expanded & {"router_role", "access_point_role", "repeater_role", "gateway_role"}:
        expanded.update({"av_ict", "electronic", "electrical"})
    if "wearable" in expanded:
        expanded.add("body_worn_or_applied")
    if expanded & {"body_contact", "oral_contact"}:
        expanded.add("body_worn_or_applied")
    if "oral_contact" in expanded:
        expanded.add("personal_care")
    if expanded & {"wifi_5ghz", "wifi_6", "wifi_7", "tri_band_wifi", "mesh_network_node", "wpa3"}:
        expanded.add("wifi")
    if expanded & {"wifi_6", "wifi_7", "tri_band_wifi"}:
        expanded.add("wifi_5ghz")
    if expanded & {"gsm", "lte_m", "5g_nr"}:
        expanded.add("cellular")
    if "lorawan" in expanded:
        expanded.add("lora")
    if "luminaire" in expanded:
        expanded.add("lighting")
    if expanded & {"uv_emitting", "infrared_emitting", "laser"}:
        expanded.update({"optical_emission", "photobiological_relevance"})
    if expanded & {"lighting", "optical_emission"}:
        expanded.update({"electrical", "photobiological_relevance"})
    if expanded & {"display_touchscreen", "e_ink_display", "hdr_display", "high_refresh_display"}:
        expanded.add("display")
    if "privacy_switch" in expanded:
        expanded.update({"microphone", "personal_data_likely"})
    if "biometric" in expanded:
        expanded.update({"health_related", "personal_data_likely"})
    if "health_data" in expanded:
        expanded.update({"health_related", "personal_data_likely"})
    if expanded & {"wellness", "medical_adjacent"}:
        expanded.add("health_related")
    if "medical_adjacent" in expanded:
        expanded.add("possible_medical_boundary")
    if expanded & {"medical_context", "medical_claims", "possible_medical_boundary"}:
        expanded.add("health_related")
    if expanded & {"home_security", "access_control", "locking"}:
        expanded.add("security_or_barrier")
    if "surveillance" in expanded:
        expanded.update({"camera_surveillance", "security_or_barrier"})
    if expanded & {"parental_controls", "subscription_dependency"}:
        expanded.add("account")
    if "account_required" in expanded:
        expanded.add("account")
    if "subscription_dependency" in expanded:
        expanded.add("monetary_transaction")
    if "offline_capable" in expanded:
        expanded.add("local_only")
    if "cloud_dependent" in expanded:
        expanded.update({"cloud", "internet", "internet_connected"})
    if "matter_bridge" in expanded:
        expanded.add("matter")
    if expanded & {"internet", "internet_connected"}:
        expanded.update({"internet", "internet_connected"})
    if "health_related" in expanded and (
        {"app_control", "cloud", "account", "authentication", "data_storage", "wifi", "bluetooth", "internet", "location"} & expanded
    ):
        expanded.add("personal_data_likely")
    if expanded & {
        "rechargeable",
        "removable_battery",
        "lithium_ion_battery",
        "energy_storage",
        "charger_role",
        "charge_controller",
        "power_source",
        "powered_load",
        "wireless_charging_rx",
        "wireless_charging_tx",
        "usb_pd",
        "poe_powered",
        "poe_supply",
        "backup_battery",
        "energy_monitoring",
        "smart_grid_ready",
        "vehicle_supply",
        "ev_charging",
        "solar_powered",
        "ev_connector",
        "ev_cable_accessory",
    }:
        expanded.add("electrical")
    if "weather_exposure" in expanded:
        expanded.add("outdoor_use")
    if expanded & {"machine_like", "cutting_hazard", "fan_air_mover", "pump_system", "compressor_system", "rotating_part"}:
        expanded.update({"motorized", "electrical"})
    if expanded & {
        "camera",
        "display",
        "microphone",
        "speaker",
        "data_storage",
        "screen_mirroring",
        "multi_room_audio",
        "spatial_audio",
        "voice_assistant",
        "parental_controls",
        "subscription_dependency",
        "secure_boot",
        "hardware_security_element",
        "remote_management",
        "matter_bridge",
        "e_ink_display",
        "hdr_display",
        "high_refresh_display",
        "display_touchscreen",
    }:
        expanded.add("av_ict")
    if expanded & {
        "camera",
        "display",
        "microphone",
        "speaker",
        "data_storage",
        "screen_mirroring",
        "multi_room_audio",
        "spatial_audio",
        "voice_assistant",
        "privacy_switch",
        "parental_controls",
        "subscription_dependency",
        "secure_boot",
        "hardware_security_element",
        "remote_management",
        "matter_bridge",
        "poe_powered",
        "poe_supply",
        "wireless_charging_rx",
        "wireless_charging_tx",
        "usb_pd",
        "energy_monitoring",
        "smart_grid_ready",
        "backup_battery",
        "ambient_light_sensor",
        "occupancy_detection",
        "gas_detection",
        "flood_detection",
        "door_window_sensor",
        "strobe_output",
    }:
        expanded.add("electronic")

    return expanded


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

    inferred_traits = _expand_related_traits(_infer_baseline_traits(text, explicit_traits))
    if inferred_traits:
        _record_trait_state(state_map, "text_inferred", inferred_traits, "text:baseline_inference")

    connected_inferred = _expand_related_traits(_infer_connected_traits(text, explicit_traits | inferred_traits)) - explicit_traits - inferred_traits
    if connected_inferred:
        inferred_traits |= connected_inferred
        _record_trait_state(state_map, "text_inferred", connected_inferred, "text:connected_inference")

    return explicit_traits, inferred_traits, state_map, negations


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
    text = normalize(f"{category} {description}")
    explicit_traits: set[str] = set()
    inferred_traits: set[str] = set()
    confirmed_traits: set[str] = set()
    functional_classes: set[str] = set()
    confirmed_functional_classes: set[str] = set()
    contradictions: list[str] = []
    diagnostics: list[str] = []
    negations = sorted(trait for trait in _signal_snapshot().negations if _trait_is_negated(text, trait))

    _add_regex_trait(text, explicit_traits)
    explicit_traits = _expand_related_traits(explicit_traits)
    explicit_traits = _apply_explicit_trait_negations(explicit_traits, negations)
    inferred_traits.update(_infer_baseline_traits(text, explicit_traits))
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
        )
    )
    inferred_traits = _apply_explicit_trait_negations(inferred_traits, negations)
    inferred_traits.update(
        _suppress_unmentioned_product_wireless_traits(
            text,
            _expand_related_traits(set(match["subtype_traits"])),
            explicit_traits,
            matched_aliases,
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

    if "battery_powered" in explicit_traits and "mains_powered" in explicit_traits:
        contradictions.append("Both battery-powered and mains-powered signals were detected.")
    if "cloud" in explicit_traits and "local_only" in explicit_traits:
        contradictions.append("Both cloud-connected and local-only signals were detected.")
    if "professional" in explicit_traits and "household" in explicit_traits:
        contradictions.append("Both professional/commercial and household-use signals were detected.")
    if "wifi" in explicit_traits and _trait_is_negated(text, "internet") and {"cloud", "ota", "account"} & explicit_traits:
        contradictions.append("Wi-Fi is present while the text also says no internet, but cloud or OTA features were also detected.")

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
    return extract_traits_v2(description=description, category=category)


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
    "_known_trait_ids",
    "extract_traits",
    "extract_traits_v1",
    "extract_traits_v2",
    "reset_classifier_cache",
]
