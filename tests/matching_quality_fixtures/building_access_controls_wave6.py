from __future__ import annotations

from .base import ambiguous_case, family_case, subtype_case

GROUP = "building_access_controls"

_SUBTYPE_CASES = (
    ("smart_lock_bridge_for_bluetooth_door_lock", "smart lock bridge for bluetooth door lock", "iot_gateway", ("companion", "contrastive"), ("organic",)),
    ("bluetooth_lock_gateway_bridge", "bluetooth lock gateway bridge", "iot_gateway", ("companion", "contrastive"), ("paraphrase",)),
    ("smart_lock_bridge_gateway_bluetooth", "smart lock bridge gateway bluetooth", "iot_gateway", ("companion", "contrastive"), ("adversarial",)),
    ("lock_bridge_gateway_for_deadbolt", "lock bridge gateway for smart deadbolt", "iot_gateway", ("companion", "relation"), ("organic",)),
    ("door_entry_panel_camera_keypad", "door entry panel with camera and keypad", "ip_intercom", ("hybrid", "contrastive"), ("organic",)),
    ("access_keypad_intercom_panel", "access keypad intercom panel", "ip_intercom", ("hybrid", "contrastive"), ("paraphrase",)),
    ("gate_access_keypad_camera_intercom", "gate access keypad with camera intercom", "ip_intercom", ("hybrid", "contrastive"), ("organic",)),
    ("video_entry_panel_keypad", "video entry panel with keypad intercom", "ip_intercom", ("hybrid", "contrastive"), ("paraphrase",)),
    ("outdoor_intercom_keypad_camera_panel", "outdoor intercom keypad camera panel", "ip_intercom", ("hybrid", "contrastive"), ("organic",)),
    ("camera_intercom_access_panel", "camera intercom access panel", "ip_intercom", ("hybrid", "contrastive"), ("paraphrase",)),
    ("entry_intercom_with_keypad_camera", "entry intercom with keypad camera", "ip_intercom", ("hybrid", "relation"), ("paraphrase",)),
    ("door_station_intercom_panel", "door station intercom panel with keypad", "ip_intercom", ("hybrid", "relation"), ("organic",)),
    ("gate_entry_intercom_panel", "gate entry intercom panel", "ip_intercom", ("hybrid",), ("organic",)),
    ("garage_opener_control_module", "garage opener control module", "garage_door_controller", ("companion", "contrastive"), ("organic",)),
    ("garage_door_wifi_controller", "garage door wifi controller", "garage_door_controller", ("contrastive",), ("paraphrase",)),
    ("controller_for_garage_door_opener", "controller for garage door opener", "garage_door_controller", ("relation",), ("paraphrase",)),
    ("smart_gate_opener_controller_wifi", "smart gate opener controller wifi", "garage_door_controller", ("contrastive",), ("organic",)),
    ("garage_door_opener_controller_app", "garage door opener controller with app", "garage_door_controller", ("relation",), ("organic",)),
    ("garage_controller_module_for_opener", "garage controller module for opener motor", "garage_door_controller", ("relation",), ("paraphrase",)),
    ("garage_opener_module_wifi", "garage opener module with wifi", "garage_door_controller", ("companion",), ("organic",)),
    ("gate_opener_control_module", "gate opener control module", "garage_door_controller", ("companion",), ("paraphrase",)),
    ("doorbell_chime_receiver", "doorbell chime receiver", "doorbell_chime_receiver", ("companion",), ("organic",)),
    ("wireless_doorbell_chime_receiver", "wireless doorbell chime receiver", "doorbell_chime_receiver", ("companion", "contrastive"), ("paraphrase",)),
    ("plug_in_chime_receiver_for_doorbell", "plug in chime receiver for video doorbell", "doorbell_chime_receiver", ("companion", "relation"), ("organic",)),
    ("camera_panel_for_gate", "camera intercom panel for gate", "ip_intercom", ("hybrid", "contrastive"), ("adversarial",)),
)

_FAMILY_CASES = (
    ("wifi_bridge_for_smart_lock", "wifi bridge for smart lock", "networking_device", ("family_only", "companion"), ("organic",)),
    ("building_entry_panel_keypad_camera", "building entry panel with keypad and camera", "smart_home_security", ("family_only", "boundary"), ("organic",)),
)

_AMBIGUOUS_CASES = (
    ("gate_access_control_panel", "gate access control panel", ("boundary", "contrastive"), ("adversarial",)),
    ("door_entry_access_system", "door entry access system", ("boundary", "contrastive"), ("adversarial",)),
    ("entry_panel_access_terminal", "entry panel access terminal", ("boundary", "contrastive"), ("adversarial",)),
    ("smart_access_module", "smart access module", ("boundary", "contrastive"), ("adversarial",)),
)

CASES = tuple(
    subtype_case(GROUP, name, description, expected_subtype, tags=tags, modes=modes)
    for name, description, expected_subtype, tags, modes in _SUBTYPE_CASES
) + tuple(
    family_case(GROUP, name, description, expected_family, tags=tags, modes=modes)
    for name, description, expected_family, tags, modes in _FAMILY_CASES
) + tuple(
    ambiguous_case(GROUP, name, description, tags=tags, modes=modes)
    for name, description, tags, modes in _AMBIGUOUS_CASES
)
