from __future__ import annotations

from dataclasses import dataclass
from typing import Any


CONNECTED_ROUTE_TRAITS = {
    "account",
    "account_required",
    "app_control",
    "authentication",
    "bluetooth",
    "cellular",
    "cloud",
    "cloud_dependent",
    "internet",
    "internet_connected",
    "matter",
    "ota",
    "radio",
    "thread",
    "wifi",
    "zigbee",
}

WEARABLE_ROUTE_TRAITS = {"wearable", "body_worn_or_applied", "close_proximity_emf"}

ROUTE_FAMILY_SCOPE = {
    "household_appliance": "appliance",
    "av_ict": "av_ict",
    "av_ict_wearable": "av_ict",
    "lighting_device": "appliance",
    "building_hardware": "appliance",
    "hvac_control": "appliance",
    "life_safety_alarm": "appliance",
    "ev_charging": "appliance",
    "ev_connector_accessory": "appliance",
    "machinery_power_tool": "machinery",
    "toy": "toy",
    "power_system_boundary": "generic",
    "medical_wellness_boundary": "generic",
    "micromobility_device": "generic",
    "drone_uas": "generic",
    "specialty_electrical_boundary": "generic",
}

ROUTE_FAMILY_PRIMARY_DIRECTIVE = {
    "ev_connector_accessory": "LVD",
    "machinery_power_tool": "MD",
    "toy": "TOY",
}

ROUTE_STANDARD_FAMILY_RULES: tuple[tuple[str, str, str], ...] = (
    ("EN IEC 61851-", "ev_charging", "EV charging equipment"),
    ("IEC 62752", "ev_charging", "portable EV charging equipment"),
    ("EN 62196-2", "ev_connector_accessory", "EV connector / cable accessory"),
    ("EN 62841-", "machinery_power_tool", "power-tool / machinery equipment"),
    ("EN 50636-", "machinery_power_tool", "garden / outdoor powered equipment"),
    ("EN 60335-2-77", "machinery_power_tool", "garden / outdoor powered equipment"),
    ("EN 60335-2-91", "machinery_power_tool", "garden / outdoor powered equipment"),
    ("EN 60335-2-92", "machinery_power_tool", "garden / outdoor powered equipment"),
    ("EN 60335-2-94", "machinery_power_tool", "garden / outdoor powered equipment"),
    ("EN 60335-2-107", "machinery_power_tool", "garden / outdoor powered equipment"),
    ("EN 14846", "building_hardware", "building access device"),
    ("EN 12209", "building_hardware", "building access device"),
    ("EN 60335-2-95", "building_hardware", "building access drive"),
    ("EN 60335-2-97", "building_hardware", "building access drive"),
    ("EN 60335-2-103", "building_hardware", "building access drive"),
    ("EN 60730-", "hvac_control", "control equipment"),
    ("EN 14604", "life_safety_alarm", "life-safety alarm"),
    ("EN 50291-", "life_safety_alarm", "life-safety alarm"),
    ("EN IEC 62560", "lighting_device", "lighting product"),
    ("EN 60598-", "lighting_device", "lighting product"),
    ("EN 60335-", "household_appliance", "household appliance"),
    ("EN 62368-1", "av_ict", "AV/ICT equipment"),
    ("EN 15194", "micromobility_device", "micromobility product"),
    ("EN 17128", "micromobility_device", "micromobility product"),
    ("UAS OPEN-CATEGORY REVIEW", "drone_uas", "drone / UAS product"),
    ("EN 62115", "toy", "toy"),
)


@dataclass(frozen=True, slots=True)
class RouteAnchorDefinition:
    key: str
    route_family: str
    label: str
    primary_directive: str | None = None
    exact_primary_candidates: tuple[str, ...] = ()
    prefix_primary_candidates: tuple[str, ...] = ()
    boundary_tags: tuple[str, ...] = ()
    max_match_stage: str | None = None
    route_confidence_cap: str | None = None
    family_level_reason: str | None = None


