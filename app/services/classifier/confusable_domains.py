from __future__ import annotations

from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass

from .models import SubtypeCandidate
from .normalization import normalize


@dataclass(frozen=True, slots=True)
class DomainDisambiguationContext:
    cue_hits: frozenset[str]
    signal_traits: frozenset[str]
    primary_head: str | None = None
    primary_head_term: str | None = None
    primary_head_quality: str | None = None
    primary_head_conflict: bool = False
    primary_is_accessory: bool = False
    target_device: tuple[str, ...] = ()
    controlled_device: tuple[str, ...] = ()
    charged_device: tuple[str, ...] = ()
    powered_device: tuple[str, ...] = ()
    host_device: tuple[str, ...] = ()
    integrated_feature: tuple[str, ...] = ()
    installation_context: tuple[str, ...] = ()

    @property
    def primary_head_text(self) -> str:
        return normalize(" ".join(part for part in (self.primary_head, self.primary_head_term) if part))


@dataclass(frozen=True, slots=True)
class CandidateDomainAdjustment:
    delta: int = 0
    domain_role_reasons: tuple[str, ...] = ()
    confusable_adjustments: tuple[str, ...] = ()


def _has_cue(context: DomainDisambiguationContext, *cue_names: str) -> bool:
    return any(cue_name in context.cue_hits for cue_name in cue_names)


def _contains_fragment(values: Sequence[str], *fragments: str) -> bool:
    normalized_values = [normalize(value) for value in values if value]
    return any(fragment in value for value in normalized_values for fragment in fragments)


def _head_contains(context: DomainDisambiguationContext, *fragments: str) -> bool:
    head_text = context.primary_head_text
    return any(fragment in head_text for fragment in fragments)


def _apply_delta(
    bucket: dict[str, list[tuple[int, str, str]]],
    candidate: SubtypeCandidate,
    delta: int,
    *,
    reason: str,
    confusable: bool = False,
) -> None:
    bucket[candidate.id].append((delta, reason, "confusable" if confusable else "domain"))


def _security_vs_projector_display_matrix(
    candidates: Sequence[SubtypeCandidate],
    context: DomainDisambiguationContext,
    bucket: dict[str, list[tuple[int, str, str]]],
) -> None:
    if not (
        _has_cue(context, "intercom_role", "intercom_access_context", "access_control_context")
        or _head_contains(context, "intercom", "access panel", "video intercom")
    ):
        return

    for candidate in candidates:
        if candidate.id == "ip_intercom":
            _apply_delta(
                bucket,
                candidate,
                44,
                reason="security_vs_projector_display: intercom and access cues strongly matched the intercom family",
                confusable=True,
            )
        elif candidate.family == "smart_home_security":
            _apply_delta(
                bucket,
                candidate,
                22,
                reason="security_vs_projector_display: security-family context fit the detected intercom/access head",
                confusable=True,
            )
        elif candidate.family == "access_control_device":
            _apply_delta(
                bucket,
                candidate,
                18,
                reason="security_vs_projector_display: access-control context supported the candidate",
                confusable=True,
            )
        elif candidate.family in {"projector_device", "home_entertainment_device", "smart_assistant_device", "display_device"}:
            _apply_delta(
                bucket,
                candidate,
                -34,
                reason="security_vs_projector_display: intercom, keypad, and access cues outweighed projector or display families",
                confusable=True,
            )


