from __future__ import annotations

from .base import ambiguous_case, family_case, subtype_case

GROUP = "contrastive_relations"

# Wave 5 contrastive cases: companion vs main device, hybrid vs single-role,
# water-heater vs room-heater, EV module vs EV charger.

_SUBTYPE_CASES = (
    # Electric shower heater must NOT be room_heater
    ("electric_shower_heater_not_room", "electric shower water heater wall mounted", "electric_shower_heater",
     ("contrastive",), ("adversarial",)),
    ("instant_shower_heater_not_room", "instant shower heater 10kw", "electric_shower_heater",
     ("contrastive",), ("adversarial",)),
    # Shower heater ≠ room_heater — resolves to electric_shower_heater subtype
    ("shower_heater_not_room_heater", "electric shower water heater", "electric_shower_heater",
     ("contrastive",), ("adversarial",)),
    ("instant_heater_not_room_heater", "instant shower heater wall mounted", "electric_shower_heater",
     ("contrastive",), ("adversarial",)),
    # Chime receiver ≠ video doorbell — resolves to doorbell_chime_receiver subtype
    ("chime_receiver_not_doorbell", "doorbell chime receiver wireless", "doorbell_chime_receiver",
     ("contrastive",), ("adversarial",)),
    ("wireless_chime_not_doorbell", "wireless chime box for video doorbell", "doorbell_chime_receiver",
     ("contrastive",), ("adversarial",)),
    # Smart relay module
    ("smart_relay_not_generic_module", "smart relay control module with wifi", "smart_relay_module",
     ("contrastive",), ("paraphrase",)),
    # Smart lock bridge resolves to iot_gateway
    ("smart_lock_bridge_to_iot_gateway", "iot gateway hub smart lock bridge", "iot_gateway",
     ("contrastive",), ("adversarial",)),
    # All-in-one PC from display-PC hybrid wording
)

_FAMILY_CASES = (
    # Bridge/gateway for lock ≠ smart_lock — family must be networking_device
    ("lock_bridge_not_smart_lock", "smart lock bridge gateway", "networking_device",
     ("contrastive", "family_only"), ("adversarial",)),
    ("bt_lock_bridge_not_lock", "bluetooth lock bridge for smart door lock", "networking_device",
     ("contrastive", "family_only"), ("adversarial",)),
    # EV load-balancing module ≠ ev_charger_home
    ("ev_module_not_charger", "wallbox load balancing meter module", "energy_power_system",
     ("contrastive", "family_only"), ("adversarial",)),
    ("din_rail_not_charger", "din rail energy meter for ev charger", "energy_power_system",
     ("contrastive", "family_only"), ("adversarial",)),
    # Underblanket controller ≠ room_heater — family must be personal_heating_appliance
    ("underblanket_not_room_heater", "electric underblanket controller", "personal_heating_appliance",
     ("contrastive", "family_only"), ("adversarial",)),
    ("blanket_controller_not_room_heater", "heated blanket temperature controller unit", "personal_heating_appliance",
     ("contrastive", "family_only"), ("adversarial",)),
    # UPS module ≠ standalone UPS
    ("ups_module_family", "ups network management card monitoring", "energy_power_system",
     ("contrastive", "family_only"), ("adversarial",)),
    # Display with built-in PC → personal_computing_device family (not plain monitor)
    ("all_in_one_display_not_monitor", "all in one desktop display computer", "personal_computing_device",
     ("contrastive", "family_only", "hybrid"), ("paraphrase",)),
    ("all_in_one_from_aio_phrase", "all in one pc with large display", "personal_computing_device",
     ("contrastive", "family_only", "hybrid"), ("paraphrase",)),
)

_AMBIGUOUS_CASES = (
    # Desktop-display-with-built-in-PC phrasing can ambiguously describe a monitor or an AIO
    ("display_builtin_pc_not_monitor", "desktop display with built in pc", ("contrastive", "hybrid"), ("adversarial",)),
    # Smart door entry panel — ambiguous between intercom and projector/display
    ("entry_panel_not_display", "smart door entry panel with camera", ("contrastive",), ("adversarial",)),
    # Audio-enabled eye mask — not obvious which wins
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