ROUTE_ANCHOR_RULES: dict[str, RouteAnchorDefinition] = {
    "household_core": RouteAnchorDefinition(
        key="household_core",
        route_family="household_appliance",
        label="Household appliance",
        exact_primary_candidates=("EN 60335-1",),
        prefix_primary_candidates=("EN 60335-2-",),
    ),
    "household_connected": RouteAnchorDefinition(
        key="household_connected",
        route_family="household_appliance",
        label="Connected household appliance",
        exact_primary_candidates=("EN 60335-1",),
        prefix_primary_candidates=("EN 60335-2-",),
    ),
    "hvac_control": RouteAnchorDefinition(
        key="hvac_control",
        route_family="hvac_control",
        label="HVAC / building control",
        exact_primary_candidates=("EN 60730-2-9", "EN 60730-1"),
        prefix_primary_candidates=("EN 60730-",),
    ),
    "lighting_core": RouteAnchorDefinition(
        key="lighting_core",
        route_family="lighting_device",
        label="Lighting / optical product",
        exact_primary_candidates=("EN IEC 62560", "EN 60598-1"),
        prefix_primary_candidates=("EN 60598-",),
    ),
    "lighting_connected": RouteAnchorDefinition(
        key="lighting_connected",
        route_family="lighting_device",
        label="Connected lighting / optical product",
        exact_primary_candidates=("EN IEC 62560", "EN 60598-1"),
        prefix_primary_candidates=("EN 60598-",),
    ),
    "avict_core": RouteAnchorDefinition(
        key="avict_core",
        route_family="av_ict",
        label="AV / ICT device",
        exact_primary_candidates=("EN 62368-1",),
    ),
    "avict_connected": RouteAnchorDefinition(
        key="avict_connected",
        route_family="av_ict",
        label="Connected AV / ICT device",
        exact_primary_candidates=("EN 62368-1",),
    ),
    "avict_wearable": RouteAnchorDefinition(
        key="avict_wearable",
        route_family="av_ict_wearable",
        label="Wearable AV / ICT device",
        exact_primary_candidates=("EN 62368-1",),
    ),
    "building_access": RouteAnchorDefinition(
        key="building_access",
        route_family="building_hardware",
        label="Building access / security hardware",
        exact_primary_candidates=("EN 14846", "EN 12209", "EN 60335-2-95", "EN 60335-2-97", "EN 60335-2-103"),
    ),
    "life_safety_alarm": RouteAnchorDefinition(
        key="life_safety_alarm",
        route_family="life_safety_alarm",
        label="Life-safety alarm",
        exact_primary_candidates=("EN 14604", "EN 50291-1"),
        prefix_primary_candidates=("EN 50291-",),
    ),
    "ev_charging": RouteAnchorDefinition(
        key="ev_charging",
        route_family="ev_charging",
        label="EV charging equipment",
        exact_primary_candidates=("EN IEC 61851-1", "IEC 62752", "EN IEC 61851-21-2"),
        prefix_primary_candidates=("EN IEC 61851-",),
    ),
    "ev_connector_accessory": RouteAnchorDefinition(
        key="ev_connector_accessory",
        route_family="ev_connector_accessory",
        label="EV connector / cable accessory",
        exact_primary_candidates=("EN 62196-2",),
    ),
    "machinery_tool": RouteAnchorDefinition(
        key="machinery_tool",
        route_family="machinery_power_tool",
        label="Machinery / tool / outdoor powered equipment",
        exact_primary_candidates=("EN 62841-1", "EN 50636-2-107"),
        prefix_primary_candidates=("EN 62841-", "EN 50636-", "EN 60335-2-77", "EN 60335-2-91", "EN 60335-2-92", "EN 60335-2-94", "EN 60335-2-107"),
        primary_directive="MD",
    ),
    "toy": RouteAnchorDefinition(
        key="toy",
        route_family="toy",
        label="Toy / child-directed product",
        exact_primary_candidates=("EN 62115",),
        primary_directive="TOY",
    ),
    "power_system_boundary": RouteAnchorDefinition(
        key="power_system_boundary",
        route_family="power_system_boundary",
        label="Energy system / inverter / storage boundary",
        boundary_tags=("energy_system_boundary", "industrial_installation_boundary"),
        max_match_stage="family",
        route_confidence_cap="low",
        family_level_reason="Energy-system and fixed-installation products stay at family level pending boundary review.",
    ),
    "medical_wellness_boundary": RouteAnchorDefinition(
        key="medical_wellness_boundary",
        route_family="medical_wellness_boundary",
        label="Wellness / medical boundary",
        boundary_tags=("possible_medical_boundary",),
        max_match_stage="family",
        route_confidence_cap="low",
        family_level_reason="Wellness and therapy-adjacent products stay at family level pending medical-boundary review.",
    ),
    "micromobility_boundary": RouteAnchorDefinition(
        key="micromobility_boundary",
        route_family="micromobility_device",
        label="Micromobility boundary",
        route_confidence_cap="medium",
    ),
    "drone_uas_boundary": RouteAnchorDefinition(
        key="drone_uas_boundary",
        route_family="drone_uas",
        label="Drone / UAS boundary",
        route_confidence_cap="medium",
    ),
    "specialty_electrical_boundary": RouteAnchorDefinition(
        key="specialty_electrical_boundary",
        route_family="specialty_electrical_boundary",
        label="Specialty / agricultural electrical boundary",
        boundary_tags=("industrial_installation_boundary",),
        max_match_stage="family",
        route_confidence_cap="low",
        family_level_reason="Special-use electrical products stay at family level pending specialty-use review.",
    ),
}


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if isinstance(item, str) and str(item).strip()]


