from __future__ import annotations

from .base import MatchingQualityCase, expected_case_family
from .climate_water import CASES as CLIMATE_WATER_CASES
from .contrastive import CASES as CONTRASTIVE_CASES
from .ev_micromobility import CASES as EV_MICROMOBILITY_CASES
from .household import CASES as HOUSEHOLD_CASES
from .kitchen_beverage import CASES as KITCHEN_BEVERAGE_CASES
from .lighting_optical import CASES as LIGHTING_OPTICAL_CASES
from .networking import CASES as NETWORKING_CASES
from .office_peripherals import CASES as OFFICE_PERIPHERALS_CASES
from .personal_care import CASES as PERSONAL_CARE_CASES
from .power_charging import CASES as POWER_CHARGING_CASES
from .security_access import CASES as SECURITY_ACCESS_CASES
from .specialty_boundary import CASES as SPECIALTY_BOUNDARY_CASES
from .tools_machinery import CASES as TOOLS_MACHINERY_CASES
from .wellness_boundary import CASES as WELLNESS_BOUNDARY_CASES

MATCHING_QUALITY_GROUPS: dict[str, tuple[MatchingQualityCase, ...]] = {
    "household_core": HOUSEHOLD_CASES,
    "kitchen_beverage": KITCHEN_BEVERAGE_CASES,
    "climate_water": CLIMATE_WATER_CASES,
    "personal_care": PERSONAL_CARE_CASES,
    "office_peripherals": OFFICE_PERIPHERALS_CASES,
    "networking": NETWORKING_CASES,
    "security_access": SECURITY_ACCESS_CASES,
    "power_charging": POWER_CHARGING_CASES,
    "lighting_optical": LIGHTING_OPTICAL_CASES,
    "tools_machinery": TOOLS_MACHINERY_CASES,
    "ev_micromobility": EV_MICROMOBILITY_CASES,
    "wellness_boundary": WELLNESS_BOUNDARY_CASES,
    "specialty_boundary": SPECIALTY_BOUNDARY_CASES,
    "contrastive_relations": CONTRASTIVE_CASES,
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