def _networking_vs_security_matrix(
    candidates: Sequence[SubtypeCandidate],
    context: DomainDisambiguationContext,
    bucket: dict[str, list[tuple[int, str, str]]],
) -> None:
    switch_like = _head_contains(context, "switch", "injector", "gateway") or _has_cue(
        context, "network_switch_role", "poe_injector_role"
    )
    camera_target = _contains_fragment(context.target_device, "camera", "cameras") or _has_cue(
        context, "security_camera_poe_context", "recorder_system_role"
    )
    if not (switch_like and camera_target):
        return

    for candidate in candidates:
        if candidate.id == "network_switch":
            _apply_delta(
                bucket,
                candidate,
                38,
                reason="networking_vs_security: switch wording with camera PoE context matched the networking-switch family",
                confusable=True,
            )
        elif candidate.id == "poe_injector":
            _apply_delta(
                bucket,
                candidate,
                22,
                reason="networking_vs_security: PoE camera context supported edge-power networking accessories",
                confusable=True,
            )
        elif candidate.id == "nvr_dvr_recorder" and _has_cue(context, "recorder_system_role"):
            _apply_delta(
                bucket,
                candidate,
                28,
                reason="networking_vs_security: recorder cues with PoE camera context supported the security-recording family",
                confusable=True,
            )
        elif candidate.family == "networking_device":
            _apply_delta(
                bucket,
                candidate,
                16,
                reason="networking_vs_security: route anchor and role cues fit networking over security peripherals",
                confusable=True,
            )
        elif candidate.family in {"smart_home_security", "building_hardware_lock"}:
            _apply_delta(
                bucket,
                candidate,
                -24,
                reason="networking_vs_security: switch and PoE wording outweighed security-device families",
                confusable=True,
            )


def _power_system_vs_charger_matrix(
    candidates: Sequence[SubtypeCandidate],
    context: DomainDisambiguationContext,
    bucket: dict[str, list[tuple[int, str, str]]],
) -> None:
    ups_like = _has_cue(context, "ups_backup_role") or _head_contains(context, "ups", "backup unit")
    backup_targets = _contains_fragment(context.powered_device, "nas", "router", "modem", "server") or _has_cue(
        context, "nas_router_backup_context"
    )
    if not (ups_like and backup_targets):
        return

    for candidate in candidates:
        if candidate.id == "ups":
            _apply_delta(
                bucket,
                candidate,
                42,
                reason="power_system_vs_charger: backup-unit wording for NAS or router context matched UPS governance",
                confusable=True,
            )
        elif candidate.family == "energy_power_system":
            _apply_delta(
                bucket,
                candidate,
                24,
                reason="power_system_vs_charger: powered-device context supported the energy-power system family",
                confusable=True,
            )
        elif candidate.id in {"power_bank", "external_power_supply", "battery_charger"} or candidate.family in {
            "portable_power_charger",
            "portable_power_system",
        }:
            _apply_delta(
                bucket,
                candidate,
                -28,
                reason="power_system_vs_charger: UPS backup context ruled out charger and simple battery-pack readings",
                confusable=True,
            )


def _portable_power_station_matrix(
    candidates: Sequence[SubtypeCandidate],
    context: DomainDisambiguationContext,
    bucket: dict[str, list[tuple[int, str, str]]],
) -> None:
    if not (_has_cue(context, "portable_power_station_context") or _head_contains(context, "power station")):
        return

    for candidate in candidates:
        if candidate.id == "portable_power_station":
            _apply_delta(
                bucket,
                candidate,
                38,
                reason="portable_power_station_matrix: power-station cues supported the portable energy-storage family",
                confusable=True,
            )
        elif candidate.id in {"power_bank", "external_power_supply"}:
            _apply_delta(
                bucket,
                candidate,
                -22,
                reason="portable_power_station_matrix: station-scale energy cues outweighed charger and adapter families",
                confusable=True,
            )


