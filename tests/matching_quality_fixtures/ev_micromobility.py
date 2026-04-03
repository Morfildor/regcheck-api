from __future__ import annotations

from .base import subtype_case

GROUP = "ev_micromobility"

CASES = (
    subtype_case(GROUP, "electric_bicycle_city", "electric bicycle with pedal assist and battery", "electric_bicycle"),
    subtype_case(GROUP, "electric_cargo_bike", "electric cargo bike with rear motor", "electric_cargo_bike"),
    subtype_case(GROUP, "electric_scooter_foldable", "foldable electric scooter with display", "electric_scooter"),
    subtype_case(GROUP, "electric_skateboard", "electric skateboard with remote controller", "electric_skateboard"),
    subtype_case(GROUP, "electric_unicycle", "electric unicycle with self balancing control", "electric_unicycle"),
    subtype_case(GROUP, "ev_charger_home_wallbox", "home ev charger wallbox with tethered cable", "ev_charger_home"),
    subtype_case(GROUP, "ev_connector_accessory", "type 2 vehicle connector tethered charging cable accessory", "ev_connector_accessory", forbidden_subtypes=("portable_ev_charger",)),
    subtype_case(GROUP, "hoverboard_led", "hoverboard with led lighting and self balance", "hoverboard"),
    subtype_case(GROUP, "portable_ev_charger", "portable ev charger with mode 2 cable and in cable protection device", "portable_ev_charger", forbidden_subtypes=("ev_connector_accessory",)),
    subtype_case(GROUP, "ebike_with_charger", "ebike with charger and removable battery", "electric_bicycle", tags=("contrastive", "relation")),
)
