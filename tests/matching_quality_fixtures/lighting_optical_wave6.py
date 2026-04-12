from __future__ import annotations

from .base import ambiguous_case, family_case, subtype_case

GROUP = "lighting_optical"

_SUBTYPE_CASES = (
    ("plant_grow_light_strip", "plant grow light strip", "grow_light", ("contrastive", "hybrid"), ("organic",)),
    ("led_grow_strip_for_plants", "led grow strip for plants", "grow_light", ("relation", "contrastive"), ("paraphrase",)),
    ("grow_light_bar_for_seedlings", "grow light bar for seedlings", "grow_light", ("contrastive",), ("organic",)),
    ("grow_lamp_strip_for_indoor_plants", "grow lamp strip for indoor plants", "grow_light", ("contrastive",), ("paraphrase",)),
    ("horticulture_light_strip", "horticulture light strip", "grow_light", ("contrastive",), ("organic",)),
    ("full_spectrum_grow_strip", "full spectrum grow strip for herbs", "grow_light", ("contrastive",), ("paraphrase",)),
    ("ring_light_for_streaming", "ring light for streaming", "ring_light", ("contrastive",), ("organic",)),
    ("studio_light_for_video_calls", "studio light for video calls", "ring_light", ("hybrid", "contrastive"), ("organic",)),
    ("led_studio_light_for_streaming", "led studio light for streaming", "ring_light", ("hybrid", "contrastive"), ("paraphrase",)),
    ("video_conference_light", "video conference light", "ring_light", ("contrastive",), ("paraphrase",)),
    ("desktop_ring_light_for_camera", "desktop ring light for camera", "ring_light", ("relation",), ("organic",)),
    ("smart_mirror_with_display", "smart mirror with display", "smart_mirror", ("hybrid", "contrastive"), ("organic",)),
    ("connected_beauty_mirror_with_display", "connected beauty mirror with display", "smart_mirror", ("hybrid", "contrastive"), ("paraphrase",)),
    ("mirror_with_display_and_speaker", "mirror with display and speaker", "smart_mirror", ("hybrid", "contrastive"), ("paraphrase",)),
    ("mirror_display", "mirror display", "smart_mirror", ("hybrid",), ("organic",)),
    ("display_mirror_with_touchscreen", "display mirror with touchscreen", "smart_mirror", ("hybrid",), ("organic",)),
)

_FAMILY_CASES = (
    ("illuminated_mirror_with_speaker", "illuminated mirror with speaker", "lighting_accessory_device", ("family_only", "hybrid", "boundary"), ("organic",)),
    ("vanity_mirror_with_lights", "vanity mirror with lights", "lighting_accessory_device", ("family_only", "boundary"), ("organic",)),
    ("vanity_mirror_with_lights_and_speaker", "vanity mirror with lights and speaker", "lighting_accessory_device", ("family_only", "hybrid", "boundary"), ("paraphrase",)),
    ("lighted_vanity_mirror", "lighted vanity mirror", "lighting_accessory_device", ("family_only", "boundary"), ("organic",)),
    ("mirror_with_lights_and_speaker", "mirror with lights and speaker", "lighting_accessory_device", ("family_only", "hybrid", "boundary"), ("paraphrase",)),
)

_AMBIGUOUS_CASES = (
    ("decorative_light_panel", "decorative light panel", ("boundary", "contrastive"), ("adversarial",)),
    ("ambient_light_bar", "ambient light bar", ("boundary", "contrastive"), ("adversarial",)),
    ("smart_light_with_display", "smart light module with display", ("boundary", "contrastive"), ("adversarial",)),
    ("speaker_light_module", "speaker light module", ("boundary", "contrastive"), ("adversarial",)),
    ("grow_monitor_light", "grow monitor light", ("boundary", "contrastive"), ("adversarial",)),
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