def _building_access_controller_matrix(
    candidates: Sequence[SubtypeCandidate],
    context: DomainDisambiguationContext,
    bucket: dict[str, list[tuple[int, str, str]]],
) -> None:
    controller_like = _head_contains(context, "controller", "control module", "panel", "gateway") or _has_cue(
        context, "gateway_module_role", "panel_role"
    )
    access_like = _contains_fragment(context.controlled_device, "garage", "door", "gate", "access", "opener") or _has_cue(
        context, "building_access_controller_context", "garage_control_context", "access_control_context"
    )
    if not (controller_like and access_like):
        return

    for candidate in candidates:
        if candidate.id == "garage_door_controller":
            _apply_delta(
                bucket,
                candidate,
                44,
                reason="building_access_controller_matrix: garage and opener control cues matched the building-access controller family",
                confusable=True,
            )
        elif candidate.family in {"building_access_device", "access_control_device"}:
            _apply_delta(
                bucket,
                candidate,
                22,
                reason="building_access_controller_matrix: building-access context supported the candidate family",
                confusable=True,
            )
        elif candidate.family in {"projector_device", "home_entertainment_device", "personal_computing_device"}:
            _apply_delta(
                bucket,
                candidate,
                -26,
                reason="building_access_controller_matrix: garage and access-control wording ruled out generic AV or PC controller families",
                confusable=True,
            )


def _office_creator_vs_avict_matrix(
    candidates: Sequence[SubtypeCandidate],
    context: DomainDisambiguationContext,
    bucket: dict[str, list[tuple[int, str, str]]],
) -> None:
    if _has_cue(context, "home_theater_context") or _head_contains(context, "home theater receiver", "av receiver"):
        for candidate in candidates:
            if candidate.id == "home_cinema_system":
                _apply_delta(
                    bucket,
                    candidate,
                    36,
                    reason="office_creator_vs_avict: home-theater receiver cues favored the home-cinema family over microphone receivers",
                    confusable=True,
                )
            elif candidate.id == "wireless_microphone_receiver":
                _apply_delta(
                    bucket,
                    candidate,
                    -24,
                    reason="office_creator_vs_avict: home-theater receiver wording ruled out the wireless-microphone receiver family",
                    confusable=True,
                )

    document_camera_like = _has_cue(context, "document_camera_context") or _head_contains(
        context, "document camera", "visualizer"
    )
    if document_camera_like:
        for candidate in candidates:
            if candidate.id == "document_camera":
                _apply_delta(
                    bucket,
                    candidate,
                    42,
                    reason="office_creator_vs_avict: classroom visualizer cues matched the document-camera subtype",
                    confusable=True,
                )
            elif candidate.family == "creator_office_device":
                _apply_delta(
                    bucket,
                    candidate,
                    20,
                    reason="office_creator_vs_avict: creator-device context supported the family",
                    confusable=True,
                )
            elif candidate.family in {"projector_device", "display_device", "personal_computing_device"}:
                _apply_delta(
                    bucket,
                    candidate,
                    -24,
                    reason="office_creator_vs_avict: visualizer cues outweighed projector and generic display families",
                    confusable=True,
                )

    kvm_like = _has_cue(context, "kvm_context") or _head_contains(context, "kvm switch")
    if kvm_like:
        for candidate in candidates:
            if candidate.id == "kvm_switch":
                _apply_delta(
                    bucket,
                    candidate,
                    40,
                    reason="office_creator_vs_avict: KVM wording with monitor or computer cues matched the office-peripheral subtype",
                    confusable=True,
                )
            elif candidate.family == "office_avict_peripheral":
                _apply_delta(
                    bucket,
                    candidate,
                    18,
                    reason="office_creator_vs_avict: office peripheral cues supported the family",
                    confusable=True,
                )
            elif candidate.family in {"display_device", "personal_computing_device"}:
                _apply_delta(
                    bucket,
                    candidate,
                    -20,
                    reason="office_creator_vs_avict: KVM switching cues ruled out plain display or PC families",
                    confusable=True,
                )

    presentation_like = _has_cue(context, "presentation_clicker_context")
    if presentation_like:
        for candidate in candidates:
            if candidate.id == "presentation_clicker":
                _apply_delta(
                    bucket,
                    candidate,
                    34,
                    reason="office_creator_vs_avict: clicker and slide-control cues matched the presentation remote subtype",
                    confusable=True,
                )