def normalized_standard_codes(codes: set[str] | list[str] | None) -> list[str]:
    normalized: list[str] = []
    seen: set[str] = set()
    for raw_code in codes or []:
        code = str(raw_code or "").upper().replace("  ", " ").strip()
        if not code or code in seen:
            continue
        seen.add(code)
        normalized.append(code)
    return normalized


def family_from_standard_code(code: str, prefer_wearable: bool) -> str | None:
    normalized = str(code or "").upper().replace("  ", " ").strip()
    for prefix, family, _label in ROUTE_STANDARD_FAMILY_RULES:
        if normalized.startswith(prefix):
            if family == "av_ict" and prefer_wearable:
                return "av_ict_wearable"
            return family
    return None


def best_primary_standard_for_family(route_family: str, preferred_codes: list[str]) -> str | None:
    family_codes: list[str] = []
    for code in preferred_codes:
        generic_family = family_from_standard_code(code, prefer_wearable=False)
        wearable_family = family_from_standard_code(code, prefer_wearable=True)
        if route_family in {generic_family, wearable_family}:
            family_codes.append(code)
    if not family_codes:
        return None

    if route_family == "household_appliance":
        part2 = [code for code in family_codes if code.startswith("EN 60335-2-")]
        if part2:
            return sorted(part2)[0]
    if route_family == "machinery_power_tool":
        part2 = [code for code in family_codes if code.startswith("EN 62841-2-")]
        if part2:
            return sorted(part2)[0]
    if route_family == "lighting_device":
        for preferred in ("EN IEC 62560", "EN 60598-1"):
            if preferred in family_codes:
                return preferred
    if route_family == "ev_charging":
        for preferred in ("EN IEC 61851-1", "IEC 62752"):
            if preferred in family_codes:
                return preferred
    if route_family == "ev_connector_accessory" and "EN 62196-2" in family_codes:
        return "EN 62196-2"
    if route_family == "building_hardware":
        for preferred in ("EN 14846", "EN 12209", "EN 60335-2-95", "EN 60335-2-97", "EN 60335-2-103"):
            if preferred in family_codes:
                return preferred
    if route_family == "life_safety_alarm":
        for preferred in ("EN 14604", "EN 50291-1"):
            if preferred in family_codes:
                return preferred
    if route_family == "hvac_control":
        for preferred in ("EN 60730-2-9", "EN 60730-1"):
            if preferred in family_codes:
                return preferred
    if route_family == "micromobility_device":
        for preferred in ("EN 15194", "EN 17128"):
            if preferred in family_codes:
                return preferred
    if route_family in {"av_ict", "av_ict_wearable"} and "EN 62368-1" in family_codes:
        return "EN 62368-1"
    if route_family == "toy" and "EN 62115" in family_codes:
        return "EN 62115"
    return sorted(family_codes)[0]


def route_anchor_definition(anchor: str | None) -> RouteAnchorDefinition | None:
    if not anchor:
        return None
    return ROUTE_ANCHOR_RULES.get(anchor)


def _collect_row_traits(row: dict[str, Any]) -> set[str]:
    traits: set[str] = set()
    for field in ("implied_traits", "core_traits", "default_traits", "family_traits", "subtype_traits", "boundary_tags"):
        traits.update(_string_list(row.get(field)))
    return traits


