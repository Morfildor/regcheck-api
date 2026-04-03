from __future__ import annotations

from .base import family_case, subtype_case

GROUP = "tools_machinery"

CASES = (
    subtype_case(GROUP, "angle_grinder", "angle grinder with side handle", "angle_grinder"),
    family_case(GROUP, "bench_saw", "bench saw for workshop cutting", "industrial_power_equipment", tags=("boundary",)),
    subtype_case(GROUP, "corded_power_drill", "corded power drill with hammer mode", "corded_power_drill"),
    subtype_case(GROUP, "cordless_power_drill", "cordless power drill with battery pack", "cordless_power_drill"),
    subtype_case(GROUP, "electric_garden_tool", "electric garden tool for hedge trimming", "electric_garden_tool"),
    subtype_case(GROUP, "heat_gun", "heat gun for shrink tubing", "heat_gun"),
    subtype_case(GROUP, "high_pressure_cleaner", "high pressure cleaner with spray lance", "high_pressure_cleaner"),
    subtype_case(GROUP, "impact_driver", "impact driver with hex chuck", "impact_driver"),
    subtype_case(GROUP, "lawn_mower", "electric lawn mower with grass box", "lawn_mower"),
    subtype_case(GROUP, "outdoor_barbecue", "outdoor barbecue grill with heating element", "outdoor_barbecue"),
    subtype_case(GROUP, "portable_power_saw", "portable power saw with guard", "portable_power_saw"),
    subtype_case(GROUP, "robotic_lawn_mower", "robotic lawn mower with boundary wire", "robotic_lawn_mower"),
    subtype_case(GROUP, "rotary_hammer", "rotary hammer with sds chuck", "rotary_hammer"),
    family_case(GROUP, "rotary_tool", "rotary tool with engraving accessories", "industrial_power_equipment", tags=("boundary",)),
)