def _smoke_alarm_vs_monitor_matrix(
    candidates: Sequence[SubtypeCandidate],
    context: DomainDisambiguationContext,
    bucket: dict[str, list[tuple[int, str, str]]],
) -> None:
    if not (_has_cue(context, "smoke_co_alarm_context") or _head_contains(context, "smoke", "alarm")):
        return

    smart_alarm = "wifi" in context.signal_traits or "app_control" in context.signal_traits or _head_contains(context, "smart")
    for candidate in candidates:
        if smart_alarm and candidate.id == "smart_smoke_co_alarm":
            _apply_delta(
                bucket,
                candidate,
                42,
                reason="smoke_alarm_vs_monitor: smoke and carbon-monoxide cues with connected context matched the smart alarm subtype",
                confusable=True,
            )
        elif not smart_alarm and candidate.id == "smoke_co_alarm":
            _apply_delta(
                bucket,
                candidate,
                34,
                reason="smoke_alarm_vs_monitor: smoke and carbon-monoxide cues matched the non-connected alarm subtype",
                confusable=True,
            )
        elif candidate.family == "life_safety_alarm":
            _apply_delta(
                bucket,
                candidate,
                22,
                reason="smoke_alarm_vs_monitor: life-safety family aligned with the detected alarm head",
                confusable=True,
            )
        elif candidate.family in {"smart_home_security", "projector_device", "smart_assistant_device"}:
            _apply_delta(
                bucket,
                candidate,
                -18,
                reason="smoke_alarm_vs_monitor: alarm and CO cues outweighed generic security or display families",
                confusable=True,
            )


def _lighting_vs_wellness_vs_mirror_matrix(
    candidates: Sequence[SubtypeCandidate],
    context: DomainDisambiguationContext,
    bucket: dict[str, list[tuple[int, str, str]]],
) -> None:
    if _has_cue(context, "smart_lighting_controller_context") or _head_contains(context, "lighting controller", "lighting gateway"):
        for candidate in candidates:
            if candidate.id == "smart_light_controller":
                _apply_delta(
                    bucket,
                    candidate,
                    40,
                    reason="lighting_vs_wellness_vs_mirror: lighting bridge and gateway cues matched the smart-lighting controller family",
                    confusable=True,
                )
            elif candidate.family == "smart_lighting":
                _apply_delta(
                    bucket,
                    candidate,
                    22,
                    reason="lighting_vs_wellness_vs_mirror: lighting-control context supported the family",
                    confusable=True,
                )
            elif candidate.id in {"iot_gateway", "security_hub"}:
                _apply_delta(
                    bucket,
                    candidate,
                    -18,
                    reason="lighting_vs_wellness_vs_mirror: lighting-controller cues outweighed generic gateway families",
                    confusable=True,
                )

    if _has_cue(context, "vanity_mirror_context"):
        display_like = "display" in context.signal_traits or "wifi" in context.signal_traits or _head_contains(context, "smart mirror")
        for candidate in candidates:
            if display_like and candidate.id == "smart_mirror":
                _apply_delta(
                    bucket,
                    candidate,
                    26,
                    reason="lighting_vs_wellness_vs_mirror: connected display cues kept the smart-mirror reading viable",
                    confusable=True,
                )
            elif not display_like and candidate.id == "illuminated_mirror":
                _apply_delta(
                    bucket,
                    candidate,
                    28,
                    reason="lighting_vs_wellness_vs_mirror: vanity-mirror wording without strong display cues favored the illuminated-mirror boundary family",
                    confusable=True,
                )