def _has_connected_signals(row: dict[str, Any], traits: set[str]) -> bool:
    if CONNECTED_ROUTE_TRAITS & traits:
        return True
    genres = set(_string_list(row.get("genres")))
    if genres & {"smart_home_iot", "security_access_iot", "pet_tech"}:
        return True
    codes = normalized_standard_codes(_string_list(row.get("likely_standards")))
    return any(code.startswith(("EN 18031-", "EN 303 645")) for code in codes)


def _anchor_from_route_family(route_family: str | None, traits: set[str]) -> str | None:
    if route_family == "household_appliance":
        return "household_connected" if CONNECTED_ROUTE_TRAITS & traits else "household_core"
    if route_family == "lighting_device":
        return "lighting_connected" if CONNECTED_ROUTE_TRAITS & traits else "lighting_core"
    if route_family == "av_ict":
        return "avict_connected" if CONNECTED_ROUTE_TRAITS & traits else "avict_core"
    if route_family == "av_ict_wearable":
        return "avict_wearable"
    if route_family == "hvac_control":
        return "hvac_control"
    if route_family == "building_hardware":
        return "building_access"
    if route_family == "life_safety_alarm":
        return "life_safety_alarm"
    if route_family == "ev_charging":
        return "ev_charging"
    if route_family == "ev_connector_accessory":
        return "ev_connector_accessory"
    if route_family == "machinery_power_tool":
        return "machinery_tool"
    if route_family == "toy":
        return "toy"
    if route_family == "power_system_boundary":
        return "power_system_boundary"
    if route_family == "medical_wellness_boundary":
        return "medical_wellness_boundary"
    if route_family == "micromobility_device":
        return "micromobility_boundary"
    if route_family == "drone_uas":
        return "drone_uas_boundary"
    if route_family == "specialty_electrical_boundary":
        return "specialty_electrical_boundary"
    return None


def infer_route_anchor(row: dict[str, Any]) -> str | None:
    explicit = str(row.get("route_anchor") or "").strip()
    if explicit in ROUTE_ANCHOR_RULES:
        return explicit

    traits = _collect_row_traits(row)
    route_family = str(row.get("route_family") or "").strip() or None
    anchored = _anchor_from_route_family(route_family, traits)
    if anchored:
        return anchored

    pid = str(row.get("id") or "")
    genres = set(_string_list(row.get("genres")))
    codes = normalized_standard_codes(
        _string_list(row.get("likely_standards"))
        + _string_list(row.get("supporting_standard_codes"))
        + ([str(row.get("primary_standard_code"))] if row.get("primary_standard_code") else [])
    )
    connected = _has_connected_signals(row, traits)

    if "energy_system_boundary" in traits:
        return "power_system_boundary"
    if {"possible_medical_boundary", "medical_adjacent", "medical_claims", "body_treatment_boundary"} & traits:
        return "medical_wellness_boundary"
    if {"industrial_installation_boundary", "agricultural_special_use_boundary"} & traits:
        return "specialty_electrical_boundary"
    if genres & {"ev_charging_equipment"} or {"ev_charging", "vehicle_supply"} & traits:
        if "EN 62196-2" in codes and not any(code.startswith("EN IEC 61851-") or code == "IEC 62752" for code in codes):
            return "ev_connector_accessory"
        return "ev_charging"
    if "toy" in traits or genres & {"connected_toy_childcare"} or "EN 62115" in codes:
        return "toy"
    if genres & {"drone_uas"} or "drone" in pid:
        return "drone_uas_boundary"
    if genres & {"micromobility"} or {"light_means_of_transport", "traction_motor"} & traits or "EN 15194" in codes or "EN 17128" in codes:
        return "micromobility_boundary"
    if genres & {"building_access_drive", "building_hardware_lock"} or any(token in pid for token in ("lock", "garage_door", "gate_door", "shutter")):
        return "building_access"
    if genres & {"life_safety_alarm"} or "alarm" in pid or "smoke" in pid or "co_" in pid:
        return "life_safety_alarm"
    if genres & {"lighting_device"} or {"lighting", "optical_emission", "photobiological_relevance"} & traits or any(
        code.startswith(("EN IEC 62560", "EN 60598-")) for code in codes
    ):
        return "lighting_connected" if connected else "lighting_core"
    if genres & {"wearable_device", "xr_immersive"} or WEARABLE_ROUTE_TRAITS & traits:
        return "avict_wearable"
    if str(row.get("product_family") or "") == "hvac_control" or any(token in pid for token in ("thermostat", "radiator_valve")):
        return "hvac_control"
    if genres & {"garden_outdoor_power", "electric_power_tool"} or "machinery_boundary" in traits or any(
        code.startswith(("EN 62841-", "EN 50636-")) for code in codes
    ):
        return "machinery_tool"
    if genres & {"av_ict_device", "security_access_iot"} or "av_ict" in traits or "EN 62368-1" in codes:
        return "avict_connected" if (connected or genres & {"smart_home_iot", "security_access_iot"}) else "avict_core"
    if genres & {
        "household_appliance",
        "commercial_appliance",
        "kitchen_food_appliance",
        "cooking_food_appliance",
        "cleaning_laundry_appliance",
        "hvac_environmental_appliance",
        "personal_care_appliance",
        "garden_outdoor_appliance",
        "pet_tech",
    }:
        return "household_connected" if connected else "household_core"
    if any(code.startswith("EN 60335-") for code in codes):
        return "household_connected" if connected else "household_core"
    if any(code.startswith("EN 62368-1") for code in codes):
        return "avict_wearable" if WEARABLE_ROUTE_TRAITS & traits else ("avict_connected" if connected else "avict_core")
    if {"solar_powered", "pressure"} & traits:
        return "specialty_electrical_boundary"
    return None


