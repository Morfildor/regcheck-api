from __future__ import annotations

from dataclasses import dataclass
import re

from .head_resolution import HeadCandidate, resolve_primary_head
from .models import HeadCandidateAudit, RoleParseAudit
from .normalization import normalize
from .signal_config import get_classifier_signal_snapshot

_ROLE_PARSE_PRIORITY = {
    "built_into": 0,
    "with_integrated": 0,
    "with_built_in_pc": 0,
    "built_in": 1,
    "charger_for": 2,
    "controller_for": 3,
    "injector_for": 4,
    "backup_for": 5,
    "hub_for": 6,
    "gateway_for": 7,
    "dock_for": 8,
    "receiver_for": 9,
    "adapter_for": 10,
    "module_for": 11,
    "meter_for": 11,
    "panel_for": 12,
    "unit_for": 13,
    "box_for": 14,
    "station_for": 15,
    "visualizer_for": 16,
    "monitoring_for": 17,
    "for": 20,
    "with": 30,
    "mounted_on": 40,
    "mounted_for": 41,
}
_BINARY_ROLES = frozenset(
    {
        "target_device",
        "controlled_device",
        "charged_device",
        "powered_device",
        "host_device",
        "integrated_feature",
        "mounted_on_or_for",
    }
)
_PREFIX_ROLE_BY_HEAD = {
    "adapter": "target_device",
    "access keypad": "target_device",
    "backup": "powered_device",
    "backup unit": "powered_device",
    "bracket": "mounted_on_or_for",
    "bridge": "host_device",
    "charger": "charged_device",
    "chime": "target_device",
    "chime receiver": "target_device",
    "control module": "controlled_device",
    "controller": "controlled_device",
    "dock": "host_device",
    "entry panel": "target_device",
    "gateway": "host_device",
    "hub": "host_device",
    "injector": "powered_device",
    "keypad": "target_device",
    "lock bridge": "host_device",
    "load balancing meter": "target_device",
    "meter module": "target_device",
    "module": "target_device",
    "mount": "mounted_on_or_for",
    "panel": "target_device",
    "reader": "target_device",
    "receiver": "target_device",
    "relay module": "target_device",
    "smart meter display": "target_device",
    "smart meter gateway": "target_device",
    "stand": "mounted_on_or_for",
    "terminal": "target_device",
    "transmitter": "target_device",
    "underblanket controller": "target_device",
}
_ACCESSORY_HEAD_TERMS = frozenset(
    {
        "adapter",
        "arm",
        "backup",
        "bracket",
        "bridge",
        "cable",
        "chime",
        "connector",
        "dock",
        "gateway",
        "hub",
        "injector",
        "keypad",
        "module",
        "mount",
        "panel",
        "reader",
        "receiver",
        "stand",
        "terminal",
        "transmitter",
        "ups",
    }
)
_ACCESSORY_HEAD_PHRASES = frozenset(
    {
        "backup unit",
        "chime receiver",
        "control module",
        "docking station",
        "entry panel",
        "gateway",
        "lock bridge",
        "load balancing meter",
        "meter module",
        "monitor stand",
        "receiver",
        "relay module",
        "smart meter display",
        "smart meter gateway",
        "terminal",
        "underblanket controller",
        "ups backup unit",
    }
)
_PREFIX_FILLER_TERMS = frozenset(
    {
        "all",
        "built",
        "ceiling",
        "connected",
        "desktop",
        "digital",
        "home",
        "in",
        "mini",
        "portable",
        "smart",
        "wall",
        "wireless",
    }
)
_SECONDARY_STOP_PATTERNS = tuple(
    re.compile(pattern)
    for pattern in (
        r"\bwith integrated\b",
        r"\bwith\b",
        r"\bbuilt in\b",
        r"\bbuilt-in\b",
        r"\bbuilt into\b",
        r"\bmounted on\b",
        r"\bmounted for\b",
    )
)
_REVERSE_INTEGRATED_PATTERNS = tuple(
    re.compile(pattern)
    for pattern in (
        r"\bbuilt into\b",
        r"\bintegrated into\b",
        r"\bbuilt in to\b",
    )
)
_DECISIVE_FULL_HEAD_FRAGMENTS = frozenset(
    {
        "access keypad",
        "bridge",
        "chime receiver",
        "controller",
        "control module",
        "entry panel",
        "gateway",
        "grow light strip",
        "induction hot plate",
        "kiosk display",
        "kvm switch",
        "load balancing meter",
        "meter module",
        "panel",
        "poe recorder",
        "receiver",
        "relay module",
        "shower heater",
        "smart meter display",
        "smart meter gateway",
        "terminal display",
        "underblanket controller",
        "video recorder",
        "visualizer",
    }
)
_GENERIC_PRIMARY_HEAD_TAILS = frozenset({"box", "camera", "display", "monitor", "station", "system", "unit"})


