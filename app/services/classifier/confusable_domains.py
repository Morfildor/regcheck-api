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


def _companion_lock_bridge_matrix(
    candidates: Sequence[SubtypeCandidate],
    context: DomainDisambiguationContext,
    bucket: dict[str, list[tuple[int, str, str]]],
) -> None:
    bridge_like = _head_contains(context, "bridge", "lock bridge") or _has_cue(context, "bridge_companion_context")
    lock_context = (
        _contains_fragment(context.host_device, "lock", "door lock", "smart lock")
        or _contains_fragment(context.controlled_device, "lock", "door lock")
        or _contains_fragment(context.target_device, "lock", "door lock")
        or _has_cue(context, "bridge_companion_context")
    )
    if not (bridge_like and lock_context):
        return

    for candidate in candidates:
        if candidate.id == "iot_gateway":
            _apply_delta(
                bucket,
                candidate,
                38,
                reason="companion_lock_bridge: bridge/gateway wording for a lock device matched the IoT gateway companion family",
                confusable=True,
            )
        elif candidate.family == "networking_device":
            _apply_delta(
                bucket,
                candidate,
                20,
                reason="companion_lock_bridge: bridge or gateway companion context supported the networking family",
                confusable=True,
            )
        elif candidate.id == "smart_lock":
            _apply_delta(
                bucket,
                candidate,
                -30,
                reason="companion_lock_bridge: companion-bridge wording down-ranked the main smart-lock reading",
                confusable=True,
            )
        elif candidate.family == "building_hardware_lock":
            _apply_delta(
                bucket,
                candidate,
                -18,
                reason="companion_lock_bridge: bridge/gateway companion wording outweighed the main lock family",
                confusable=True,
            )


def _doorbell_chime_matrix(
    candidates: Sequence[SubtypeCandidate],
    context: DomainDisambiguationContext,
    bucket: dict[str, list[tuple[int, str, str]]],
) -> None:
    chime_like = _head_contains(context, "chime receiver", "chime") or _has_cue(context, "chime_receiver_context")
    main_doorbell_camera = _head_contains(context, "video doorbell", "doorbell camera", "chime camera")
    doorbell_context = (
        _contains_fragment(context.target_device, "doorbell", "door bell")
        or _has_cue(context, "chime_receiver_context")
        or _head_contains(context, "chime")
    )
    if not (chime_like or doorbell_context):
        return

    for candidate in candidates:
        if candidate.id == "doorbell_chime_receiver":
            if main_doorbell_camera and not _head_contains(context, "chime receiver", "chime box", "chime unit"):
                _apply_delta(
                    bucket,
                    candidate,
                    -80,
                    reason="doorbell_chime_matrix: video-doorbell camera wording outweighed the companion chime receiver reading",
                    confusable=True,
                )
                continue
            _apply_delta(
                bucket,
                candidate,
                40,
                reason="doorbell_chime_matrix: chime or receiver wording matched the companion doorbell chime product",
                confusable=True,
            )
        elif candidate.family == "smart_home_security" and candidate.id != "smart_doorbell":
            _apply_delta(
                bucket,
                candidate,
                14,
                reason="doorbell_chime_matrix: chime receiver context supported the smart-home security family",
                confusable=True,
            )
        elif candidate.id == "smart_doorbell":
            _apply_delta(
                bucket,
                candidate,
                -28,
                reason="doorbell_chime_matrix: chime or receiver wording down-ranked the main video-doorbell subtype",
                confusable=True,
            )


def _ev_companion_module_matrix(
    candidates: Sequence[SubtypeCandidate],
    context: DomainDisambiguationContext,
    bucket: dict[str, list[tuple[int, str, str]]],
) -> None:
    module_like = context.primary_is_accessory or _head_contains(context, "meter module", "relay module", "module")
    ev_load_context = _has_cue(context, "ev_load_module_context")
    if not (module_like and ev_load_context):
        return

    for candidate in candidates:
        if candidate.id == "ev_energy_module":
            _apply_delta(
                bucket,
                candidate,
                40,
                reason="ev_companion_module: load-balancing or metering module wording matched the EV companion module family",
                confusable=True,
            )
        elif candidate.family == "energy_power_system":
            _apply_delta(
                bucket,
                candidate,
                18,
                reason="ev_companion_module: EV module context supported the energy power system family",
                confusable=True,
            )
        elif candidate.id == "ev_charger_home":
            _apply_delta(
                bucket,
                candidate,
                -30,
                reason="ev_companion_module: EV companion module capped main-charger subtype precision",
                confusable=True,
            )
        elif candidate.family == "ev_charging_equipment":
            _apply_delta(
                bucket,
                candidate,
                -14,
                reason="ev_companion_module: load-balancing module wording weakened the EV charger family reading",
                confusable=True,
            )


