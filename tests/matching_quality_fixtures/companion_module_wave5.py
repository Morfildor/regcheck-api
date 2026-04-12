from __future__ import annotations

from .base import ambiguous_case, family_case, subtype_case

GROUP = "companion_module"

_SUBTYPE_CASES = (
    ("doorbell_chime_receiver_basic", "doorbell chime receiver for smart video doorbell", "doorbell_chime_receiver", ("companion", "relation"), ("paraphrase",)),
    ("wireless_chime_receiver_doorbell", "wireless chime receiver for doorbell system", "doorbell_chime_receiver", ("companion", "relation"), ("paraphrase",)),
    ("chime_box_doorbell", "wireless chime box for video doorbell", "doorbell_chime_receiver", ("companion",), ("organic",)),
    ("plug_in_chime_unit", "plug in chime unit for smart doorbell", "doorbell_chime_receiver", ("companion", "relation"), ("organic",)),
    ("apartment_entry_panel_camera", "apartment intercom entry panel with keypad", "ip_intercom", ("companion", "hybrid"), ("paraphrase",)),
    ("apartment_entry_panel_family", "apartment entry system panel with video intercom", "ip_intercom", ("companion", "hybrid"), ("paraphrase",)),
    ("intercom_panel_camera_keypad", "intercom panel with camera and keypad access control", "ip_intercom", ("companion", "hybrid"), ("adversarial",)),
    ("access_entry_intercom_panel", "access entry intercom panel with video call", "ip_intercom", ("companion", "hybrid"), ("organic",)),
    ("video_entry_panel", "video entry panel with intercom and camera", "ip_intercom", ("hybrid",), ("paraphrase",)),
    ("smart_door_entry_panel_camera", "smart door entry panel with camera", "ip_intercom", ("companion", "hybrid"), ("adversarial",)),
    ("smart_relay_control_module", "smart relay control module wifi", "smart_relay_module", ("companion",), ("paraphrase",)),
    ("relay_module_basic", "wifi relay module for home automation", "smart_relay_module", ("companion", "relation"), ("organic",)),
    ("control_relay_module", "remote control relay module smart home", "smart_relay_module", ("companion",), ("organic",)),
    ("gate_controller_relay_wifi", "smart gate controller with wifi relay", "smart_relay_module", ("companion",), ("organic",)),
    ("smart_lock_bridge_gateway", "smart lock bridge gateway", "iot_gateway", ("companion", "contrastive"), ("adversarial",)),
    ("lock_gateway_bridge_bt", "lock gateway bridge for bluetooth door lock", "iot_gateway", ("companion", "relation"), ("adversarial",)),
    ("smart_lock_wifi_bridge", "smart lock wifi bridge adapter", "iot_gateway", ("companion",), ("paraphrase",)),
    ("zigbee_bridge_smart_home", "zigbee bridge for smart home devices", "iot_gateway", ("companion",), ("paraphrase",)),
    ("matter_bridge_gateway", "matter bridge gateway for smart home", "iot_gateway", ("companion",), ("organic",)),
    ("smart_home_bridge_hub", "smart home bridge hub for automation devices", "iot_gateway", ("companion",), ("paraphrase",)),
    ("iot_gateway_basic", "iot gateway hub smart home", "iot_gateway", ("companion",), ("paraphrase",)),
    ("smart_home_gateway", "smart home gateway hub", "iot_gateway", ("companion",), ("paraphrase",)),
    ("wallbox_load_balancing_module", "wallbox load balancing meter module", "ev_energy_module", ("companion", "contrastive"), ("adversarial",)),
    ("ev_load_management_module", "ev load management module", "ev_energy_module", ("companion", "relation"), ("paraphrase",)),
    ("ev_metering_module", "ev energy meter module for wallbox", "ev_energy_module", ("companion", "relation"), ("organic",)),
    ("smart_ev_load_balancer", "smart ev load balancer din rail", "ev_energy_module", ("companion",), ("organic",)),
    ("all_in_one_desktop_display", "all in one desktop display computer", "all_in_one_pc", ("hybrid",), ("paraphrase",)),
    ("all_in_one_business", "business all-in-one pc with touch display", "all_in_one_pc", ("hybrid",), ("organic",)),
    ("touchscreen_all_in_one", "touchscreen all in one desktop computer", "all_in_one_pc", ("hybrid",), ("organic",)),
    ("desktop_display_builtin_pc", "desktop display with built in pc", "all_in_one_pc", ("hybrid",), ("adversarial",)),
    ("electric_shower_water_heater", "electric shower water heater", "electric_shower_heater", ("contrastive",), ("adversarial",)),
    ("instant_shower_heater", "instant shower heater wall mounted", "electric_shower_heater", ("contrastive",), ("adversarial",)),
    ("instantaneous_water_heater", "instantaneous water heater electric", "electric_shower_heater", ("contrastive",), ("paraphrase",)),
    ("must_not_be_smart_lock", "smart lock bridge gateway bluetooth", "iot_gateway", ("companion", "contrastive"), ("adversarial",)),
    ("must_not_be_ev_charger", "wallbox load balancing meter module companion", "ev_energy_module", ("companion", "contrastive"), ("adversarial",)),
)