@dataclass(frozen=True, slots=True)
class ProductRoleParse:
    primary_product_phrase: str | None = None
    primary_product_head: str | None = None
    primary_product_head_term: str | None = None
    primary_head_quality: str | None = None
    primary_head_candidates: tuple[str, ...] = ()
    competing_primary_heads: tuple[str, ...] = ()
    head_candidate_details: tuple[HeadCandidate, ...] = ()
    accessory_or_attachment: tuple[str, ...] = ()
    target_device: tuple[str, ...] = ()
    controlled_device: tuple[str, ...] = ()
    charged_device: tuple[str, ...] = ()
    powered_device: tuple[str, ...] = ()
    host_device: tuple[str, ...] = ()
    mounted_on_or_for: tuple[str, ...] = ()
    integrated_feature: tuple[str, ...] = ()
    installation_context: tuple[str, ...] = ()
    cue_hits: tuple[str, ...] = ()
    parse_notes: tuple[str, ...] = ()
    primary_head_source: str | None = None
    primary_is_accessory: bool = False
    primary_head_conflict: bool = False
    head_conflict_reason: str | None = None

    def role_values(self, role_name: str) -> tuple[str, ...]:
        return tuple(getattr(self, role_name, ()) or ())

    def to_audit(self) -> RoleParseAudit:
        return RoleParseAudit(
            primary_product_phrase=self.primary_product_phrase,
            primary_product_head=self.primary_product_head,
            primary_product_head_term=self.primary_product_head_term,
            primary_head_quality=self.primary_head_quality,
            primary_head_candidates=self.primary_head_candidates,
            competing_primary_heads=self.competing_primary_heads,
            head_candidate_details=tuple(
                HeadCandidateAudit(
                    phrase=item.phrase,
                    head_term=item.head_term,
                    score=item.score,
                    source=item.source,
                    quality=item.quality,
                    reasons=item.reasons,
                )
                for item in self.head_candidate_details
            ),
            accessory_or_attachment=self.accessory_or_attachment,
            target_device=self.target_device,
            controlled_device=self.controlled_device,
            charged_device=self.charged_device,
            powered_device=self.powered_device,
            host_device=self.host_device,
            mounted_on_or_for=self.mounted_on_or_for,
            integrated_feature=self.integrated_feature,
            installation_context=self.installation_context,
            cue_hits=self.cue_hits,
            parse_notes=self.parse_notes,
            primary_head_source=self.primary_head_source,
            primary_is_accessory=self.primary_is_accessory,
            primary_head_conflict=self.primary_head_conflict,
            head_conflict_reason=self.head_conflict_reason,
        )


def _clean_fragment(text: str) -> str:
    cleaned = normalize(text)
    return cleaned.strip()


def _truncate_secondary_fragment(text: str) -> str:
    fragment = _clean_fragment(text)
    if not fragment:
        return ""
    cut_points = [match.start() for pattern in _SECONDARY_STOP_PATTERNS if (match := pattern.search(fragment))]
    if cut_points:
        fragment = fragment[: min(cut_points)].strip()
    return fragment


def _prefer_full_phrase_head(primary: HeadCandidate | None, full: HeadCandidate | None) -> bool:
    if full is None:
        return False
    if primary is None:
        return True
    full_term = (full.head_term or full.phrase).strip()
    primary_term = (primary.head_term or primary.phrase).strip()
    if not full_term or full_term == primary_term:
        return False
    if not any(fragment in full_term for fragment in _DECISIVE_FULL_HEAD_FRAGMENTS):
        return False
    primary_tail = primary_term.split()[-1] if primary_term else ""
    if primary_tail in _GENERIC_PRIMARY_HEAD_TAILS:
        return True
    return full.score >= primary.score + 14


def _clean_prefix_phrase(text: str) -> str:
    tokens = [token for token in _clean_fragment(text).split() if token not in _PREFIX_FILLER_TERMS]
    if len(tokens) > 1 and tokens[0] in {"usb", "usb-c", "usb4"}:
        return " ".join(tokens[:2]).strip()
    return " ".join(tokens).strip()


def _dedupe(values: list[str]) -> tuple[str, ...]:
    seen: set[str] = set()
    ordered: list[str] = []
    for value in values:
        if not value or value in seen:
            continue
        seen.add(value)
        ordered.append(value)
    return tuple(ordered)


