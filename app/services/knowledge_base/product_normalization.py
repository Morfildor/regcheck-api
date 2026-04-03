from __future__ import annotations

from typing import Any

from app.services.rules.route_anchors import apply_route_anchor_defaults


def _group(update: dict[str, Any], *product_ids: str) -> dict[str, dict[str, Any]]:
    return {product_id: dict(update) for product_id in product_ids}


PRODUCT_STRUCTURE_OVERRIDES: dict[str, dict[str, Any]] = {}
PRODUCT_STRUCTURE_OVERRIDES.update(
    _group(
        {"product_family": "water_handling_appliance"},
        "aquarium_appliance",
        "circulator",
        "electric_pump",
        "food_waste_disposer",
    )
)
PRODUCT_STRUCTURE_OVERRIDES.update(
    _group(
        {"product_family": "washing_hygiene_appliance"},
        "commercial_dishwasher",
        "commercial_rinsing_sink",
        "commercial_washing_machine",
        "dishwasher",
        "electrolyser_washing_machine",
        "shower_cabinet",
        "smart_toilet",
        "washing_machine",
        "whirlpool_bath",
    )
)
PRODUCT_STRUCTURE_OVERRIDES.update(
    _group(
        {"product_family": "climate_conditioning_appliance"},
        "climate_conditioning_appliance",
        "fan",
        "fan_heater",
        "heat_pump",
        "heating_lamp",
        "humidifier",
        "hvac_humidifier",
        "incubator",
        "room_dehumidifier",
        "room_heater",
        "room_heating_appliance",
        "sauna_heater",
        "vaporizer",
    )
)
PRODUCT_STRUCTURE_OVERRIDES.update(
    _group(
        {"product_family": "personal_heating_appliance"},
        "electric_blanket",
        "foot_warmer",
        "heated_carpet",
        "heating_pad",
        "water_bed_heater",
    )
)
PRODUCT_STRUCTURE_OVERRIDES.update(
    _group(
        {"product_family": "water_heating_appliance"},
        "immersion_heater",
        "portable_immersion_heater",
        "storage_water_heater",
    )
)
PRODUCT_STRUCTURE_OVERRIDES.update(
    _group(
        {"product_family": "laundry_textile_appliance"},
        "electric_iron",
        "fabric_steamer",
        "ironer",
        "sewing_machine",
        "tumble_dryer",
    )
)
PRODUCT_STRUCTURE_OVERRIDES.update(
    _group(
        {"product_family": "surface_cleaning_appliance"},
        "commercial_floor_treatment_machine",
        "commercial_spray_extraction_machine",
        "floor_treatment_machine",
        "high_pressure_cleaner",
        "robot_mop",
        "robot_vacuum",
        "spray_extraction_machine",
        "vacuum_cleaner",
        "water_suction_cleaner",
    )
)
PRODUCT_STRUCTURE_OVERRIDES.update(
    _group(
        {"product_family": "fitness_training_equipment"},
        "elliptical_trainer",
        "exercise_bike",
        "smart_treadmill",
    )
)
PRODUCT_STRUCTURE_OVERRIDES.update(
    _group(
        {"product_family": "countertop_cooking_appliance"},
        "air_fryer",
        "barbecue_grill",
        "cooking_range",
        "deep_fryer",
        "electric_frying_pan",
        "hob",
        "microwave_oven",
        "outdoor_barbecue",
        "oven",
        "portable_grill",
        "toaster",
        "warming_plate",
    )
)
PRODUCT_STRUCTURE_OVERRIDES.update(
    _group(
        {"product_family": "food_preparation_appliance"},
        "blender",
        "food_processor",
        "juicer",
        "kitchen_machine",
        "spin_extractor",
    )
)
PRODUCT_STRUCTURE_OVERRIDES.update(
    _group(
        {"product_family": "beverage_preparation_appliance"},
        "coffee_grinder",
        "coffee_machine",
        "electric_kettle",
        "liquid_heater",
        "rice_cooker",
    )
)
PRODUCT_STRUCTURE_OVERRIDES.update(
    _group(
        {"product_family": "commercial_food_service_appliance"},
        "bain_marie",
        "commercial_cooking_appliance",
        "commercial_dispensing_appliance",
        "commercial_fryer",
        "commercial_hood",
        "commercial_kitchen_machine",
        "commercial_microwave",
        "commercial_oven",
        "hot_cupboard",
        "vending_machine",
    )
)
PRODUCT_STRUCTURE_OVERRIDES.update(
    _group(
        {"product_family": "cold_storage_appliance"},
        "commercial_refrigerator",
        "refrigerator_freezer",
    )
)
PRODUCT_STRUCTURE_OVERRIDES.update(
    _group(
        {"product_family": "ventilation_extraction_appliance"},
        "kitchen_extractor_fan",
        "range_hood",
    )
)
PRODUCT_STRUCTURE_OVERRIDES.update(
    _group(
        {"product_family": "garden_power_equipment"},
        "electric_garden_tool",
        "grass_shear",
        "grass_trimmer",
        "lawn_mower",
        "robotic_lawn_mower",
        "scarifier_aerator",
    )
)
PRODUCT_STRUCTURE_OVERRIDES.update(
    _group(
        {"product_family": "portable_power_charger"},
        "battery_charger",
        "industrial_charger",
        "usb_charging_hub",
        "wireless_charger",
    )
)
PRODUCT_STRUCTURE_OVERRIDES.update(
    _group(
        {"product_family": "portable_power_system"},
        "portable_power_station",
        "power_bank",
    )
)
PRODUCT_STRUCTURE_OVERRIDES.update(
    _group(
        {"product_family": "energy_power_system"},
        "home_battery_system",
        "home_energy_monitor",
        "smart_meter_gateway",
        "smart_meter_display",
        "solar_charge_controller",
        "solar_inverter_gateway",
        "solar_panel_module",
    )
)
PRODUCT_STRUCTURE_OVERRIDES.update(
    _group(
        {"product_family": "building_access_device"},
        "garage_door_drive",
        "gate_door_window_drive",
        "rolling_shutter_drive",
    )
)
PRODUCT_STRUCTURE_OVERRIDES.update(
    _group(
        {"product_family": "smart_home_security"},
        "baby_monitor",
        "ip_camera",
        "ip_intercom",
        "pet_camera",
        "security_hub",
    )
)
PRODUCT_STRUCTURE_OVERRIDES.update(
    _group(
        {"product_family": "networking_device"},
        "5g_home_gateway",
        "iot_gateway",
        "lora_gateway",
        "mesh_wifi_system",
        "modem",
        "network_switch",
        "router",
        "satellite_terminal",
        "wireless_access_point",
    )
)
PRODUCT_STRUCTURE_OVERRIDES.update(
    _group(
        {"product_family": "personal_computing_device"},
        "desktop_pc",
        "e_reader",
        "laptop",
        "tablet",
    )
)
PRODUCT_STRUCTURE_OVERRIDES.update(
    _group(
        {"product_family": "display_device"},
        "digital_photo_frame",
        "monitor",
        "smart_tv",
    )
)
PRODUCT_STRUCTURE_OVERRIDES.update(
    _group(
        {"product_family": "office_avict_peripheral"},
        "docking_station",
        "external_storage",
        "usb_hub",
        "webcam",
    )
)
PRODUCT_STRUCTURE_OVERRIDES.update(
    _group(
        {"product_family": "home_entertainment_device"},
        "bluetooth_speaker",
        "digital_audio_player",
        "digital_piano",
        "electric_guitar",
        "game_console",
        "home_cinema_system",
        "soundbar",
        "streaming_device",
        "voip_dect_phone",
    )
)
PRODUCT_STRUCTURE_OVERRIDES.update(
    _group(
        {"product_family": "creator_office_device"},
        "pen_3d",
        "printer_3d",
    )
)
PRODUCT_STRUCTURE_OVERRIDES.update(
    _group(
        {"product_family": "micromobility_device"},
        "electric_bicycle",
        "electric_cargo_bike",
        "electric_scooter",
        "electric_skateboard",
        "electric_unicycle",
        "hoverboard",
    )
)
PRODUCT_STRUCTURE_OVERRIDES.update(
    _group(
        {"product_family": "drone_device"},
        "consumer_drone",
        "drone_controller",
    )
)
PRODUCT_STRUCTURE_OVERRIDES.update(
    _group(
        {"product_family": "specialty_electrical_device"},
        "electric_fish_stunner",
        "fence_energizer",
    )
)
PRODUCT_STRUCTURE_OVERRIDES.update(
    _group(
        {"product_family": "agricultural_appliance"},
        "livestock_heater",
        "milking_machine",
    )
)
PRODUCT_STRUCTURE_OVERRIDES.update(
    _group(
        {"product_family": "personal_care_appliance"},
        "battery_powered_oral_hygiene",
        "beauty_treatment_appliance",
        "hair_clipper",
        "hair_curler",
        "oral_hygiene_appliance",
        "shaver",
        "skin_hair_care_appliance",
    )
)
PRODUCT_STRUCTURE_OVERRIDES.update(
    _group(
        {"product_family": "wearable_device_family"},
        "led_shoes",
        "sleep_tracker",
    )
)
PRODUCT_STRUCTURE_OVERRIDES.update(
    _group(
        {"product_family": "smart_environment_sensor"},
        "smart_air_quality_monitor",
        "smart_sensor_node",
        "soil_moisture_sensor",
    )
)
PRODUCT_STRUCTURE_OVERRIDES.update(
    _group(
        {"product_family": "smart_power_control"},
        "smart_light_controller",
        "smart_plug",
        "smart_power_strip",
    )
)
PRODUCT_STRUCTURE_OVERRIDES.update(
    _group(
        {"product_family": "smart_home_control_device"},
        "smart_home_panel",
        "smart_button_remote",
    )
)
PRODUCT_STRUCTURE_OVERRIDES.update(
    _group(
        {"product_family": "connected_child_product"},
        "rc_boat",
        "rc_car",
    )
)
PRODUCT_STRUCTURE_OVERRIDES.update(
    _group(
        {"product_family": "health_monitor"},
        "smart_blood_pressure_monitor",
        "smart_scale",
    )
)
PRODUCT_STRUCTURE_OVERRIDES.update(
    _group(
        {"product_family": "sports_wearable"},
        "smart_jump_rope",
    )
)

