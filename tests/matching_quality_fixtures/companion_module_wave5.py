from __future__ import annotations

from .base import ambiguous_case, family_case, subtype_case

GROUP = "companion_module"

# ── Access / security companion products ──────────────────────────────────────

_SUBTYPE_CASES_SECURITY = (
    # Doorbell chime receivers (companion — NOT the video doorbell itself)
    ("doorbell_chime_receiver_basic", "doorbell chime receiver for smart video doorbell", "doorbell_chime_receiver", ("companion", "relation"), ("paraphrase",)),
    ("wireless_chime_receiver_doorbell", "wireless chime receiver for doorbell system", "doorbell_chime_receiver", ("companion", "relation"), ("paraphrase",)),
    ("chime_box_doorbell", "wireless chime box for video doorbell", "doorbell_chime_receiver", ("companion",), ("organic",)),
    ("plug_in_chime_unit", "plug in chime unit for smart doorbell", "doorbell_chime_receiver", ("companion", "relation"), ("organic",)),
    ("wireless_chime_box_family", "wireless chime box for doorbell system", "doorbell_chime_receiver", ("companion",), ("organic",)),
    ("doorbell_chime_unit_family", "doorbell chime unit plug in", "doorbell_chime_receiver", ("companion",), ("organic",)),
    # Intercom entry panels
    ("apartment_entry_panel_camera", "apartment intercom entry panel with keypad", "ip_intercom", ("companion",), ("paraphrase",)),
    ("apartment_entry_panel_family", "apartment entry system panel with video intercom", "ip_intercom", ("companion",), ("paraphrase",)),
    # Smart home relay modules
    ("smart_relay_control_module", "smart relay control module wifi", "smart_relay_module", ("companion",), ("paraphrase",)),
    ("relay_module_basic", "wifi relay module for home automation", "smart_relay_module", ("companion", "relation"), ("organic",)),
    ("control_relay_module", "remote control relay module smart home", "smart_relay_module", ("companion",), ("organic",)),
    ("gate_controller_relay_wifi", "smart gate controller with wifi relay", "smart_relay_module", ("companion",), ("organic",)),
)

_FAMILY_CASES_SECURITY = (
    # Chime receiver — family-only stop is expected
    # Generic smart-home security companions
    ("smart_lock_bridge_gateway", "smart lock bridge gateway", "networking_device", ("companion",), ("adversarial",)),
    ("lock_gateway_bridge_bt", "lock gateway bridge for bluetooth door lock", "networking_device", ("companion", "relation"), ("adversarial",)),
    ("smart_lock_wifi_bridge", "smart lock wifi bridge adapter", "networking_device", ("companion",), ("paraphrase",)),
    # Entry panels at family level
    ("door_entry_panel_keypad_camera2", "building entry panel with keypad and camera", "smart_home_security", ("companion",), ("organic",)),
    # Smart home relay / gate (family level for ambiguous gate cases)
)

# ── EV / energy companion modules ───────────────────────────────────────────

_FAMILY_CASES_EV = (
    ("wallbox_load_balancing_module", "wallbox load balancing meter module", "energy_power_system", ("companion", "family_only"), ("adversarial",)),
    ("din_rail_ev_meter", "din rail energy meter for ev charger load balancing", "energy_power_system", ("companion", "relation", "family_only"), ("adversarial",)),
    ("ev_load_management_module", "ev load management module for home charger", "energy_power_system", ("companion", "relation", "family_only"), ("paraphrase",)),
    ("ev_metering_module", "ev energy meter module for wallbox", "energy_power_system", ("companion", "relation", "family_only"), ("organic",)),
    ("smart_ev_load_balancer", "smart ev load balancer din rail", "energy_power_system", ("companion", "family_only"), ("organic",)),
)

# ── Heating / wellness companion accessories ─────────────────────────────────

_FAMILY_CASES_HEATING = (
    ("electric_underblanket_controller", "electric underblanket controller", "personal_heating_appliance", ("companion", "family_only"), ("adversarial",)),
    ("heated_blanket_controller", "heated blanket temperature controller", "personal_heating_appliance", ("companion", "family_only"), ("adversarial",)),
    ("blanket_controller_accessory", "electric blanket controller unit", "personal_heating_appliance", ("companion", "family_only"), ("organic",)),
    ("warm_blanket_temp_control", "warm blanket controller with temperature settings", "personal_heating_appliance", ("companion", "family_only"), ("paraphrase",)),
    ("underblanket_thermostat", "electric underblanket with separate thermostat controller", "personal_heating_appliance", ("companion", "family_only"), ("organic",)),
)