def _for_boundary_index(text: str, match: re.Match[str]) -> int | None:
    for_match = re.search(r"\bfor\b", text[match.start() : match.end()])
    if for_match is None:
        for_match = re.search(r"\bfor\b", text[match.start() :])
        if for_match is None:
            return None
        return match.start() + for_match.start()
    return match.start() + for_match.start()


def _best_binary_relation(text: str) -> tuple[str, str, re.Match[str]] | None:
    snapshot = get_classifier_signal_snapshot()
    best: tuple[int, int, int, str, str, re.Match[str]] | None = None

    for role_name, cue_map in snapshot.compiled_relation_cue_packs.items():
        if role_name == "installation_context":
            continue
        for cue_name, patterns in cue_map.items():
            if role_name not in _BINARY_ROLES:
                continue
            for pattern in patterns:
                match = pattern.search(text)
                if match is None:
                    continue
                rank = _ROLE_PARSE_PRIORITY.get(cue_name, 99)
                candidate = (rank, match.start(), -len(match.group(0)), role_name, cue_name, match)
                if best is None or candidate < best:
                    best = candidate
                break

    if best is None:
        return None
    return best[3], best[4], best[5]


def _installation_context_hits(text: str) -> tuple[tuple[str, ...], tuple[str, ...]]:
    snapshot = get_classifier_signal_snapshot()
    values: list[str] = []
    cue_hits: list[str] = []
    for cue_name, patterns in snapshot.compiled_relation_cue_packs.get("installation_context", {}).items():
        for pattern in patterns:
            match = pattern.search(text)
            if match is None:
                continue
            values.append(_clean_fragment(match.group(0)))
            cue_hits.append(cue_name)
            break
    return _dedupe(values), _dedupe(cue_hits)


def _strip_installation_prefix(text: str) -> str:
    result = text
    for value in _installation_context_hits(text)[0]:
        if result.startswith(value + " "):
            result = result[len(value) :].strip()
    return result


def _infer_prefixed_role(primary_phrase: str, primary_head: str, primary_head_term: str | None) -> tuple[str | None, str | None]:
    if not primary_phrase or not primary_head:
        return None, None
    if not primary_phrase.endswith(primary_head):
        return None, None
    prefix = _clean_prefix_phrase(primary_phrase[: -len(primary_head)])
    if not prefix:
        return None, None
    head_key = (primary_head_term or primary_head).strip()
    head_tail = head_key.split()[-1]
    return _PREFIX_ROLE_BY_HEAD.get(head_key) or _PREFIX_ROLE_BY_HEAD.get(head_tail), prefix


def _reverse_integrated_relation(text: str) -> tuple[str, str] | None:
    for pattern in _REVERSE_INTEGRATED_PATTERNS:
        match = pattern.search(text)
        if match is None:
            continue
        left_fragment = _truncate_secondary_fragment(text[: match.start()])
        right_fragment = _truncate_secondary_fragment(text[match.end() :])
        if left_fragment and right_fragment:
            return right_fragment, left_fragment
    return None


