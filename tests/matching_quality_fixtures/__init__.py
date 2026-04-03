from __future__ import annotations

from .base import MatchingQualityCase, expected_case_family
from .building_access_controls import CASES as BUILDING_ACCESS_CONTROLS_CASES
from .climate_water import CASES as CLIMATE_WATER_CASES
from .contrastive import CASES as CONTRASTIVE_CASES
from .contrastive_wave4 import CASES as CONTRASTIVE_WAVE4_CASES
from .ev_micromobility import CASES as EV_MICROMOBILITY_CASES
from .household import CASES as HOUSEHOLD_CASES
from .kitchen_beverage import CASES as KITCHEN_BEVERAGE_CASES
from .lighting_optical import CASES as LIGHTING_OPTICAL_CASES
from .lighting_optical_wave4 import CASES as LIGHTING_OPTICAL_WAVE4_CASES
from .networking import CASES as NETWORKING_CASES
from .networking_wave4 import CASES as NETWORKING_WAVE4_CASES
from .office_peripherals import CASES as OFFICE_PERIPHERALS_CASES
from .office_peripherals_wave4 import CASES as OFFICE_PERIPHERALS_WAVE4_CASES
from .personal_care import CASES as PERSONAL_CARE_CASES
from .power_charging import CASES as POWER_CHARGING_CASES
from .power_charging_wave4 import CASES as POWER_CHARGING_WAVE4_CASES
from .security_access import CASES as SECURITY_ACCESS_CASES
from .security_access_wave4 import CASES as SECURITY_ACCESS_WAVE4_CASES
from .specialty_boundary import CASES as SPECIALTY_BOUNDARY_CASES
from .specialty_boundary_wave4 import CASES as SPECIALTY_BOUNDARY_WAVE4_CASES
from .tools_machinery import CASES as TOOLS_MACHINERY_CASES
from .wellness_boundary import CASES as WELLNESS_BOUNDARY_CASES
from .wellness_boundary_wave4 import CASES as WELLNESS_BOUNDARY_WAVE4_CASES

MATCHING_QUALITY_GROUPS: dict[str, tuple[MatchingQualityCase, ...]] = {
    "household_core": HOUSEHOLD_CASES,
    "kitchen_beverage": KITCHEN_BEVERAGE_CASES,
    "climate_water": CLIMATE_WATER_CASES,
    "personal_care": PERSONAL_CARE_CASES,
    "office_peripherals": OFFICE_PERIPHERALS_CASES + OFFICE_PERIPHERALS_WAVE4_CASES,
    "networking": NETWORKING_CASES + NETWORKING_WAVE4_CASES,
    "security_access": SECURITY_ACCESS_CASES + SECURITY_ACCESS_WAVE4_CASES,
    "power_charging": POWER_CHARGING_CASES + POWER_CHARGING_WAVE4_CASES,
    "lighting_optical": LIGHTING_OPTICAL_CASES + LIGHTING_OPTICAL_WAVE4_CASES,
    "tools_machinery": TOOLS_MACHINERY_CASES,
    "ev_micromobility": EV_MICROMOBILITY_CASES,
    "wellness_boundary": WELLNESS_BOUNDARY_CASES + WELLNESS_BOUNDARY_WAVE4_CASES,
    "specialty_boundary": SPECIALTY_BOUNDARY_CASES + SPECIALTY_BOUNDARY_WAVE4_CASES,
    "building_access_controls": BUILDING_ACCESS_CONTROLS_CASES,
    "contrastive_relations": CONTRASTIVE_CASES + CONTRASTIVE_WAVE4_CASES,
}
MATCHING_QUALITY_CASES: tuple[MatchingQualityCase, ...] = tuple(
    case
    for group_cases in MATCHING_QUALITY_GROUPS.values()
    for case in group_cases
)

__all__ = [
    "MATCHING_QUALITY_CASES",
    "MATCHING_QUALITY_GROUPS",
    "MatchingQualityCase",
    "expected_case_family",
]
