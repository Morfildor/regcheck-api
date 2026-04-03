from __future__ import annotations

from .base import family_case, subtype_case

GROUP = "lighting_optical"

CASES = (
    subtype_case(GROUP, "digital_photo_frame", "digital photo frame with wifi slideshow", "digital_photo_frame"),
    subtype_case(GROUP, "heating_lamp", "heating lamp for terrarium enclosure", "heating_lamp"),
    family_case(GROUP, "home_projector", "home projector with 4k streaming support", "projector_device", tags=("boundary",)),
    family_case(GROUP, "projector_office", "office projector with hdmi input", "projector_device", tags=("boundary",)),
    subtype_case(GROUP, "smart_desk_lamp", "smart desk lamp with app dimming", "smart_desk_lamp"),
    subtype_case(GROUP, "smart_led_bulb", "smart led bulb with wifi and voice control", "smart_led_bulb"),
    family_case(GROUP, "smart_light_controller", "smart lighting controller with zigbee", "smart_lighting", tags=("boundary",)),
    subtype_case(GROUP, "smart_mirror", "smart mirror with display and speaker", "smart_mirror"),
    subtype_case(GROUP, "smart_tv", "smart tv with wifi and streaming apps", "smart_tv"),
    subtype_case(GROUP, "soundbar_tv", "soundbar with hdmi earc and bluetooth", "soundbar"),
)
