from __future__ import annotations

from .scoring import ELECTRONIC_SIGNAL_TRAITS, POWER_TRAITS, RADIO_TRAITS


def _escalate_boundary_traits(expanded: set[str]) -> set[str]:
    if expanded & {"medical_context", "medical_claims", "possible_medical_boundary"}:
        expanded.update({"health_related", "possible_medical_boundary"})
    if expanded & {"uv_emitting", "infrared_emitting", "laser"}:
        expanded.update({"optical_emission", "photobiological_relevance"})
    if expanded & {"energy_storage", "battery_storage_role", "inverter_role", "ups_role", "solar_charge_controller_role"}:
        expanded.add("energy_system_boundary")
    if expanded & {"uv_sanitization_role", "germicidal_role", "irradiation_boundary"}:
        expanded.add("uv_irradiation_boundary")
    if expanded & {"industrial_installation", "industrial_boundary"}:
        expanded.add("industrial_installation_boundary")
    if expanded & {"therapy_role", "stimulation_role", "treatment_role"}:
        expanded.add("body_treatment_boundary")
    if expanded & {"machinery_boundary", "machine_like", "cutting_hazard", "rotating_part"}:
        expanded.add("machinery_boundary")
    return expanded


def _infer_baseline_traits(
    text: str,
    explicit_traits: set[str],
    *,
    has_cue_group,
) -> set[str]:
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

    if (electrical_signals & explicit_traits) or has_cue_group(text, "electrical"):
        inferred.add("electrical")
    if (electronic_signals & explicit_traits) or has_cue_group(text, "electronic"):
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

    return _escalate_boundary_traits(inferred)


def _infer_connected_traits(
    text: str,
    signal_traits: set[str],
    *,
    has_cue_group,
) -> set[str]:
    inferred: set[str] = set()

    local_only = "local_only" in signal_traits or has_cue_group(text, "local_only")
    smartish = has_cue_group(text, "smart_connected")
    consumerish = bool({"consumer", "household", "personal_care", "wearable", "pet_use"} & signal_traits) or has_cue_group(
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
        return _escalate_boundary_traits(inferred)

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

    return _escalate_boundary_traits(inferred)


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
        "battery_storage_role",
        "inverter_role",
        "ups_role",
        "solar_charge_controller_role",
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

    return _escalate_boundary_traits(expanded)


__all__ = [
    "_escalate_boundary_traits",
    "_expand_related_traits",
    "_infer_baseline_traits",
    "_infer_connected_traits",
]
