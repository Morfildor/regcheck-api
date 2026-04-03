from __future__ import annotations

from .base import family_case, subtype_case

GROUP = "household_core"

CASES = (
    subtype_case(GROUP, "robot_vacuum_lidar", "robot vacuum cleaner with lidar mapping", "robot_vacuum", forbidden_subtypes=("vacuum_cleaner",)),
    subtype_case(GROUP, "robot_mop_floorcare", "robot mop with floor cleaning dock", "robot_mop"),
    subtype_case(GROUP, "vacuum_cleaner_bagless", "bagless vacuum cleaner with cord reel", "vacuum_cleaner", forbidden_subtypes=("robot_vacuum",)),
    subtype_case(GROUP, "washing_machine_front_load", "front load washing machine with inverter motor", "washing_machine"),
    subtype_case(GROUP, "tumble_dryer_heat_pump", "heat pump tumble dryer with sensor drying", "tumble_dryer"),
    subtype_case(GROUP, "steam_cleaner_handheld", "steam cleaner for tile floor and grout", "steam_cleaner"),
    subtype_case(GROUP, "electric_iron_steam", "steam electric iron with ceramic soleplate", "electric_iron"),
    subtype_case(GROUP, "garment_steamer", "garment steamer with hanging rail", "garment_steamer"),
    family_case(GROUP, "fabric_steamer_portable", "portable fabric steamer for clothing", "laundry_textile_appliance", tags=("boundary",)),
    subtype_case(GROUP, "sewing_machine_computerized", "computerized sewing machine with foot pedal", "sewing_machine"),
    subtype_case(GROUP, "smart_indoor_garden", "smart indoor garden with led grow light and app", "smart_indoor_garden"),
    subtype_case(GROUP, "smart_standing_desk", "smart standing desk with memory presets and app", "smart_standing_desk"),
    subtype_case(GROUP, "smart_treadmill", "smart treadmill with bluetooth app and display", "smart_treadmill"),
)