_SUBTYPE_CASES_HEATING = (
    # Electric shower / instant water heaters — NOT room heaters
    ("electric_shower_water_heater", "electric shower water heater", "electric_shower_heater", ("companion",), ("adversarial",)),
    ("instant_shower_heater", "instant shower heater wall mounted", "electric_shower_heater", ("companion",), ("adversarial",)),
    ("instantaneous_water_heater", "instantaneous water heater electric", "electric_shower_heater", ("companion",), ("paraphrase",)),
    ("electric_shower_unit", "electric shower heater unit", "electric_shower_heater", ("companion",), ("organic",)),
    ("wall_shower_heater", "wall mounted electric shower heater 9kw", "electric_shower_heater", ("companion",), ("organic",)),
    ("instant_electric_shower", "instant electric shower 8.5kw", "electric_shower_heater", ("companion",), ("organic",)),
)

# ── Display / computing hybrids ───────────────────────────────────────────────

_FAMILY_CASES_HYBRID = (
    ("all_in_one_desktop_display", "all in one desktop display computer", "personal_computing_device", ("hybrid", "family_only"), ("paraphrase",)),
    ("all_in_one_business", "business all-in-one pc with touch display", "personal_computing_device", ("hybrid", "family_only"), ("organic",)),
    ("touchscreen_all_in_one", "touchscreen all in one desktop computer", "personal_computing_device", ("hybrid", "family_only"), ("organic",)),
    ("display_integrated_computer", "desktop display with integrated computer unit", "personal_computing_device", ("hybrid", "family_only"), ("adversarial",)),
)

_SUBTYPE_CASES_HYBRID = (
)

# ── UPS / battery backup companion units ────────────────────────────────────

_FAMILY_CASES_UPS = (
    ("ups_battery_backup_module", "ups battery backup module", "energy_power_system", ("companion", "family_only"), ("paraphrase",)),
    ("ups_network_management_card", "ups network management card", "energy_power_system", ("companion", "family_only"), ("adversarial",)),
    ("ups_monitoring_module", "ups monitoring module for server rack", "energy_power_system", ("companion", "relation", "family_only"), ("organic",)),
    ("ups_companion_generic", "battery backup control unit for rack", "energy_power_system", ("companion", "family_only"), ("adversarial",)),
)

# ── Smart-home bridges and gateways (companion, not main device) ─────────────

_FAMILY_CASES_BRIDGE = (
    ("zigbee_bridge_smart_home", "zigbee bridge for smart home devices", "networking_device", ("companion", "family_only", "relation"), ("paraphrase",)),
    ("matter_bridge_gateway", "matter bridge gateway for smart home", "networking_device", ("companion", "family_only"), ("organic",)),
    ("zwave_gateway_home", "z-wave gateway for home automation", "networking_device", ("companion", "family_only"), ("organic",)),
    ("smart_home_bridge_hub", "smart home bridge hub for automation devices", "networking_device", ("companion", "family_only"), ("paraphrase",)),
)

_SUBTYPE_CASES_BRIDGE = (
    ("iot_gateway_basic", "iot gateway hub smart home", "iot_gateway", ("companion",), ("paraphrase",)),
    ("smart_home_gateway", "smart home gateway hub", "iot_gateway", ("companion",), ("paraphrase",)),
    ("thread_border_router", "thread border router smart home bridge", "router", ("companion",), ("organic",)),
)

# ── Thermostat / HVAC companion controllers ──────────────────────────────────

_FAMILY_CASES_THERMOSTAT = (
    ("smart_thermostat_manifold", "smart thermostat manifold controller", "hvac_control", ("companion", "family_only"), ("adversarial",)),
    ("underfloor_heating_controller", "underfloor heating controller multizone", "hvac_control", ("companion", "family_only"), ("organic",)),
    ("zone_valve_controller", "zone valve controller for underfloor heating", "hvac_control", ("companion", "relation", "family_only"), ("organic",)),
    ("heating_manifold_controller", "heating manifold controller with wifi", "hvac_control", ("companion", "family_only"), ("paraphrase",)),
)

# ── Irrigation / garden companion controllers ─────────────────────────────────

_SUBTYPE_CASES_IRRIGATION = ()

# Irrigation controllers stay at family level due to specialty agricultural boundary
_FAMILY_CASES_IRRIGATION = (
    ("smart_irrigation_controller", "smart irrigation controller wifi", "agricultural_appliance", ("companion", "family_only"), ("paraphrase",)),
    ("irrigation_pump_wifi", "irrigation pump controller with wifi", "agricultural_appliance", ("companion", "family_only"), ("organic",)),
    ("garden_watering_controller", "garden watering controller smart", "agricultural_appliance", ("companion", "family_only"), ("organic",)),
    ("sprinkler_controller_wifi", "wifi sprinkler controller 6 zone", "agricultural_appliance", ("companion", "family_only"), ("organic",)),
)