PRODUCT_BOUNDARY_OVERRIDES: dict[str, dict[str, Any]] = {}
PRODUCT_BOUNDARY_OVERRIDES.update(
    _group(
        {
            "route_anchor": "medical_wellness_boundary",
            "boundary_tags": ["possible_medical_boundary", "body_treatment_boundary"],
        },
        "cpap_device",
        "ems_tens_device",
        "red_light_therapy_device",
    )
)
PRODUCT_BOUNDARY_OVERRIDES.update(
    _group(
        {
            "route_anchor": "power_system_boundary",
            "route_family": "power_system_boundary",
            "primary_standard_code": None,
            "boundary_tags": ["energy_system_boundary", "industrial_installation_boundary"],
            "genres": ["energy_power_system"],
        },
        "home_battery_system",
        "home_energy_monitor",
        "smart_meter_gateway",
        "smart_meter_display",
        "solar_charge_controller",
        "solar_inverter_gateway",
        "solar_panel_module",
    )
)
PRODUCT_BOUNDARY_OVERRIDES.update(
    _group(
        {"route_anchor": "drone_uas_boundary"},
        "consumer_drone",
        "drone_controller",
    )
)
PRODUCT_BOUNDARY_OVERRIDES.update(
    _group(
        {"route_anchor": "specialty_electrical_boundary", "boundary_tags": ["agricultural_special_use_boundary"]},
        "electric_fish_stunner",
        "fence_energizer",
        "livestock_heater",
        "milking_machine",
    )
)
PRODUCT_BOUNDARY_OVERRIDES.update(
    _group(
        {"route_anchor": "lighting_core", "boundary_tags": ["uv_irradiation_boundary", "body_treatment_boundary"]},
        "ultraviolet_appliance",
        "uv_c_sanitizer",
        "uv_nail_lamp",
    )
)
PRODUCT_BOUNDARY_OVERRIDES.update(
    _group(
        {"route_anchor": "hvac_control"},
        "smart_radiator_valve",
    )
)
PRODUCT_BOUNDARY_OVERRIDES.update(
    _group(
        {"route_anchor": "ev_charging"},
        "portable_ev_charger",
    )
)
PRODUCT_BOUNDARY_OVERRIDES.update(
    _group(
        {"route_anchor": "avict_core"},
        "industrial_charger",
    )
)

