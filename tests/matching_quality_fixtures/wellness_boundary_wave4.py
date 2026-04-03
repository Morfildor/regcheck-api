from __future__ import annotations

from .base import ambiguous_case, family_case, subtype_case

GROUP = "wellness_boundary"

_SUBTYPE_CASES = (
    ("bluetooth_digital_stethoscope", "bluetooth digital stethoscope", "digital_stethoscope", ("boundary",), ("paraphrase",)),
    ("smart_glucose_meter_app", "smart glucose meter with app", "smart_glucose_meter", ("boundary",), ("organic",)),
    ("smart_thermometer_app_log", "wireless smart thermometer with app log", "smart_thermometer", ("boundary",), ("paraphrase",)),
    ("bluetooth_body_composition_scale", "bluetooth body composition scale", "smart_scale", ("boundary",), ("organic",)),
    ("deep_tissue_massage_gun", "deep tissue percussion massage gun", "massage_gun", ("boundary",), ("paraphrase",)),
    ("pulse_oximeter_finger_clip", "pulse oximeter finger clip display", "pulse_oximeter", ("boundary",), ("organic",)),
    ("oxygen_fingertip_pulse_oximeter", "oxygen fingertip pulse oximeter", "pulse_oximeter", ("boundary",), ("paraphrase",)),
    ("digital_stethoscope_app_recording", "digital stethoscope with app recording", "digital_stethoscope", ("boundary",), ("organic",)),
)

_FAMILY_CASES = (
    ("heated_eye_mask_usb_rechargeable", "heated eye mask usb rechargeable", "personal_heating_appliance", ("contrastive", "family_only"), ("adversarial",)),
    ("heated_eye_mask_rechargeable", "heated eye mask rechargeable", "personal_heating_appliance", ("contrastive", "family_only"), ("paraphrase",)),
    ("continuous_glucose_monitor_sensor_patch", "continuous glucose monitor sensor patch", "health_monitor", ("boundary", "family_only"), ("adversarial",)),
    ("continuous_glucose_monitor_phone_app", "continuous glucose monitor with phone app", "health_monitor", ("boundary", "family_only"), ("organic",)),
    ("wearable_ecg_heart_rhythm_monitor", "wearable ecg heart rhythm monitor", "health_monitor", ("boundary", "family_only"), ("adversarial",)),
    ("smart_inhaler_dose_tracker", "smart inhaler with dose tracker", "respiratory_therapy", ("boundary", "family_only"), ("organic",)),
    ("cpap_machine_humidifier", "cpap machine with humidifier", "respiratory_therapy", ("boundary", "family_only"), ("paraphrase",)),
    ("red_light_therapy_panel_timer", "red light therapy device panel timer", "wellness_light_device", ("boundary", "family_only"), ("paraphrase",)),
    ("heart_monitor_chest_strap_bluetooth", "heart monitor chest strap bluetooth", "health_monitor", ("boundary", "family_only"), ("organic",)),
)

_AMBIGUOUS_CASES = (
    ("eye_mask_bluetooth_speakers", "eye mask with bluetooth speakers", ("contrastive", "boundary"), ("adversarial",)),
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

