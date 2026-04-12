from __future__ import annotations

from dataclasses import dataclass

from .matching_runtime import _product_matching_snapshot
from .normalization import normalize

_EDGE_MODIFIER_TERMS = frozenset(
    {
        "all",
        "built",
        "desktop",
        "in",
        "mini",
        "mounted",
        "one",
        "portable",
        "rechargeable",
        "smart",
        "usb",
        "usb-c",
        "wall",
        "wifi",
        "wireless",
        "zigbee",
    }
)
_NON_HEAD_TAIL_TERMS = frozenset(
    {
        "bluetooth",
        "desktop",
        "portable",
        "rechargeable",
        "smart",
        "usb",
        "wall",
        "wifi",
        "wireless",
        "zigbee",
    }
)
_GOVERNED_HEAD_TERMS = frozenset(
    {
        "access keypad",
        "access panel",
        "backup unit",
        "chime receiver",
        "control module",
        "document camera",
        "entry panel",
        "eye mask",
        "garage door controller",
        "grow light",
        "grow light strip",
        "heating controller",
        "heated belt",
        "heated neck wrap",
        "heated shoulder wrap",
        "induction hot plate",
        "intercom",
        "kiosk display",
        "kvm switch",
        "lock bridge",
        "load balancing meter",
        "meter module",
        "microphone receiver",
        "monitor stand",
        "portable power station",
        "power station",
        "ring light",
        "relay module",
        "shower heater",
        "smart meter display",
        "smart meter gateway",
        "smoke co alarm",
        "studio light",
        "terminal display",
        "thin client",
        "underblanket controller",
        "ups backup unit",
        "video intercom",
        "visualizer",
        "wireless microphone receiver",
    }
)


@dataclass(frozen=True, slots=True)
class HeadCandidate:
    phrase: str
    head_term: str
    score: int
    source: str
    quality: str
    reasons: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class HeadResolution:
    primary: HeadCandidate | None = None
    ordered: tuple[HeadCandidate, ...] = ()
    competing: tuple[HeadCandidate, ...] = ()
    conflict_reason: str | None = None


def _trim_phrase_edges(tokens: tuple[str, ...]) -> tuple[str, ...]:
    if not tokens:
        return ()

    left = 0
    right = len(tokens)
    while left < right - 1 and tokens[left] in _EDGE_MODIFIER_TERMS:
        left += 1
    while right > left + 1 and tokens[right - 1] in _NON_HEAD_TAIL_TERMS:
        right -= 1
    return tokens[left:right]


def _candidate_variants(tokens: tuple[str, ...]) -> tuple[str, ...]:
    variants = {" ".join(tokens)}
    trimmed = _trim_phrase_edges(tokens)
    if trimmed:
        variants.add(" ".join(trimmed))
    if len(trimmed) >= 2 and trimmed[0] in {"smart", "wireless"}:
        variants.add(" ".join(trimmed[1:]))
    return tuple(variant for variant in sorted(variants, key=lambda value: (len(value.split()), value)) if variant)


def _segment_index(tokens: tuple[str, ...], phrase_tokens: tuple[str, ...]) -> int:
    if not phrase_tokens:
        return -1
    width = len(phrase_tokens)
    for idx in range(0, len(tokens) - width + 1):
        if tokens[idx : idx + width] == phrase_tokens:
            return idx
    return -1


