from __future__ import annotations

from .base import ambiguous_case, family_case, subtype_case

GROUP = "contrastive_relations"

_SUBTYPE_CASES = (
    ("stage_microphone_receiver", "wireless receiver for stage microphones", "wireless_microphone_receiver", ("contrastive",), ("adversarial",)),
    ("poe_camera_recorder", "camera system with poe recorder", "nvr_dvr_recorder", ("contrastive",), ("adversarial",)),
    ("classroom_visualizer_camera", "classroom visualizer projector camera", "document_camera", ("contrastive",), ("adversarial",)),
    ("smart_intercom_gate_panel", "smart intercom with keypad and camera", "ip_intercom", ("contrastive",), ("adversarial",)),
    ("smart_garage_controller", "garage door wifi controller", "garage_door_controller", ("contrastive",), ("adversarial",)),
)

_FAMILY_CASES = (
    ("home_theater_receiver_wireless_mics", "home theater receiver with wireless microphones", "home_entertainment_device", ("contrastive", "family_only"), ("adversarial",)),
    ("poe_switch_for_cameras", "poe switch for cameras", "networking_device", ("contrastive", "family_only"), ("adversarial",)),
    ("home_projector_streaming", "home projector streaming 4k", "projector_device", ("contrastive", "family_only"), ("paraphrase",)),
    ("vanity_mirror_speaker_light", "vanity mirror with speakers and light", "lighting_accessory_device", ("contrastive", "family_only"), ("organic",)),
)

_SUBTYPE_CASES = _SUBTYPE_CASES + (
    ("heated_eye_mask", "heated eye mask rechargeable", "heated_wellness_mask", ("contrastive", "wearable"), ("paraphrase",)),
)

_AMBIGUOUS_CASES = (
    ("audio_eye_mask", "eye mask with bluetooth speakers", ("contrastive",), ("adversarial",)),
    ("carbon_monoxide_monitor_display", "carbon monoxide monitor with display", ("contrastive",), ("adversarial",)),
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