# ── Intercom / panel hybrids ──────────────────────────────────────────────────

_SUBTYPE_CASES_INTERCOM = (
    ("intercom_panel_camera_keypad", "intercom panel with camera and keypad access control", "ip_intercom", ("hybrid", "companion"), ("adversarial",)),
    ("access_entry_intercom_panel", "access entry intercom panel with video call", "ip_intercom", ("hybrid", "companion"), ("organic",)),
    ("hybrid_intercom_display", "smart intercom display panel with home screen", "ip_intercom", ("hybrid",), ("adversarial",)),
)

_FAMILY_CASES_INTERCOM = (
    ("smart_entry_panel_keypad", "smart entry panel with keypad and camera", "smart_home_security", ("companion", "family_only"), ("organic",)),
)

# ── Must-not-overmatch contrastive cases ─────────────────────────────────────

_SUBTYPE_CASES_CONTRASTIVE = (
    ("must_not_be_room_heater", "instant shower water heater wall mount", "electric_shower_heater",
     ("companion",), ("adversarial",)),
    ("must_not_be_video_doorbell", "doorbell chime receiver wireless plug in", "doorbell_chime_receiver",
     ("companion",), ("adversarial",)),
)

_FAMILY_CASES_CONTRASTIVE = (
    # smart lock bridge ≠ smart_lock → must be networking_device
    ("must_not_be_smart_lock", "smart lock bridge gateway bluetooth", "networking_device",
     ("companion", "family_only"), ("adversarial",)),
    # ev load module ≠ ev_charger_home → must be energy_power_system
    ("must_not_be_ev_charger", "wallbox load balancing meter module companion", "energy_power_system",
     ("companion", "family_only"), ("adversarial",)),
    # shower heater ≠ room_heater → water_heating_appliance family (subtype resolves further)
    # underblanket controller ≠ room_heater → personal_heating_appliance
    ("must_not_be_room_heater_blanket", "electric underblanket controller unit", "personal_heating_appliance",
     ("companion", "family_only"), ("adversarial",)),
    # chime receiver ≠ video doorbell → smart_home_security
)

_AMBIGUOUS_CASES = (
    ("video_entry_panel", "video entry panel with intercom and camera", ("hybrid",), ("paraphrase",)),
    ("smart_door_entry_panel_camera", "smart door entry panel with camera", ("companion",), ("adversarial",)),
    ("gate_opener_control_box", "gate opener control box with relay", ("companion",), ("adversarial",)),
    ("desktop_display_builtin_pc", "desktop display with built in pc", ("hybrid",), ("adversarial",)),
)

# ── Compile all cases ─────────────────────────────────────────────────────────

_ALL_SUBTYPE = (
    _SUBTYPE_CASES_SECURITY
    + _SUBTYPE_CASES_HEATING
    + _SUBTYPE_CASES_HYBRID
    + _SUBTYPE_CASES_BRIDGE
    + _SUBTYPE_CASES_IRRIGATION
    + _SUBTYPE_CASES_INTERCOM
    + _SUBTYPE_CASES_CONTRASTIVE
)
_ALL_FAMILY = (
    _FAMILY_CASES_SECURITY
    + _FAMILY_CASES_EV
    + _FAMILY_CASES_HEATING
    + _FAMILY_CASES_HYBRID
    + _FAMILY_CASES_UPS
    + _FAMILY_CASES_BRIDGE
    + _FAMILY_CASES_THERMOSTAT
    + _FAMILY_CASES_IRRIGATION
    + _FAMILY_CASES_INTERCOM
    + _FAMILY_CASES_CONTRASTIVE
)
_ALL_AMBIGUOUS = _AMBIGUOUS_CASES

CASES = (
    tuple(
        subtype_case(GROUP, name, description, expected_subtype, tags=tags, modes=modes)
        for name, description, expected_subtype, tags, modes in _ALL_SUBTYPE
    )
    + tuple(
        family_case(GROUP, name, description, expected_family, tags=tags, modes=modes)
        for name, description, expected_family, tags, modes in _ALL_FAMILY
    )
    + tuple(
        ambiguous_case(GROUP, name, description, tags=tags, modes=modes)
        for name, description, tags, modes in _ALL_AMBIGUOUS
    )
)