def _governed_head_bonus(
    phrase: str,
    phrase_terms: set[str],
    segment_terms: set[str],
) -> tuple[int, str | None, list[str]]:
    reasons: list[str] = []
    head_term: str | None = None
    bonus = 0

    if "intercom" in phrase_terms:
        bonus += 30
        head_term = "video intercom" if "video" in phrase_terms else "intercom"
        reasons.append("intercom compound head")
    if "controller" in phrase_terms and "garage" in segment_terms and ("door" in segment_terms or "opener" in segment_terms):
        bonus += 34
        head_term = "garage door controller"
        reasons.append("garage-access controller head")
    if "module" in phrase_terms and {"garage", "opener"} & segment_terms:
        bonus += 28
        head_term = "control module"
        reasons.append("garage control-module head")
    if "receiver" in phrase_terms and {"microphone", "microphones", "mic", "mics", "lavalier", "stage"} & segment_terms:
        bonus += 34
        head_term = "wireless microphone receiver" if "wireless" in phrase_terms or "wireless" in segment_terms else "microphone receiver"
        reasons.append("microphone receiver head")
    if ({"ups", "backup"} <= segment_terms) or phrase in {"ups backup unit", "backup unit"}:
        if "ups" in phrase_terms or "backup" in phrase_terms or "unit" in phrase_terms:
            bonus += 34
            head_term = "ups backup unit" if "ups" in segment_terms else "backup unit"
            reasons.append("UPS or battery-backup head")
    if ({"document", "camera"} <= phrase_terms) or "visualizer" in phrase_terms:
        if {"document", "camera"} <= segment_terms or "visualizer" in segment_terms:
            bonus += 32
            head_term = "document camera" if {"document", "camera"} <= phrase_terms else "visualizer"
            reasons.append("document-camera visualizer head")
    if "recorder" in phrase_terms and {"camera", "cameras", "poe", "surveillance", "nvr", "dvr"} & segment_terms:
        bonus += 34
        if "poe" in phrase_terms or "poe" in segment_terms:
            head_term = "poe recorder"
        elif {"network", "video"} <= phrase_terms or {"nvr", "dvr"} & phrase_terms:
            head_term = "network video recorder"
        else:
            head_term = "video recorder"
        reasons.append("camera-system recorder head")
    if {"kvm", "switch"} <= phrase_terms:
        bonus += 38
        head_term = "kvm switch"
        reasons.append("KVM switch head")
    if "alarm" in phrase_terms and "smoke" in segment_terms and ({"co", "carbon", "monoxide"} & segment_terms):
        bonus += 36
        head_term = "smoke co alarm"
        reasons.append("smoke and carbon-monoxide alarm head")
    if {"power", "station"} <= phrase_terms:
        bonus += 32
        head_term = "portable power station" if "portable" in segment_terms else "power station"
        reasons.append("portable power-station head")
    if {"eye", "mask"} <= phrase_terms:
        bonus += 28
        head_term = "eye mask"
        reasons.append("heated wearable mask head")
    if {"thin", "client"} <= phrase_terms:
        bonus += 26
        head_term = "thin client"
        reasons.append("thin-client head")
    if {"all", "in", "one", "pc"} <= phrase_terms:
        bonus += 26
        head_term = "all in one pc"
        reasons.append("all-in-one PC head")
    if {"monitor", "arm"} <= phrase_terms:
        bonus += 28
        head_term = "monitor arm"
        reasons.append("monitor-arm host head")
    if {"monitor", "stand"} <= phrase_terms:
        bonus += 24
        head_term = "monitor stand"
        reasons.append("monitor-stand host head")

    # Companion / hybrid governed heads — wave 5
    if "chime" in phrase_terms and {"receiver", "box", "unit"} & (phrase_terms | segment_terms):
        bonus += 30
        head_term = "chime receiver"
        reasons.append("doorbell chime receiver head")
    if "panel" in phrase_terms and {"entry", "door", "access"} & (phrase_terms | segment_terms):
        bonus += 26
        head_term = "entry panel"
        reasons.append("access entry panel compound head")
    if "keypad" in phrase_terms and {"access", "entry", "door", "gate"} & (phrase_terms | segment_terms):
        bonus += 28
        head_term = "access keypad"
        reasons.append("building-access keypad head")
    if "bridge" in phrase_terms and {"lock", "gateway"} & (phrase_terms | segment_terms):
        bonus += 26
        head_term = "lock bridge"
        reasons.append("companion lock-bridge or gateway head")
    if "relay" in phrase_terms and "module" in phrase_terms:
        bonus += 24
        head_term = "relay module"
        reasons.append("relay control module head")
    if {"load", "balancing", "meter"} <= phrase_terms or (
        "meter" in phrase_terms and {"load", "balancing"} & segment_terms
    ):
        bonus += 30
        head_term = "load balancing meter"
        reasons.append("EV load-balancing meter head")
    if "meter" in phrase_terms and "module" in phrase_terms and {"ev", "load", "balancing", "energy"} & segment_terms:
        bonus += 26
        head_term = "meter module"
        reasons.append("EV energy meter module head")
    if "display" in phrase_terms and "meter" in phrase_terms and {"smart", "energy"} & (phrase_terms | segment_terms):
        bonus += 28
        head_term = "smart meter display"
        reasons.append("smart-meter display head")
    if "gateway" in phrase_terms and "meter" in phrase_terms:
        bonus += 28
        head_term = "smart meter gateway"
        reasons.append("smart-meter gateway head")
    if {"grow", "light"} <= phrase_terms:
        bonus += 30
        head_term = "grow light strip" if "strip" in phrase_terms or "strip" in segment_terms else "grow light"
        reasons.append("grow-light compound head")
    if {"ring", "light"} <= phrase_terms:
        bonus += 24
        head_term = "ring light"
        reasons.append("ring-light head")
    if {"studio", "light"} <= phrase_terms:
        bonus += 22
        head_term = "studio light"
        reasons.append("studio-light head")
    if "shower" in phrase_terms and "heater" in phrase_terms:
        bonus += 28
        head_term = "shower heater"
        reasons.append("electric shower water-heater head")
    if {"induction", "hot", "plate"} <= phrase_terms or {"induction", "cooker"} <= phrase_terms:
        bonus += 30
        head_term = "induction hot plate"
        reasons.append("portable induction hot-plate head")
    if {"kiosk", "display"} <= phrase_terms:
        bonus += 30
        head_term = "kiosk display"
        reasons.append("kiosk-display hybrid head")
    if {"terminal", "display"} <= phrase_terms or ({"touch", "display"} <= phrase_terms and "terminal" in segment_terms):
        bonus += 28
        head_term = "terminal display"
        reasons.append("terminal-display hybrid head")
    if (
        "controller" in phrase_terms
        and {"underblanket", "blanket"} & segment_terms
        and "heating" not in phrase_terms
    ):
        bonus += 24
        head_term = "underblanket controller"
        reasons.append("underblanket controller head")
    if {"heated", "neck", "wrap"} <= phrase_terms:
        bonus += 28
        head_term = "heated neck wrap"
        reasons.append("heated wellness-wrap head")
    if {"heated", "shoulder", "wrap"} <= phrase_terms:
        bonus += 28
        head_term = "heated shoulder wrap"
        reasons.append("heated wellness-wrap head")
    if {"heated", "belt"} <= phrase_terms:
        bonus += 26
        head_term = "heated belt"
        reasons.append("heated wellness-belt head")
    # Display + built-in PC hybrid: detect "pc" or "computer" in the phrase while "display" is nearby
    if "pc" in phrase_terms and {"display", "monitor", "screen"} & (phrase_terms | segment_terms):
        bonus += 26
        head_term = "all in one pc"
        reasons.append("display-computing hybrid head (built-in PC)")
    if "computer" in phrase_terms and {"display", "monitor", "screen"} & (phrase_terms | segment_terms):
        bonus += 22
        head_term = "all in one pc"
        reasons.append("display-computing hybrid head (integrated computer)")

    return bonus, head_term, reasons


