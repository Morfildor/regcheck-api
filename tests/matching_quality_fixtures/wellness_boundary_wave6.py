from __future__ import annotations

from .base import ambiguous_case, family_case, subtype_case

GROUP = "wellness_boundary"

_SUBTYPE_CASES = (
    ("heated_neck_wrap_rechargeable", "heated neck wrap rechargeable", "heated_wellness_wrap", ("contrastive", "wearable"), ("organic",)),
    ("rechargeable_heated_shoulder_wrap", "rechargeable heated shoulder wrap", "heated_wellness_wrap", ("contrastive", "wearable"), ("paraphrase",)),
    ("heated_shoulder_wrap_usb", "heated shoulder wrap usb", "heated_wellness_wrap", ("contrastive", "wearable"), ("organic",)),
    ("heated_belt_for_lower_back", "heated belt for lower back", "heated_wellness_wrap", ("relation", "wearable"), ("organic",)),
    ("wearable_heated_neck_wrap", "wearable heated neck wrap", "heated_wellness_wrap", ("wearable",), ("paraphrase",)),
    ("heated_back_wrap_rechargeable", "heated back wrap rechargeable", "heated_wellness_wrap", ("wearable",), ("organic",)),
    ("usb_heated_eye_mask", "usb heated eye mask", "heated_wellness_mask", ("contrastive", "wearable"), ("organic",)),
    ("heated_eye_mask_rechargeable", "heated eye mask rechargeable", "heated_wellness_mask", ("contrastive", "wearable"), ("paraphrase",)),
    ("warming_eye_mask", "warming eye mask", "heated_wellness_mask", ("wearable",), ("organic",)),
    ("warm_compress_eye_mask", "warm compress eye mask", "heated_wellness_mask", ("wearable",), ("organic",)),
    ("rechargeable_eye_mask_heat", "rechargeable eye mask heat", "heated_wellness_mask", ("wearable",), ("paraphrase",)),
    ("heating_pad_with_controller", "heating pad with controller", "heating_pad", ("contrastive",), ("organic",)),
    ("heating_blanket_pad", "heating blanket pad", "heating_pad", ("contrastive",), ("paraphrase",)),
    ("rechargeable_heating_pad", "rechargeable heating pad", "heating_pad", ("contrastive",), ("organic",)),
    ("heating_pad_for_shoulder", "heating pad for shoulder", "heating_pad", ("relation",), ("organic",)),
    ("personal_heating_wrap", "personal heating wrap", "heated_wellness_wrap", ("wearable",), ("paraphrase",)),
)

_FAMILY_CASES = (
    ("electric_underblanket_controller", "electric underblanket controller", "personal_heating_appliance", ("family_only", "companion", "boundary"), ("organic",)),
    ("electric_blanket_controller", "electric blanket controller", "personal_heating_appliance", ("family_only", "companion", "boundary"), ("paraphrase",)),
    ("heated_blanket_controller", "heated blanket controller", "personal_heating_appliance", ("family_only", "companion", "boundary"), ("organic",)),
    ("blanket_temperature_controller", "blanket temperature controller", "personal_heating_appliance", ("family_only", "companion", "boundary"), ("paraphrase",)),
    ("warming_blanket_controller", "warm blanket controller", "personal_heating_appliance", ("family_only", "companion", "boundary"), ("organic",)),
)

_AMBIGUOUS_CASES = (
    ("therapy_heat_wrap", "therapy heat wrap", ("boundary", "contrastive"), ("adversarial",)),
    ("warm_body_accessory", "warm body accessory", ("boundary", "contrastive"), ("adversarial",)),
    ("heated_wearable_controller", "heated wearable controller", ("boundary", "contrastive"), ("adversarial",)),
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