def _wellness_boundary_matrix(
    candidates: Sequence[SubtypeCandidate],
    context: DomainDisambiguationContext,
    bucket: dict[str, list[tuple[int, str, str]]],
) -> None:
    heated_like = _has_cue(context, "heated_wearable_context") or _head_contains(
        context,
        "heated eye mask",
        "warming eye mask",
        "warm compress eye mask",
    )
    eye_mask_like = _head_contains(context, "eye mask")
    audio_like = _contains_fragment(
        context.integrated_feature,
        "speaker",
        "speakers",
        "headphone",
        "headphones",
        "earbud",
        "earbuds",
    )
    if not (heated_like or eye_mask_like):
        return

    for candidate in candidates:
        if candidate.id == "heated_wellness_mask" and heated_like:
            _apply_delta(
                bucket,
                candidate,
                42,
                reason="wellness_boundary_matrix: heated wearable and eye-mask cues matched the personal-heating wellness boundary product",
                confusable=True,
            )
        elif candidate.id == "heated_wellness_mask" and audio_like:
            _apply_delta(
                bucket,
                candidate,
                -30,
                reason="wellness_boundary_matrix: audio-enabled eye-mask wording lacked heating cues, so the heated-mask reading stayed conservative",
                confusable=True,
            )
        elif audio_like and candidate.id == "wireless_headphones":
            _apply_delta(
                bucket,
                candidate,
                20,
                reason="wellness_boundary_matrix: integrated speaker wording kept the wireless-audio family viable for non-heated masks",
                confusable=True,
            )
        elif audio_like and candidate.family in {"projector_device", "display_device", "smart_assistant_device"}:
            _apply_delta(
                bucket,
                candidate,
                -24,
                reason="wellness_boundary_matrix: eye-mask audio wording ruled out projector and display-family leakage",
                confusable=True,
            )
        elif candidate.family == "personal_heating_appliance" and heated_like:
            _apply_delta(
                bucket,
                candidate,
                20,
                reason="wellness_boundary_matrix: heated wearable cues supported the personal-heating family",
                confusable=True,
            )
        elif candidate.family == "personal_heating_appliance" and audio_like:
            _apply_delta(
                bucket,
                candidate,
                -16,
                reason="wellness_boundary_matrix: non-heated audio-mask wording weakened the personal-heating family reading",
                confusable=True,
            )
        elif candidate.family in {"personal_care_appliance", "av_ict_device"}:
            _apply_delta(
                bucket,
                candidate,
                -18,
                reason="wellness_boundary_matrix: heated wearable language outweighed oral-care and generic AV/ICT families",
                confusable=True,
            )


def apply_domain_role_matrices(
    candidates: Sequence[SubtypeCandidate],
    context: DomainDisambiguationContext,
) -> dict[str, CandidateDomainAdjustment]:
    bucket: dict[str, list[tuple[int, str, str]]] = defaultdict(list)
    _security_vs_projector_display_matrix(candidates, context, bucket)
    _networking_vs_security_matrix(candidates, context, bucket)
    _power_system_vs_charger_matrix(candidates, context, bucket)
    _portable_power_station_matrix(candidates, context, bucket)
    _building_access_controller_matrix(candidates, context, bucket)
    _office_creator_vs_avict_matrix(candidates, context, bucket)
    _smoke_alarm_vs_monitor_matrix(candidates, context, bucket)
    _lighting_vs_wellness_vs_mirror_matrix(candidates, context, bucket)
    _wellness_boundary_matrix(candidates, context, bucket)

    adjustments: dict[str, CandidateDomainAdjustment] = {}
    for candidate in candidates:
        rows = bucket.get(candidate.id, [])
        if not rows:
            continue
        adjustments[candidate.id] = CandidateDomainAdjustment(
            delta=sum(delta for delta, _, _ in rows),
            domain_role_reasons=tuple(reason for _, reason, kind in rows if kind == "domain" or kind == "confusable"),
            confusable_adjustments=tuple(reason for _, reason, kind in rows if kind == "confusable"),
        )
    return adjustments


__all__ = [
    "CandidateDomainAdjustment",
    "DomainDisambiguationContext",
    "apply_domain_role_matrices",
]