def _head_quality(score: int, competing_score: int | None) -> str:
    gap = score - competing_score if competing_score is not None else score
    if score >= 88 and gap >= 12:
        return "high"
    if score >= 56 and gap >= 6:
        return "medium"
    return "low"


def resolve_primary_head(segment: str) -> HeadResolution:
    segment = normalize(segment)
    if not segment:
        return HeadResolution()

    snapshot = _product_matching_snapshot()
    known_phrases = {phrase.normalized for phrase in snapshot.head_phrases}
    known_terms = set(snapshot.head_terms) | {term.split()[-1] for term in _GOVERNED_HEAD_TERMS}
    segment_tokens = tuple(segment.split())
    segment_terms = set(segment_tokens)
    candidates: dict[str, HeadCandidate] = {}
    built_into_index = segment.find("built into")

    for left in range(len(segment_tokens)):
        for right in range(left + 1, min(len(segment_tokens), left + 6) + 1):
            window_tokens = segment_tokens[left:right]
            for phrase in _candidate_variants(window_tokens):
                phrase_tokens = tuple(phrase.split())
                if not phrase_tokens:
                    continue
                phrase_terms = set(phrase_tokens)
                known_phrase = phrase in known_phrases
                bonus, governed_head_term, governed_reasons = _governed_head_bonus(phrase, phrase_terms, segment_terms)
                head_term = governed_head_term or phrase
                tail = head_term.split()[-1]
                if not known_phrase and not bonus and tail not in known_terms and head_term not in _GOVERNED_HEAD_TERMS:
                    continue

                reasons: list[str] = []
                score = len(phrase_tokens) * 10
                if known_phrase:
                    score += 26
                    reasons.append("catalog head phrase")
                if tail in known_terms:
                    score += 10
                    reasons.append(f"governed head term '{tail}'")
                if bonus:
                    score += bonus
                    reasons.extend(governed_reasons)
                if phrase_tokens[-1] in _NON_HEAD_TAIL_TERMS:
                    score -= 26
                    reasons.append(f"trimmed away weak tail '{phrase_tokens[-1]}'")
                phrase_index = _segment_index(segment_tokens, phrase_tokens)
                if phrase_index >= 0:
                    end_distance = len(segment_tokens) - (phrase_index + len(phrase_tokens))
                    score += max(0, 12 - end_distance * 3)
                    if built_into_index >= 0 and phrase_index >= len(segment[:built_into_index].split()):
                        score += 10
                        reasons.append("phrase stayed on the host side of 'built into'")
                if left == 0:
                    score += 4
                    reasons.append("phrase started at the product lead")
                if tail in {"unit", "box", "station"} and bonus == 0:
                    score -= 10
                    reasons.append("generic system noun needed stronger support")

                source = "catalog_head_phrase" if known_phrase else "governed_head_rule"
                existing = candidates.get(phrase)
                if existing is None or score > existing.score:
                    candidates[phrase] = HeadCandidate(
                        phrase=phrase,
                        head_term=head_term,
                        score=score,
                        source=source,
                        quality="low",
                        reasons=tuple(reasons),
                    )

    if not candidates:
        fallback_tokens = _trim_phrase_edges(segment_tokens)
        fallback_phrase = " ".join(fallback_tokens or segment_tokens[-1:])
        if not fallback_phrase:
            return HeadResolution()
        fallback = HeadCandidate(
            phrase=fallback_phrase,
            head_term=fallback_phrase,
            score=8,
            source="tail_fallback",
            quality="low",
            reasons=("fallback to the last viable noun span",),
        )
        return HeadResolution(primary=fallback, ordered=(fallback,))

    ordered = sorted(
        candidates.values(),
        key=lambda candidate: (-candidate.score, -len(candidate.phrase.split()), candidate.phrase),
    )
    competing_score = ordered[1].score if len(ordered) > 1 else None
    primary = HeadCandidate(
        phrase=ordered[0].phrase,
        head_term=ordered[0].head_term,
        score=ordered[0].score,
        source=ordered[0].source,
        quality=_head_quality(ordered[0].score, competing_score),
        reasons=ordered[0].reasons,
    )
    competing = tuple(
        HeadCandidate(
            phrase=candidate.phrase,
            head_term=candidate.head_term,
            score=candidate.score,
            source=candidate.source,
            quality=_head_quality(candidate.score, primary.score),
            reasons=candidate.reasons,
        )
        for candidate in ordered[1:4]
        if candidate.score >= primary.score - 8 and candidate.head_term != primary.head_term
    )
    conflict_reason = None
    if competing:
        conflict_reason = "Competing governed head spans remained close, so subtype precision should stay conservative."
    ordered_with_quality = tuple(
        primary
        if idx == 0
        else HeadCandidate(
            phrase=candidate.phrase,
            head_term=candidate.head_term,
            score=candidate.score,
            source=candidate.source,
            quality=_head_quality(candidate.score, primary.score),
            reasons=candidate.reasons,
        )
        for idx, candidate in enumerate(ordered[:5])
    )
    return HeadResolution(
        primary=primary,
        ordered=ordered_with_quality,
        competing=competing,
        conflict_reason=conflict_reason,
    )


__all__ = ["HeadCandidate", "HeadResolution", "resolve_primary_head"]