_FAMILY_CASES = (
    ("charger_companion_module_family", "charger companion module for wallbox", "energy_power_system", ("companion", "family_only"), ("organic",)),
    ("din_rail_ev_meter", "din rail energy meter for ev charger load balancing", "energy_power_system", ("companion", "family_only"), ("adversarial",)),
    ("electric_underblanket_controller", "electric underblanket controller", "personal_heating_appliance", ("companion", "family_only"), ("adversarial",)),
    ("heated_blanket_controller", "heated blanket temperature controller", "personal_heating_appliance", ("companion", "family_only"), ("adversarial",)),
    ("blanket_controller_accessory", "electric blanket controller unit", "personal_heating_appliance", ("companion", "family_only"), ("organic",)),
    ("underblanket_thermostat", "electric underblanket with separate thermostat controller", "personal_heating_appliance", ("companion", "family_only"), ("organic",)),
    ("ups_battery_backup_module", "ups battery backup module", "energy_power_system", ("companion", "family_only"), ("paraphrase",)),
    ("ups_network_management_card", "ups network management card", "energy_power_system", ("companion", "family_only"), ("adversarial",)),
    ("ups_monitoring_module", "ups monitoring module for server rack", "energy_power_system", ("companion", "family_only"), ("organic",)),
    ("ups_companion_generic", "battery backup control unit for rack", "energy_power_system", ("companion", "family_only"), ("adversarial",)),
    ("zwave_gateway_home", "z-wave gateway for home automation", "networking_device", ("companion", "family_only"), ("organic",)),
    ("smart_thermostat_manifold", "smart thermostat manifold controller", "hvac_control", ("companion", "family_only"), ("adversarial",)),
    ("underfloor_heating_controller", "underfloor heating controller multizone", "hvac_control", ("companion", "family_only"), ("organic",)),
    ("zone_valve_controller", "zone valve controller for underfloor heating", "hvac_control", ("companion", "relation", "family_only"), ("organic",)),
    ("heating_manifold_controller", "heating manifold controller with wifi", "hvac_control", ("companion", "family_only"), ("paraphrase",)),
    ("smart_irrigation_controller", "smart irrigation controller wifi", "agricultural_appliance", ("companion", "family_only"), ("paraphrase",)),
    ("irrigation_pump_wifi", "irrigation pump controller with wifi", "agricultural_appliance", ("companion", "family_only"), ("organic",)),
    ("garden_watering_controller", "garden watering controller smart", "agricultural_appliance", ("companion", "family_only"), ("organic",)),
    ("sprinkler_controller_wifi", "wifi sprinkler controller 6 zone", "agricultural_appliance", ("companion", "family_only"), ("organic",)),
)

_AMBIGUOUS_CASES = (
    ("gate_opener_control_box", "gate opener control box with relay", ("companion",), ("adversarial",)),
    ("display_integrated_computer", "desktop display with integrated computer unit", ("hybrid",), ("adversarial",)),
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
