from __future__ import annotations

from .base import ambiguous_case, family_case, subtype_case

GROUP = "specialty_boundary"

_SUBTYPE_CASES = (
    ("consumer_drone_quadcopter_camera", "consumer drone quadcopter with camera", "consumer_drone", ("boundary",), ("paraphrase",)),
    ("camera_drone_gps_return_home", "camera drone with gps return home", "consumer_drone", ("boundary",), ("organic",)),
)

_FAMILY_CASES = (
    ("drone_controller_telemetry_screen", "drone controller with telemetry screen", "drone_device", ("contrastive", "boundary"), ("adversarial",)),
    ("fpv_remote_controller_drone", "fpv remote controller for drone", "drone_device", ("contrastive", "boundary"), ("paraphrase",)),
    ("electric_fence_energizer_pulse_box", "electric fence energizer pulse box", "specialty_electrical_device", ("boundary",), ("organic",)),
    ("portable_milking_machine_vacuum", "portable milking machine with vacuum pump", "agricultural_appliance", ("boundary",), ("paraphrase",)),
    ("drone_remote_joysticks_screen", "drone remote with joysticks and screen", "drone_device", ("contrastive", "boundary"), ("organic",)),
    ("livestock_fence_charger_energizer", "livestock fence charger energizer", "specialty_electrical_device", ("boundary",), ("organic",)),
    ("radio_controller_for_fpv_drone", "radio controller for fpv drone", "drone_device", ("contrastive", "boundary"), ("paraphrase",)),
)

_AMBIGUOUS_CASES = (
    ("aquaculture_fish_stunner_wand", "aquaculture fish stunner wand", ("boundary",), ("organic",)),
    ("farm_milker_bucket_system", "farm milker bucket system", ("boundary",), ("organic",)),
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