def parse_product_roles(text: str) -> ProductRoleParse:
    normalized = _clean_fragment(text)
    if not normalized:
        return ProductRoleParse()

    notes: list[str] = []
    cue_hits: list[str] = []
    installation_context, installation_cues = _installation_context_hits(normalized)
    cue_hits.extend(installation_cues)
    if installation_context:
        notes.append(f"installation context: {', '.join(installation_context)}")

    relation_match = _best_binary_relation(normalized)
    primary_phrase = _strip_installation_prefix(normalized)
    role_values: dict[str, list[str]] = {
        "accessory_or_attachment": [],
        "target_device": [],
        "controlled_device": [],
        "charged_device": [],
        "powered_device": [],
        "host_device": [],
        "mounted_on_or_for": [],
        "integrated_feature": [],
    }
    reverse_integrated = _reverse_integrated_relation(primary_phrase)
    if reverse_integrated is not None:
        primary_phrase, integrated_feature = reverse_integrated
        role_values["integrated_feature"].append(integrated_feature)
        cue_hits.append("built_into")
        notes.append(f"integrated feature: {integrated_feature}")

    if relation_match is not None:
        role_name, cue_name, match = relation_match
        cue_hits.append(cue_name)
        if role_name in {"target_device", "controlled_device", "charged_device", "powered_device", "host_device"}:
            boundary = _for_boundary_index(normalized, match)
            if boundary is not None:
                primary_phrase = normalized[:boundary].strip()
                secondary_fragment = _truncate_secondary_fragment(normalized[boundary + len("for") :])
                if secondary_fragment:
                    role_values[role_name].append(secondary_fragment)
                    notes.append(f"{role_name.replace('_', ' ')}: {secondary_fragment}")
        elif role_name in {"integrated_feature", "mounted_on_or_for"}:
            if cue_name != "built_into":
                primary_phrase = normalized[: match.start()].strip() or primary_phrase
            secondary_fragment = _truncate_secondary_fragment(normalized[match.end() :])
            if secondary_fragment:
                role_values[role_name].append(secondary_fragment)
                notes.append(f"{role_name.replace('_', ' ')}: {secondary_fragment}")

    primary_phrase = _clean_fragment(primary_phrase or normalized)
    head_resolution = resolve_primary_head(primary_phrase)
    head_candidate = head_resolution.primary
    if relation_match is not None and relation_match[0] in {"integrated_feature", "mounted_on_or_for"}:
        full_head_resolution = resolve_primary_head(normalized)
        full_head_candidate = full_head_resolution.primary
        if full_head_candidate is not None and _prefer_full_phrase_head(head_candidate, full_head_candidate):
            head_resolution = full_head_resolution
            head_candidate = full_head_candidate
            notes.append(
                f"primary head kept full-phrase span '{full_head_candidate.phrase}' because it was more decisive than the relation-truncated span"
            )
    primary_head = head_candidate.phrase if head_candidate is not None else None
    primary_head_term = head_candidate.head_term if head_candidate is not None else None
    primary_head_source = head_candidate.source if head_candidate is not None else None
    primary_head_quality = head_candidate.quality if head_candidate is not None else None
    head_candidates = tuple(candidate.phrase for candidate in head_resolution.ordered[:5])
    competing_heads = tuple(candidate.phrase for candidate in head_resolution.competing[:3])
    if primary_head:
        notes.append(
            f"primary head '{primary_head}' ({primary_head_term or primary_head}) from {primary_head_source or 'direct phrase'}"
        )
    if head_resolution.conflict_reason:
        notes.append(head_resolution.conflict_reason)

    prefixed_role, prefixed_value = _infer_prefixed_role(primary_phrase, primary_head or "", primary_head_term)
    if prefixed_role and prefixed_value:
        role_values[prefixed_role].append(prefixed_value)
        primary_head_tail = (primary_head_term or primary_head or "").split()[-1] if primary_head or primary_head_term else "primary"
        cue_hits.append(f"{primary_head_tail}_prefix")
        notes.append(f"{prefixed_role.replace('_', ' ')} inferred from primary phrase: {prefixed_value}")

    accessory_key = (primary_head_term or primary_head or "").strip()
    primary_is_accessory = bool(
        accessory_key in _ACCESSORY_HEAD_PHRASES or accessory_key.split()[-1] in _ACCESSORY_HEAD_TERMS
    )
    integrated_text = " ".join(role_values["integrated_feature"])
    if primary_is_accessory and accessory_key in {"access keypad", "entry panel"}:
        if any(fragment in integrated_text for fragment in ("intercom", "camera")) or any(
            fragment in primary_phrase for fragment in ("gate", "entry", "door access", "access keypad")
        ):
            primary_is_accessory = False
            notes.append("building-access keypad or entry-panel wording stayed as the main entry device")
    if primary_is_accessory and primary_phrase:
        role_values["accessory_or_attachment"].append(primary_phrase)
        notes.append(f"accessory attachment primary phrase: {primary_phrase}")

    return ProductRoleParse(
        primary_product_phrase=primary_phrase or None,
        primary_product_head=primary_head,
        primary_product_head_term=primary_head_term,
        primary_head_quality=primary_head_quality,
        primary_head_candidates=head_candidates,
        competing_primary_heads=competing_heads,
        head_candidate_details=head_resolution.ordered,
        accessory_or_attachment=_dedupe(role_values["accessory_or_attachment"]),
        target_device=_dedupe(role_values["target_device"]),
        controlled_device=_dedupe(role_values["controlled_device"]),
        charged_device=_dedupe(role_values["charged_device"]),
        powered_device=_dedupe(role_values["powered_device"]),
        host_device=_dedupe(role_values["host_device"]),
        mounted_on_or_for=_dedupe(role_values["mounted_on_or_for"]),
        integrated_feature=_dedupe(role_values["integrated_feature"]),
        installation_context=installation_context,
        cue_hits=_dedupe(cue_hits),
        parse_notes=_dedupe(notes),
        primary_head_source=primary_head_source,
        primary_is_accessory=primary_is_accessory,
        primary_head_conflict=bool(competing_heads),
        head_conflict_reason=head_resolution.conflict_reason,
    )


__all__ = ["ProductRoleParse", "parse_product_roles"]
