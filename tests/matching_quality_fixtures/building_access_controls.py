from __future__ import annotations

from .base import family_case, subtype_case

GROUP = "building_access_controls"

_SUBTYPE_CASES = (
    ("garage_door_wifi_controller", "garage door wifi controller", "garage_door_controller", ("contrastive",), ("adversarial",)),
    ("garage_opener_control_module", "garage opener control module", "garage_door_controller", ("contrastive",), ("adversarial",)),
    ("controller_for_garage_door_opener", "controller for garage door opener", "garage_door_controller", ("relation",), ("paraphrase",)),
    ("smart_gate_opener_controller_wifi", "smart gate opener controller wifi", "garage_door_controller", ("contrastive",), ("organic",)),
    ("garage_door_opener_controller_app", "garage door opener controller with app", "garage_door_controller", ("relation",), ("organic",)),
    ("garage_controller_module_opener_motor", "garage controller module for opener motor", "garage_door_controller", ("relation",), ("paraphrase",)),
    ("video_intercom_access_panel", "video intercom access panel", "ip_intercom", ("contrastive",), ("adversarial",)),
    ("smart_intercom_keypad_camera", "smart intercom with keypad and camera", "ip_intercom", ("contrastive",), ("adversarial",)),
    ("intercom_access_panel_gate_entry", "intercom access panel for gate entry", "ip_intercom", ("relation",), ("paraphrase",)),
    ("outdoor_door_station_keypad_camera", "outdoor door station with keypad camera intercom", "ip_intercom", ("relation",), ("organic",)),
    ("lighting_gateway_for_smart_bulbs", "lighting gateway for smart bulbs", "smart_light_controller", ("contrastive",), ("adversarial",)),
    ("wall_smart_switch_matter_thread", "wall smart switch matter thread", "smart_switch", ("boundary",), ("organic",)),
    ("din_rail_smart_relay_gate_lights", "din rail smart relay for gate lights", "smart_relay", ("boundary",), ("paraphrase",)),
    ("door_entry_panel_keypad_camera", "door entry panel with keypad and camera", "ip_intercom", ("contrastive", "boundary", "hybrid"), ("adversarial",)),
    ("gate_keypad_panel_camera_intercom", "gate keypad panel with camera intercom", "ip_intercom", ("contrastive", "boundary", "hybrid"), ("paraphrase",)),
)

_FAMILY_CASES = (
    ("home_alarm_hub_keypad_siren", "home alarm hub with keypad and siren", "smart_home_security", ("boundary",), ("organic",)),
    ("access_panel_camera_keypad", "door access panel with camera and keypad", "smart_home_security", ("contrastive", "boundary"), ("organic",)),
    ("zigbee_light_bridge_controller", "zigbee light bridge controller", "smart_power_control", ("contrastive", "boundary"), ("adversarial",)),
    ("smart_lighting_controller_zigbee", "smart lighting controller with zigbee", "smart_power_control", ("contrastive", "boundary"), ("paraphrase",)),
    ("matter_lighting_bridge_controller", "matter lighting bridge controller", "smart_power_control", ("contrastive", "boundary"), ("adversarial",)),
)

CASES = tuple(
    subtype_case(GROUP, name, description, expected_subtype, tags=tags, modes=modes)
    for name, description, expected_subtype, tags, modes in _SUBTYPE_CASES
) + tuple(
    family_case(GROUP, name, description, expected_family, tags=tags, modes=modes)
    for name, description, expected_family, tags, modes in _FAMILY_CASES
)

