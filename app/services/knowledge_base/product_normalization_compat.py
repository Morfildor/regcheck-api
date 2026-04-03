from __future__ import annotations

from typing import Any


LEGACY_PRODUCT_GENRE_OVERRIDES: dict[str, list[str]] = {
    "portable_ev_charger": ["ev_charging_equipment"],
    "electric_fish_stunner": ["commercial_appliance"],
    "fence_energizer": ["commercial_appliance"],
    "industrial_air_compressor": ["commercial_appliance"],
    "pen_3d": ["av_ict_device"],
    "rc_boat": ["connected_toy_childcare"],
    "rc_car": ["connected_toy_childcare"],
    "solar_panel_module": ["energy_power_system"],
}

LEGACY_PRODUCT_TRAIT_ENRICHMENTS: dict[str, list[str]] = {
    "5g_home_gateway": ["network_gateway"],
    "battery_powered_oral_hygiene": ["oral_irrigation", "skin_contact", "sonic_cleaning"],
    "coffee_machine": ["bean_to_cup", "capsule_brewing"],
    "docking_station": ["docking_station"],
    "electric_fish_stunner": ["agricultural_special_use_boundary"],
    "ev_connector_accessory": ["ev_cable_accessory", "ev_connector"],
    "fan": ["floor_standing"],
    "fence_energizer": ["agricultural_special_use_boundary"],
    "home_projector": ["portable_projection"],
    "industrial_air_compressor": ["machine_like"],
    "iot_gateway": ["network_gateway", "smart_home_hub"],
    "liquid_heater": ["liquid_heating"],
    "livestock_heater": ["agricultural_special_use_boundary"],
    "lora_gateway": ["network_gateway", "smart_home_hub"],
    "mesh_wifi_system": ["whole_home_wifi"],
    "milking_machine": ["agricultural_special_use_boundary"],
    "network_switch": ["vlan_support"],
    "bench_saw": ["machine_like"],
    "robot_mop": ["mop_function", "robotic_motion"],
    "robot_vacuum": ["mapping_capable", "obstacle_avoidance", "robotic_motion", "room_mapping", "self_emptying", "slam_navigation"],
    "rotary_tool": ["machine_like"],
    "router": ["vpn_capable"],
    "smart_posture_corrector": ["skin_contact", "vibration_sensor"],
    "smart_tv": ["streaming_apps"],
    "ups": ["energy_system_boundary"],
}


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if isinstance(item, str) and str(item).strip()]


def _merge_unique(*values: Any) -> list[str]:
    merged: list[str] = []
    seen: set[str] = set()
    for value in values:
        for item in _string_list(value):
            if item in seen:
                continue
            seen.add(item)
            merged.append(item)
    return merged


def apply_compatibility_enrichments(row: dict[str, Any]) -> dict[str, Any]:
    enriched = dict(row)
    product_id = str(enriched.get("id") or "").strip()

    if not _string_list(enriched.get("genres")):
        genres = LEGACY_PRODUCT_GENRE_OVERRIDES.get(product_id)
        if genres:
            enriched["genres"] = list(genres)

    extra_traits = LEGACY_PRODUCT_TRAIT_ENRICHMENTS.get(product_id)
    if extra_traits:
        enriched["default_traits"] = _merge_unique(enriched.get("default_traits"), extra_traits)

    return enriched


__all__ = [
    "LEGACY_PRODUCT_GENRE_OVERRIDES",
    "LEGACY_PRODUCT_TRAIT_ENRICHMENTS",
    "apply_compatibility_enrichments",
]
