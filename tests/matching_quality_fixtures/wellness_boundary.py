from __future__ import annotations

from .base import family_case, subtype_case

GROUP = "wellness_boundary"

CASES = (
    family_case(GROUP, "cpap_device", "cpap device with humidifier and hose", "respiratory_therapy", tags=("boundary",)),
    family_case(GROUP, "continuous_glucose_monitor", "continuous glucose monitor wearable sensor", "health_monitor", tags=("boundary",)),
    subtype_case(GROUP, "digital_stethoscope", "digital stethoscope with bluetooth app", "digital_stethoscope", tags=("boundary",)),
    family_case(GROUP, "ems_tens_device", "ems tens device for muscle stimulation", "wellness_electrostimulation", tags=("boundary",)),
    family_case(GROUP, "heart_rate_monitor", "wearable heart rate monitor with bluetooth app body contact", "health_monitor", tags=("boundary",)),
    subtype_case(GROUP, "massage_gun", "massage gun with percussion motor", "massage_gun"),
    subtype_case(GROUP, "pulse_oximeter", "pulse oximeter fingertip display", "pulse_oximeter", tags=("boundary",)),
    family_case(GROUP, "red_light_therapy_device", "red light therapy device panel with timer", "wellness_light_device", tags=("boundary",)),
    family_case(GROUP, "smart_blood_pressure_monitor", "smart blood pressure monitor with cuff and app", "health_monitor", tags=("boundary",)),
    subtype_case(GROUP, "smart_glucose_meter", "smart glucose meter with bluetooth syncing", "smart_glucose_meter", tags=("boundary",)),
    family_case(GROUP, "smart_inhaler", "smart inhaler with dose tracking", "respiratory_therapy", tags=("boundary",)),
    subtype_case(GROUP, "smart_scale", "smart scale with body composition app", "smart_scale"),
    subtype_case(GROUP, "smart_thermometer", "smart thermometer with app logging", "smart_thermometer", tags=("boundary",)),
    family_case(
        GROUP,
        "illuminated_mirror_with_speaker",
        "illuminated mirror with speaker",
        "lighting_accessory_device",
        tags=("boundary", "contrastive"),
    ),
)
