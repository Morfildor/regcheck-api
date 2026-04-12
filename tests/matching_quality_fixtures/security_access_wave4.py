from __future__ import annotations

from .base import ambiguous_case, family_case, subtype_case

GROUP = "security_access"

_SUBTYPE_CASES = (
    ("smart_intercom_keypad_camera", "smart intercom with keypad and camera", "ip_intercom", ("contrastive",), ("adversarial",)),
    ("video_intercom_access_panel", "video intercom access panel", "ip_intercom", ("contrastive",), ("adversarial",)),
    ("apartment_entry_intercom_camera_keypad", "apartment entry intercom with camera and keypad", "ip_intercom", ("relation",), ("paraphrase",)),
    ("outdoor_door_station_camera_keypad", "outdoor door station with keypad camera intercom", "ip_intercom", ("relation",), ("organic",)),
    ("intercom_access_panel_gate", "intercom access panel for gate entry", "ip_intercom", ("relation",), ("paraphrase",)),
    ("security_camera_system_poe_recorder", "security camera system with poe recorder", "nvr_dvr_recorder", ("contrastive",), ("adversarial",)),
    ("camera_system_poe_recorder", "camera system with poe recorder", "nvr_dvr_recorder", ("contrastive",), ("adversarial",)),
    ("poe_recorder_for_security_cameras", "poe recorder for security cameras", "nvr_dvr_recorder", ("relation",), ("paraphrase",)),
    ("smoke_alarm_with_carbon_sensor", "smoke alarm with carbon monoxide sensor", "smoke_co_alarm", ("contrastive",), ("adversarial",)),
    ("smart_smoke_alarm_with_carbon_sensor", "smart smoke alarm with carbon monoxide sensor", "smart_smoke_co_alarm", ("contrastive",), ("adversarial",)),
    ("indoor_alarm_keypad_entry_delay", "indoor alarm keypad with display and entry delay", "alarm_keypad_panel", ("relation",), ("organic",)),
    ("baby_monitor_two_way_audio", "baby monitor camera with two way audio", "baby_monitor", ("boundary",), ("paraphrase",)),
    ("panic_scene_button_remote", "panic scene smart button remote", "smart_button_remote", ("boundary",), ("paraphrase",)),
    ("smart_sensor_node_motion_humidity", "smart sensor node with humidity and motion sensing", "smart_sensor_node", ("boundary",), ("organic",)),
    ("door_entry_panel_keypad_camera", "door entry panel with keypad and camera", "ip_intercom", ("boundary", "hybrid"), ("adversarial",)),
    ("gate_keypad_panel_camera_intercom", "gate keypad panel with camera intercom", "ip_intercom", ("boundary", "hybrid"), ("organic",)),
    ("security_recorder_with_storage", "security recorder with poe ports and storage", "nvr_dvr_recorder", ("contrastive", "boundary"), ("organic",)),
)

_FAMILY_CASES = (
    ("video_doorbell_chime_camera", "video doorbell chime camera wifi", "smart_home_security", ("boundary",), ("organic",)),
    ("home_alarm_hub_keypad_siren", "home alarm hub with keypad and siren", "smart_home_security", ("boundary",), ("adversarial",)),
)

_AMBIGUOUS_CASES = (
    ("carbon_monoxide_monitor_display", "carbon monoxide monitor with display", ("contrastive", "boundary"), ("adversarial",)),
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

