from __future__ import annotations

from .base import family_case, subtype_case

GROUP = "personal_care"

CASES = (
    subtype_case(GROUP, "beauty_treatment_appliance", "beauty treatment appliance for facial cleansing", "beauty_treatment_appliance"),
    subtype_case(GROUP, "electric_blanket_dual_control", "electric blanket with dual control", "electric_blanket"),
    subtype_case(GROUP, "foot_warmer_plush", "plush foot warmer with heat settings", "foot_warmer"),
    subtype_case(GROUP, "hair_clipper_cordless", "cordless hair clipper with guide comb", "hair_clipper"),
    subtype_case(GROUP, "hair_curler_ionic", "ionic hair curler wand with ceramic barrel", "hair_curler"),
    subtype_case(GROUP, "heating_pad_moist", "moist heating pad for neck and shoulders", "heating_pad"),
    subtype_case(GROUP, "oral_hygiene_appliance", "cordless oral hygiene appliance with water tank", "oral_hygiene_appliance"),
    subtype_case(GROUP, "shaver_wet_dry", "wet dry electric shaver with charging stand", "shaver"),
    family_case(GROUP, "skin_hair_care_appliance", "skin hair care appliance with led facial mode", "personal_care_appliance", tags=("boundary",)),
    family_case(GROUP, "ultraviolet_appliance_nail", "uv nail lamp with timer for gel polish", "optical_beauty_device", tags=("boundary",)),
)
