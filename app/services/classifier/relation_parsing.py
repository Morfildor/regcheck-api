from __future__ import annotations

from dataclasses import dataclass
import re

from .matching_runtime import _product_matching_snapshot
from .models import RoleParseAudit
from .normalization import normalize
from .signal_config import get_classifier_signal_snapshot

_ROLE_PARSE_PRIORITY = {
    "with_integrated": 0,
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
    "panel_for": 12,
    "monitoring_for": 13,
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
    "backup": "powered_device",
    "bracket": "mounted_on_or_for",
    "charger": "charged_device",
    "controller": "controlled_device",
    "dock": "host_device",
    "gateway": "host_device",
    "hub": "host_device",
    "injector": "powered_device",
    "keypad": "target_device",
    "module": "target_device",
    "mount": "mounted_on_or_for",
    "panel": "target_device",
    "reader": "target_device",
    "receiver": "target_device",
    "stand": "mounted_on_or_for",
    "terminal": "target_device",
    "transmitter": "target_device",
}
_ACCESSORY_HEAD_TERMS = frozenset(
    {
        "adapter",
        "arm",
        "backup",
        "bracket",
        "cable",
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
        r"\bmounted on\b",
        r"\bmounted for\b",
    )
)


@dataclass(frozen=True, slots=True)
class _HeadCandidate:
    phrase: str
    score: int
    source: str


@dataclass(frozen=True, slots=True)
class ProductRoleParse:
    primary_product_phrase: str | None = None
    primary_product_head: str | None = None
    primary_head_candidates: tuple[str, ...] = ()
    competing_primary_heads: tuple[str, ...] = ()
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

    def role_values(self, role_name: str) -> tuple[str, ...]:
        return tuple(getattr(self, role_name, ()) or ())

    def to_audit(self) -> RoleParseAudit:
        return RoleParseAudit(
            primary_product_phrase=self.primary_product_phrase,
            primary_product_head=self.primary_product_head,
            primary_head_candidates=self.primary_head_candidates,
            competing_primary_heads=self.competing_primary_heads,
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


def _detect_primary_heads(segment: str) -> tuple[_HeadCandidate | None, tuple[str, ...], tuple[str, ...]]:
    segment = _clean_fragment(segment)
    if not segment:
        return None, (), ()

    snapshot = _product_matching_snapshot()
    known_phrases = {phrase.normalized for phrase in snapshot.head_phrases}
    known_terms = set(snapshot.head_terms) | set(_ACCESSORY_HEAD_TERMS)
    tokens = segment.split()
    start_index = max(0, len(tokens) - 6)
    candidates: dict[str, _HeadCandidate] = {}

    for left in range(start_index, len(tokens)):
        for right in range(left + 1, min(len(tokens), left + 4) + 1):
            phrase = " ".join(tokens[left:right])
            tail = phrase.split()[-1]
            if phrase not in known_phrases and tail not in known_terms:
                continue
            score = len(phrase.split()) * 12
            if phrase in known_phrases:
                score += 10
            if tail in known_terms:
                score += 8
            end_distance = len(tokens) - right
            score += max(0, 12 - end_distance * 4)
            source = "catalog_head_phrase" if phrase in known_phrases else "generic_head_term"
            existing = candidates.get(phrase)
            if existing is None or score > existing.score:
                candidates[phrase] = _HeadCandidate(phrase=phrase, score=score, source=source)

    if not candidates:
        tail = tokens[-1]
        return _HeadCandidate(phrase=tail, score=8, source="tail_fallback"), (tail,), ()

    ordered = sorted(candidates.values(), key=lambda row: (-row.score, -len(row.phrase.split()), row.phrase))
    primary = ordered[0]
    competing = tuple(
        candidate.phrase
        for candidate in ordered[1:]
        if candidate.score >= primary.score - 4 and candidate.phrase != primary.phrase
    )
    return primary, tuple(candidate.phrase for candidate in ordered[:4]), competing[:3]


def _infer_prefixed_role(primary_phrase: str, primary_head: str) -> tuple[str | None, str | None]:
    if not primary_phrase or not primary_head:
        return None, None
    if not primary_phrase.endswith(primary_head):
        return None, None
    prefix = _clean_prefix_phrase(primary_phrase[: -len(primary_head)])
    if not prefix:
        return None, None
    head_tail = primary_head.split()[-1]
    return _PREFIX_ROLE_BY_HEAD.get(head_tail), prefix


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
            primary_phrase = normalized[: match.start()].strip() or primary_phrase
            secondary_fragment = _truncate_secondary_fragment(normalized[match.end() :])
            if secondary_fragment:
                role_values[role_name].append(secondary_fragment)
                notes.append(f"{role_name.replace('_', ' ')}: {secondary_fragment}")

    primary_phrase = _clean_fragment(primary_phrase or normalized)
    head_candidate, head_candidates, competing_heads = _detect_primary_heads(primary_phrase)
    primary_head = head_candidate.phrase if head_candidate is not None else None
    primary_head_source = head_candidate.source if head_candidate is not None else None
    if primary_head:
        notes.append(f"primary head '{primary_head}' from {primary_head_source or 'direct phrase'}")

    prefixed_role, prefixed_value = _infer_prefixed_role(primary_phrase, primary_head or "")
    if prefixed_role and prefixed_value:
        role_values[prefixed_role].append(prefixed_value)
        primary_head_tail = (primary_head or "").split()[-1] if primary_head else "primary"
        cue_hits.append(f"{primary_head_tail}_prefix")
        notes.append(f"{prefixed_role.replace('_', ' ')} inferred from primary phrase: {prefixed_value}")

    primary_is_accessory = bool(primary_head and primary_head.split()[-1] in _ACCESSORY_HEAD_TERMS)
    if primary_is_accessory and primary_phrase:
        role_values["accessory_or_attachment"].append(primary_phrase)
        notes.append(f"accessory attachment primary phrase: {primary_phrase}")

    return ProductRoleParse(
        primary_product_phrase=primary_phrase or None,
        primary_product_head=primary_head,
        primary_head_candidates=head_candidates,
        competing_primary_heads=competing_heads,
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
    )


__all__ = ["ProductRoleParse", "parse_product_roles"]
