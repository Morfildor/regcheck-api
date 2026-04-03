from __future__ import annotations

from .base import family_case, subtype_case

GROUP = "specialty_boundary"

CASES = (
    subtype_case(GROUP, "consumer_drone", "consumer drone with camera and remote controller", "consumer_drone", tags=("boundary",)),
    family_case(GROUP, "drone_controller", "drone controller with telemetry screen", "drone_device", tags=("boundary",)),
    family_case(GROUP, "electric_fish_stunner", "electric fish stunner for aquaculture", "specialty_electrical_device", tags=("boundary",)),
    family_case(GROUP, "fence_energizer", "electric fence energizer with pulse output", "specialty_electrical_device", tags=("boundary",)),
    family_case(GROUP, "milking_machine", "portable milking machine with vacuum pump", "agricultural_appliance", tags=("boundary",)),
)