PRODUCT_GENRE_OVERRIDES: dict[str, list[str]] = {
    "portable_ev_charger": ["ev_charging_equipment"],
    "electric_fish_stunner": ["commercial_appliance"],
    "fence_energizer": ["commercial_appliance"],
    "industrial_air_compressor": ["commercial_appliance"],
    "pen_3d": ["av_ict_device"],
    "rc_boat": ["connected_toy_childcare"],
    "rc_car": ["connected_toy_childcare"],
    "solar_panel_module": ["energy_power_system"],
}

PRODUCT_TRAIT_ENRICHMENTS: dict[str, list[str]] = {
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

WEAK_FAMILY_RENAMES = {
    "electric_bicycle": "micromobility_device",
    "portable_energy_family": "portable_power_system",
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


def _normalized_genres(row: dict[str, Any]) -> list[str]:
    genres = _string_list(row.get("genres"))
    if genres:
        return genres
    return PRODUCT_GENRE_OVERRIDES.get(str(row.get("id") or ""), [])


def _heuristic_family(row: dict[str, Any], genres: list[str]) -> str | None:
    pid = str(row.get("id") or "")
    genre_set = set(genres)
    traits = set(_merge_unique(row.get("implied_traits"), row.get("core_traits"), row.get("default_traits")))

    if genre_set & {"av_ict_device"}:
        return "av_ict_device"
    if genre_set & {"wearable_device", "xr_immersive"}:
        return "wearable_device_family"
    if genre_set & {"portable_energy"}:
        return "portable_power_charger"
    if genre_set & {"building_access_drive", "building_hardware_lock"}:
        return "building_access_device"
    if genre_set & {"life_safety_alarm"}:
        return "life_safety_alarm"
    if genre_set & {"garden_outdoor_power", "electric_power_tool"}:
        return "garden_power_equipment"
    if genre_set & {"micromobility"}:
        return "micromobility_device"
    if genre_set & {"drone_uas"}:
        return "drone_device"
    if genre_set & {"personal_care_appliance"}:
        return "personal_care_appliance"
    if genre_set & {"kitchen_food_appliance", "cooking_food_appliance"}:
        if {"cooling", "refrigeration"} & traits:
            return "cold_storage_appliance"
        if {"coffee_brewing", "coffee_grinding"} & traits or "coffee" in pid:
            return "beverage_preparation_appliance"
        if "food_preparation" in traits or {"blender", "juicer", "food_processor", "kitchen_machine"} & {pid}:
            return "food_preparation_appliance"
        return "countertop_cooking_appliance"
    if genre_set & {"cleaning_laundry_appliance"}:
        if {"surface_cleaning", "cleaning"} & traits or "vacuum" in pid or "cleaner" in pid:
            return "surface_cleaning_appliance"
        return "laundry_textile_appliance"
    if genre_set & {"hvac_environmental_appliance"}:
        if {"water_heating", "water_contact"} <= traits and "heating" in traits:
            return "water_heating_appliance"
        if "heating" in traits:
            return "climate_conditioning_appliance"
        return "climate_conditioning_appliance"
    if genre_set & {"household_appliance", "commercial_appliance"}:
        if "personal_care" in traits:
            return "personal_care_appliance"
        if "security_or_barrier" in traits:
            return "building_access_device"
        return "household_appliance"
    return None


def _inferred_family(row: dict[str, Any], genres: list[str]) -> str:
    pid = str(row.get("id") or "")
    current = str(row.get("product_family") or "").strip()
    if current and current != "unknown":
        return WEAK_FAMILY_RENAMES.get(current, current)

    override = PRODUCT_STRUCTURE_OVERRIDES.get(pid, {})
    explicit = str(override.get("product_family") or "").strip()
    if explicit:
        return explicit

    heuristic = _heuristic_family(row, genres)
    if heuristic:
        return heuristic
    return pid


def _normalized_subfamily(row: dict[str, Any]) -> str:
    current = str(row.get("product_subfamily") or "").strip()
    if current and current != "unknown":
        return current
    return str(row.get("id") or current)


def _merge_overrides(row: dict[str, Any]) -> dict[str, Any]:
    pid = str(row.get("id") or "")
    merged = dict(row)
    for source in (PRODUCT_STRUCTURE_OVERRIDES.get(pid), PRODUCT_BOUNDARY_OVERRIDES.get(pid)):
        if not source:
            continue
        for key, value in source.items():
            if key in {"boundary_tags"}:
                merged[key] = _merge_unique(merged.get(key), value)
                continue
            if key == "genres":
                merged[key] = _merge_unique(merged.get(key), value)
                continue
            merged[key] = value
    return merged


def _merge_trait_enrichments(row: dict[str, Any]) -> dict[str, Any]:
    pid = str(row.get("id") or "")
    extra_traits = PRODUCT_TRAIT_ENRICHMENTS.get(pid)
    if not extra_traits:
        return row

    merged = dict(row)
    merged["default_traits"] = _merge_unique(merged.get("default_traits"), extra_traits)
    return merged


def normalize_product_row(row: dict[str, Any]) -> dict[str, Any]:
    normalized = _merge_overrides(row)
    normalized["genres"] = _normalized_genres(normalized)
    normalized["product_family"] = _inferred_family(normalized, normalized["genres"])
    normalized["product_subfamily"] = _normalized_subfamily(normalized)
    normalized = _merge_trait_enrichments(normalized)
    normalized["boundary_tags"] = _merge_unique(normalized.get("boundary_tags"))
    return apply_route_anchor_defaults(normalized)


__all__ = ["normalize_product_row"]
