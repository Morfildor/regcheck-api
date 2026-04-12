from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class BenchmarkCase:
    key: str
    description: str
    expected_product: str | None
    expected_primary_standard: str | None
    required_directives: tuple[str, ...] = ()
    expected_route_family: str | None = None
    expected_stage: str | None = None


CURATED_MATCH_CASES: tuple[BenchmarkCase, ...] = (
    BenchmarkCase(
        key="smart_speaker",
        description="smart speaker with wifi and bluetooth",
        expected_product="smart_speaker",
        expected_primary_standard="EN 62368-1",
        required_directives=("RED", "ROHS"),
        expected_stage="subtype",
    ),
    BenchmarkCase(
        key="smart_lock",
        description="smart lock with wifi and bluetooth",
        expected_product="smart_lock",
        expected_primary_standard="EN 14846",
        required_directives=("RED", "GPSR"),
        expected_route_family="building_hardware",
        expected_stage="subtype",
    ),
    BenchmarkCase(
        key="uv_nail_lamp",
        description="uv nail lamp for gel polish",
        expected_product="uv_nail_lamp",
        expected_primary_standard=None,
        required_directives=("EMC", "ROHS"),
        expected_route_family="lighting_device",
        expected_stage="family",
    ),
)


BLIND_HOLDOUT_CASES: tuple[BenchmarkCase, ...] = (
    BenchmarkCase(
        key="garage_controller",
        description="garage opener controller with wifi app control",
        expected_product="garage_door_controller",
        expected_primary_standard="EN 60335-2-95",
        required_directives=("RED",),
        expected_route_family="building_hardware",
        expected_stage="subtype",
    ),
    BenchmarkCase(
        key="portable_power_station",
        description="portable power station with ac outlets and battery backup for camping",
        expected_product="portable_power_station",
        expected_primary_standard="EN 62368-1",
        required_directives=("LVD", "EMC"),
        expected_route_family="av_ict",
        expected_stage="subtype",
    ),
)


ADVERSARIAL_CASES: tuple[BenchmarkCase, ...] = (
    BenchmarkCase(
        key="generic_tool",
        description="generic industrial tool",
        expected_product=None,
        expected_primary_standard=None,
        expected_stage="ambiguous",
    ),
    BenchmarkCase(
        key="doorbell_chime",
        description="wireless doorbell chime receiver for smart doorbell",
        expected_product="doorbell_chime_receiver",
        expected_primary_standard="EN 62368-1",
        required_directives=("RED",),
        expected_route_family="av_ict",
        expected_stage="subtype",
    ),
)