def _water_heating_vs_room_heating_matrix(
    candidates: Sequence[SubtypeCandidate],
    context: DomainDisambiguationContext,
    bucket: dict[str, list[tuple[int, str, str]]],
) -> None:
    shower_context = _has_cue(context, "shower_water_heater_context") or _head_contains(
        context, "shower heater", "shower water heater"
    )
    if not shower_context:
        return

    for candidate in candidates:
        if candidate.id == "electric_shower_heater":
            _apply_delta(
                bucket,
                candidate,
                42,
                reason="water_heating_vs_room_heating: shower or instant water-heater wording matched the electric shower heater family",
                confusable=True,
            )
        elif candidate.family == "water_heating_appliance":
            _apply_delta(
                bucket,
                candidate,
                22,
                reason="water_heating_vs_room_heating: shower context supported the water-heating appliance family",
                confusable=True,
            )
        elif candidate.id == "room_heater":
            _apply_delta(
                bucket,
                candidate,
                -36,
                reason="water_heating_vs_room_heating: shower and instant water-heater context outranked the room-heater reading",
                confusable=True,
            )
        elif candidate.id == "fan_heater":
            _apply_delta(
                bucket,
                candidate,
                -28,
                reason="water_heating_vs_room_heating: shower context ruled out fan-heater interpretation",
                confusable=True,
            )
        elif candidate.family == "climate_conditioning_appliance":
            _apply_delta(
                bucket,
                candidate,
                -16,
                reason="water_heating_vs_room_heating: water-heating cues outweighed climate-conditioning family",
                confusable=True,
            )


def _heating_accessory_matrix(
    candidates: Sequence[SubtypeCandidate],
    context: DomainDisambiguationContext,
    bucket: dict[str, list[tuple[int, str, str]]],
) -> None:
    heating_accessory = _has_cue(context, "heating_accessory_controller_context") or _head_contains(
        context, "heating controller"
    )
    if not heating_accessory:
        return

    for candidate in candidates:
        if candidate.family == "personal_heating_appliance":
            _apply_delta(
                bucket,
                candidate,
                24,
                reason="heating_accessory: underblanket or blanket-controller wording supported the personal-heating appliance family",
                confusable=True,
            )
        elif candidate.id == "room_heater":
            _apply_delta(
                bucket,
                candidate,
                -34,
                reason="heating_accessory: underblanket or blanket-controller wording outweighed the room-heater main product reading",
                confusable=True,
            )
        elif candidate.id == "fan_heater":
            _apply_delta(
                bucket,
                candidate,
                -22,
                reason="heating_accessory: heating-accessory wording outweighed fan-heater interpretation",
                confusable=True,
            )
        elif candidate.family == "climate_conditioning_appliance":
            _apply_delta(
                bucket,
                candidate,
                -14,
                reason="heating_accessory: heating-accessory context ruled out generic climate-conditioning family",
                confusable=True,
            )


def _display_pc_hybrid_matrix(
    candidates: Sequence[SubtypeCandidate],
    context: DomainDisambiguationContext,
    bucket: dict[str, list[tuple[int, str, str]]],
) -> None:
    display_head = _head_contains(context, "display", "monitor", "screen")
    pc_integrated = (
        _contains_fragment(context.integrated_feature, "pc", "computer")
        or _has_cue(context, "display_pc_hybrid_context")
        or _head_contains(context, "all in one pc")
    )
    if not (display_head and pc_integrated) and not _has_cue(context, "display_pc_hybrid_context"):
        return

    for candidate in candidates:
        if candidate.id == "all_in_one_pc":
            _apply_delta(
                bucket,
                candidate,
                38,
                reason="display_pc_hybrid: display with built-in PC or all-in-one wording matched the computing-display hybrid family",
                confusable=True,
            )
        elif candidate.family == "personal_computing_device":
            _apply_delta(
                bucket,
                candidate,
                18,
                reason="display_pc_hybrid: display-computing hybrid context supported the personal computing family",
                confusable=True,
            )
        elif candidate.id == "monitor":
            _apply_delta(
                bucket,
                candidate,
                -22,
                reason="display_pc_hybrid: integrated-PC cues outweighed a plain-monitor reading",
                confusable=True,
            )
        elif candidate.family == "display_device":
            _apply_delta(
                bucket,
                candidate,
                -12,
                reason="display_pc_hybrid: display-computing hybrid context weakened standalone display family",
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
    # Wave 5 — companion / hybrid disambiguation
    _companion_lock_bridge_matrix(candidates, context, bucket)
    _doorbell_chime_matrix(candidates, context, bucket)
    _ev_companion_module_matrix(candidates, context, bucket)
    _water_heating_vs_room_heating_matrix(candidates, context, bucket)
    _heating_accessory_matrix(candidates, context, bucket)
    _display_pc_hybrid_matrix(candidates, context, bucket)

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