def _preferred_primary_from_anchor(definition: RouteAnchorDefinition, codes: list[str]) -> str | None:
    for preferred in definition.exact_primary_candidates:
        normalized = preferred.upper()
        if normalized in codes:
            return normalized
    for prefix in definition.prefix_primary_candidates:
        normalized_prefix = prefix.upper()
        candidates = [code for code in codes if code.startswith(normalized_prefix)]
        if candidates:
            return sorted(candidates)[0]
    return None


def apply_route_anchor_defaults(row: dict[str, Any]) -> dict[str, Any]:
    enriched = dict(row)
    anchor = infer_route_anchor(enriched)
    if anchor is None:
        return enriched

    definition = route_anchor_definition(anchor)
    if definition is None:
        return enriched

    enriched.setdefault("route_anchor", anchor)
    route_family = str(enriched.get("route_family") or "").strip()
    if not route_family or route_family != definition.route_family:
        enriched["route_family"] = definition.route_family

    codes = normalized_standard_codes(
        _string_list(enriched.get("likely_standards"))
        + _string_list(enriched.get("supporting_standard_codes"))
        + ([str(enriched.get("primary_standard_code"))] if enriched.get("primary_standard_code") else [])
    )
    if definition.route_family.endswith("_boundary"):
        enriched["primary_standard_code"] = None
    elif not str(enriched.get("primary_standard_code") or "").strip():
        primary = _preferred_primary_from_anchor(definition, codes) or best_primary_standard_for_family(definition.route_family, codes)
        if primary:
            enriched["primary_standard_code"] = primary

    if definition.boundary_tags:
        existing_tags = _string_list(enriched.get("boundary_tags"))
        enriched["boundary_tags"] = list(dict.fromkeys(existing_tags + list(definition.boundary_tags)))
    if definition.max_match_stage and not enriched.get("max_match_stage"):
        enriched["max_match_stage"] = definition.max_match_stage
    if definition.route_confidence_cap and not enriched.get("route_confidence_cap"):
        enriched["route_confidence_cap"] = definition.route_confidence_cap
    if definition.family_level_reason and not str(enriched.get("family_level_reason") or "").strip():
        enriched["family_level_reason"] = definition.family_level_reason
    return enriched


__all__ = [
    "ROUTE_ANCHOR_RULES",
    "ROUTE_FAMILY_PRIMARY_DIRECTIVE",
    "ROUTE_FAMILY_SCOPE",
    "ROUTE_STANDARD_FAMILY_RULES",
    "RouteAnchorDefinition",
    "apply_route_anchor_defaults",
    "best_primary_standard_for_family",
    "family_from_standard_code",
    "infer_route_anchor",
    "normalized_standard_codes",
    "route_anchor_definition",
]
