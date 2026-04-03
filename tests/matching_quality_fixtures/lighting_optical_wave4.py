from __future__ import annotations

from .base import family_case, subtype_case

GROUP = "lighting_optical"

_SUBTYPE_CASES = (
    ("lighting_gateway_smart_bulbs", "lighting gateway for smart bulbs", "smart_light_controller", ("contrastive",), ("adversarial",)),
    ("smart_mirror_wifi_speaker_display", "smart mirror with wifi speaker and display", "smart_mirror", ("contrastive",), ("adversarial",)),
    ("wifi_led_bulb_color_changing", "wifi led bulb color changing", "smart_led_bulb", ("boundary",), ("paraphrase",)),
    ("smart_desk_lamp_app_dimming", "smart desk lamp with app dimming", "smart_desk_lamp", ("boundary",), ("paraphrase",)),
    ("digital_photo_frame_wifi_slideshow", "digital photo frame with wifi slideshow", "digital_photo_frame", ("boundary",), ("organic",)),
    ("soundbar_tv_earc", "soundbar for tv with earc", "soundbar", ("boundary",), ("organic",)),
    ("living_room_smart_tv_apps", "living room smart tv with wifi apps", "smart_tv", ("boundary",), ("organic",)),
    ("terrarium_heat_lamp_bulb", "terrarium heat lamp bulb", "heating_lamp", ("boundary",), ("paraphrase",)),
    ("connected_beauty_mirror_display", "connected beauty mirror with display", "smart_mirror", ("contrastive",), ("paraphrase",)),
)

_FAMILY_CASES = (
    ("smart_lighting_controller_zigbee", "smart lighting controller with zigbee", "smart_power_control", ("contrastive", "boundary"), ("adversarial",)),
    ("zigbee_light_bridge_controller", "zigbee light bridge controller", "smart_power_control", ("contrastive", "boundary"), ("paraphrase",)),
    ("vanity_mirror_speakers_light", "vanity mirror with speakers and light", "lighting_accessory_device", ("contrastive", "boundary"), ("adversarial",)),
    ("illuminated_vanity_mirror_touch_light", "illuminated vanity mirror with touch light", "lighting_accessory_device", ("boundary",), ("organic",)),
    ("home_projector_streaming_4k", "home projector streaming 4k", "projector_device", ("contrastive", "boundary"), ("paraphrase",)),
    ("classroom_projector_hdmi", "classroom projector with hdmi", "projector_device", ("boundary",), ("organic",)),
    ("bathroom_lighted_vanity_mirror", "bathroom lighted vanity mirror", "lighting_accessory_device", ("boundary",), ("paraphrase",)),
    ("matter_lighting_bridge_controller", "matter lighting bridge controller", "smart_power_control", ("contrastive", "boundary"), ("adversarial",)),
    ("projector_with_visualizer_input", "projector with classroom visualizer input", "projector_device", ("contrastive", "boundary"), ("adversarial",)),
)

CASES = tuple(
    subtype_case(GROUP, name, description, expected_subtype, tags=tags, modes=modes)
    for name, description, expected_subtype, tags, modes in _SUBTYPE_CASES
) + tuple(
    family_case(GROUP, name, description, expected_family, tags=tags, modes=modes)
    for name, description, expected_family, tags, modes in _FAMILY_CASES
)

