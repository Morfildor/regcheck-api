from __future__ import annotations

from .base import ambiguous_case, family_case, subtype_case

GROUP = "contrastive_relations"

_SUBTYPE_CASES = (
    ("electric_shower_heater_not_room", "electric shower water heater wall mounted", "electric_shower_heater", ("contrastive",), ("adversarial",)),
    ("instant_shower_heater_not_room", "instant shower heater 10kw", "electric_shower_heater", ("contrastive",), ("adversarial",)),
    ("shower_heater_not_room_heater", "electric shower water heater", "electric_shower_heater", ("contrastive",), ("adversarial",)),
    ("instant_heater_not_room_heater", "instant shower heater wall mounted", "electric_shower_heater", ("contrastive",), ("adversarial",)),
    ("chime_receiver_not_doorbell", "doorbell chime receiver wireless", "doorbell_chime_receiver", ("contrastive", "companion"), ("adversarial",)),
    ("wireless_chime_not_doorbell", "wireless chime box for video doorbell", "doorbell_chime_receiver", ("contrastive", "companion"), ("adversarial",)),
    ("smart_relay_not_generic_module", "smart relay control module with wifi", "smart_relay_module", ("contrastive", "companion"), ("paraphrase",)),
    ("smart_lock_bridge_to_iot_gateway", "iot gateway hub smart lock bridge", "iot_gateway", ("contrastive", "companion"), ("adversarial",)),
    ("lock_bridge_not_smart_lock", "smart lock bridge gateway", "iot_gateway", ("contrastive", "companion"), ("adversarial",)),
    ("bt_lock_bridge_not_lock", "bluetooth lock bridge for smart door lock", "iot_gateway", ("contrastive", "companion"), ("adversarial",)),
    ("ev_module_not_charger", "wallbox load balancing meter module", "ev_energy_module", ("contrastive", "companion"), ("adversarial",)),
    ("all_in_one_from_aio_phrase", "all in one pc with touchscreen display", "all_in_one_pc", ("contrastive", "hybrid"), ("paraphrase",)),
    ("all_in_one_display_not_monitor", "all in one desktop display computer", "all_in_one_pc", ("contrastive", "hybrid"), ("paraphrase",)),
    ("display_builtin_pc_not_monitor", "desktop display with built in pc", "all_in_one_pc", ("contrastive", "hybrid"), ("adversarial",)),
    ("entry_panel_not_display", "smart door entry panel with camera", "ip_intercom", ("contrastive", "hybrid"), ("adversarial",)),
)

_FAMILY_CASES = (
    ("din_rail_not_charger", "din rail energy meter for ev charger", "energy_power_system", ("contrastive", "family_only"), ("adversarial",)),
    ("underblanket_not_room_heater", "electric underblanket controller", "personal_heating_appliance", ("contrastive", "family_only"), ("adversarial",)),
    ("blanket_controller_not_room_heater", "heated blanket temperature controller unit", "personal_heating_appliance", ("contrastive", "family_only"), ("adversarial",)),
    ("ups_module_family", "ups network management card monitoring", "energy_power_system", ("contrastive", "family_only"), ("adversarial",)),
)

_AMBIGUOUS_CASES = (
    ("eye_mask_with_speakers_wave5", "eye mask with built in bluetooth speakers", ("contrastive",), ("adversarial",)),
)

CASES = (
    tuple(
        subtype_case(GROUP, name, description, expected_subtype, tags=tags, modes=modes)
        for name, description, expected_subtype, tags, modes in _SUBTYPE_CASES
    )
    + tuple(
        family_case(GROUP, name, description, expected_family, tags=tags, modes=modes)
        for name, description, expected_family, tags, modes in _FAMILY_CASES
    )
    + tuple(
        ambiguous_case(GROUP, name, description, tags=tags, modes=modes)
        for name, description, tags, modes in _AMBIGUOUS_CASES
    )
)
