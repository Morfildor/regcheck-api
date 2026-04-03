from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.services.knowledge_base.taxonomy import RouteAnchorDefinition, get_taxonomy_snapshot

from .boundary_decisions import BoundaryDecision, decide_boundary


CONNECTED_ROUTE_TRAITS = {
    "account",
    "account_required",
    "app_control",
    "authentication",
    "bluetooth",
    "cellular",
    "cloud",
    "cloud_dependent",
    "internet",
    "internet_connected",
    "matter",
    "ota",
    "radio",
    "thread",
    "wifi",
    "zigbee",
}

WEARABLE_ROUTE_TRAITS = {"wearable", "body_worn_or_applied", "close_proximity_emf"}

_CONFIDENCE_RANK = {"low": 0, "medium": 1, "high": 2}


@dataclass(frozen=True, slots=True)
class RouteAnchorReason:
    kind: str
    detail: str
    weight: int


@dataclass(frozen=True, slots=True)
class RouteAnchorCandidate:
    anchor: str
    route_family: str
    score: int
    reasons: tuple[RouteAnchorReason, ...]


@dataclass(frozen=True, slots=True)
class RouteAnchorDecision:
    anchor: str | None
    route_family: str | None
    confidence: str
    score: int
    source: str
    reasons: tuple[str, ...]
    alternatives: tuple[str, ...]
    boundary_decision: BoundaryDecision


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if isinstance(item, str) and str(item).strip()]


def normalized_standard_codes(codes: set[str] | list[str] | None) -> list[str]:
    normalized: list[str] = []
    seen: set[str] = set()
    for raw_code in codes or []:
        code = str(raw_code or "").upper().replace("  ", " ").strip()
        if not code or code in seen:
            continue
        seen.add(code)
        normalized.append(code)
    return normalized


def route_anchor_rules() -> dict[str, RouteAnchorDefinition]:
    return get_taxonomy_snapshot().route_anchors_by_id


def route_family_scope_map() -> dict[str, str]:
    return {definition.route_family: definition.scope for definition in route_anchor_rules().values()}


def route_family_primary_directive_map() -> dict[str, str]:
    return {
        definition.route_family: definition.primary_directive
        for definition in route_anchor_rules().values()
        if definition.primary_directive
    }


def route_standard_family_rules() -> tuple[tuple[str, str, str], ...]:
    rules: list[tuple[str, str, str]] = []
    for definition in route_anchor_rules().values():
        for candidate in definition.exact_primary_candidates:
            rules.append((candidate.upper(), definition.route_family, definition.label))
        for prefix in definition.prefix_primary_candidates:
            rules.append((prefix.upper(), definition.route_family, definition.label))
    ordered: list[tuple[str, str, str]] = []
    seen: set[tuple[str, str, str]] = set()
    for rule in sorted(rules, key=lambda item: (-len(item[0]), item[1], item[0])):
        if rule in seen:
            continue
        seen.add(rule)
        ordered.append(rule)
    return tuple(ordered)


def family_from_standard_code(code: str, prefer_wearable: bool) -> str | None:
    normalized = str(code or "").upper().replace("  ", " ").strip()
    for prefix, family, _label in route_standard_family_rules():
        if normalized.startswith(prefix):
            if family == "av_ict" and prefer_wearable:
                return "av_ict_wearable"
            return family
    return None


def best_primary_standard_for_family(route_family: str, preferred_codes: list[str]) -> str | None:
    family_codes: list[str] = []
    for code in preferred_codes:
        generic_family = family_from_standard_code(code, prefer_wearable=False)
        wearable_family = family_from_standard_code(code, prefer_wearable=True)
        if route_family in {generic_family, wearable_family}:
            family_codes.append(code)
    if not family_codes:
        return None

    if route_family == "household_appliance":
        part2 = [code for code in family_codes if code.startswith("EN 60335-2-")]
        if part2:
            return sorted(part2)[0]
    if route_family == "machinery_power_tool":
        part2 = [code for code in family_codes if code.startswith("EN 62841-2-")]
        if part2:
            return sorted(part2)[0]
    if route_family == "lighting_device":
        for preferred in ("EN IEC 62560", "EN 60598-1"):
            if preferred in family_codes:
                return preferred
    if route_family == "ev_charging":
        for preferred in ("EN IEC 61851-1", "IEC 62752"):
            if preferred in family_codes:
                return preferred
    if route_family == "ev_connector_accessory" and "EN 62196-2" in family_codes:
        return "EN 62196-2"
    if route_family == "building_hardware":
        for preferred in ("EN 14846", "EN 12209", "EN 60335-2-95", "EN 60335-2-97", "EN 60335-2-103"):
            if preferred in family_codes:
                return preferred
    if route_family == "life_safety_alarm":
        for preferred in ("EN 14604", "EN 50291-1"):
            if preferred in family_codes:
                return preferred
    if route_family == "hvac_control":
        for preferred in ("EN 60730-2-9", "EN 60730-1"):
            if preferred in family_codes:
                return preferred
    if route_family == "micromobility_device":
        for preferred in ("EN 15194", "EN 17128"):
            if preferred in family_codes:
                return preferred
    if route_family in {"av_ict", "av_ict_wearable"} and "EN 62368-1" in family_codes:
        return "EN 62368-1"
    if route_family == "toy" and "EN 62115" in family_codes:
        return "EN 62115"
    return sorted(family_codes)[0]


def route_anchor_definition(anchor: str | None) -> RouteAnchorDefinition | None:
    if not anchor:
        return None
    return route_anchor_rules().get(anchor)


def _collect_row_traits(row: dict[str, Any]) -> set[str]:
    traits: set[str] = set()
    for field in ("implied_traits", "core_traits", "default_traits", "family_traits", "subtype_traits", "boundary_tags"):
        traits.update(_string_list(row.get(field)))
    return traits


def _has_connected_signals(row: dict[str, Any], traits: set[str]) -> bool:
    if CONNECTED_ROUTE_TRAITS & traits:
        return True
    genres = set(_string_list(row.get("genres")))
    if genres & {"smart_home_iot", "security_access_iot", "pet_tech"}:
        return True
    codes = normalized_standard_codes(_string_list(row.get("likely_standards")))
    return any(code.startswith(("EN 18031-", "EN 303 645")) for code in codes)


def _has_wearable_signals(row: dict[str, Any], traits: set[str]) -> bool:
    if WEARABLE_ROUTE_TRAITS & traits:
        return True
    genres = set(_string_list(row.get("genres")))
    return bool(genres & {"wearable_device", "xr_immersive"})


def _candidate_anchors(
    row: dict[str, Any],
    *,
    family: str | None,
    boundary_decision: BoundaryDecision,
) -> list[str]:
    snapshot = get_taxonomy_snapshot()
    candidates: set[str] = set()
    explicit = str(row.get("route_anchor") or "").strip()
    if explicit:
        candidates.add(explicit)

    family_definition = snapshot.family_definition(family)
    if family_definition is not None:
        candidates.update(family_definition.allowed_route_anchors)

    if boundary_decision.preferred_route_anchor:
        candidates.add(boundary_decision.preferred_route_anchor)

    codes = normalized_standard_codes(
        _string_list(row.get("likely_standards"))
        + _string_list(row.get("supporting_standard_codes"))
        + ([str(row.get("primary_standard_code")).strip()] if str(row.get("primary_standard_code") or "").strip() else [])
    )
    prefer_wearable = _has_wearable_signals(row, _collect_row_traits(row))
    for code in codes:
        matched_family = family_from_standard_code(code, prefer_wearable=prefer_wearable)
        if not matched_family:
            continue
        for definition in route_anchor_rules().values():
            if definition.route_family == matched_family:
                candidates.add(definition.key)

    if not candidates:
        candidates.update(route_anchor_rules())
    return sorted(candidates)


def _evaluate_candidate(
    row: dict[str, Any],
    anchor: str,
    *,
    boundary_decision: BoundaryDecision,
    connected: bool,
    wearable: bool,
) -> RouteAnchorCandidate | None:
    definition = route_anchor_definition(anchor)
    if definition is None:
        return None

    family = str(row.get("product_family") or "").strip()
    subfamily = str(row.get("product_subfamily") or "").strip()
    route_family = str(row.get("route_family") or "").strip()
    genres = set(_string_list(row.get("genres")))
    traits = _collect_row_traits(row)
    boundary_tags = set(_string_list(row.get("boundary_tags"))) | set(boundary_decision.boundary_tags)
    codes = normalized_standard_codes(
        _string_list(row.get("likely_standards"))
        + _string_list(row.get("supporting_standard_codes"))
        + ([str(row.get("primary_standard_code")).strip()] if str(row.get("primary_standard_code") or "").strip() else [])
    )
    snapshot = get_taxonomy_snapshot()
    family_definition = snapshot.family_definition(family)

    score = 0
    reasons: list[RouteAnchorReason] = []

    if family_definition and anchor in family_definition.allowed_route_anchors:
        weight = 28 if len(family_definition.allowed_route_anchors) == 1 else 16
        score += weight
        reasons.append(RouteAnchorReason("family_allow", f"taxonomy family allows {anchor}", weight))

    if route_family and route_family == definition.route_family:
        score += 18
        reasons.append(RouteAnchorReason("route_family", f"route_family={route_family}", 18))

    if boundary_decision.preferred_route_anchor and anchor == boundary_decision.preferred_route_anchor:
        score += 36
        reasons.append(RouteAnchorReason("boundary", f"boundary prefers {anchor}", 36))

    if family and family in definition.signal_families:
        score += 22
        reasons.append(RouteAnchorReason("family", f"family={family}", 22))

    if subfamily and subfamily in definition.signal_subfamilies:
        score += 26
        reasons.append(RouteAnchorReason("subfamily", f"subfamily={subfamily}", 26))

    genre_hits = sorted(genres & set(definition.signal_genres))
    for genre in genre_hits[:3]:
        score += 10
        reasons.append(RouteAnchorReason("genre", f"genre={genre}", 10))

    trait_hits = sorted(traits & set(definition.signal_traits))
    for trait in trait_hits[:3]:
        score += 8
        reasons.append(RouteAnchorReason("trait", f"trait={trait}", 8))

    tag_hits = sorted(boundary_tags & set(definition.signal_boundary_tags))
    for tag in tag_hits[:3]:
        score += 12
        reasons.append(RouteAnchorReason("boundary_tag", f"boundary_tag={tag}", 12))

    for code in codes:
        if code in {candidate.upper() for candidate in definition.exact_primary_candidates}:
            score += 24
            reasons.append(RouteAnchorReason("standard", f"standard={code}", 24))
            break
        if any(code.startswith(prefix.upper()) for prefix in definition.prefix_primary_candidates):
            score += 18
            reasons.append(RouteAnchorReason("standard", f"standard_prefix={code}", 18))
            break
        matched_family = family_from_standard_code(code, prefer_wearable=wearable)
        if matched_family == definition.route_family:
            score += 12
            reasons.append(RouteAnchorReason("standard_family", f"standard_family={matched_family}", 12))
            break

    if definition.connected_mode == "require":
        if connected:
            score += 14
            reasons.append(RouteAnchorReason("connected", "connected_signals=require", 14))
        else:
            score -= 16
    elif definition.connected_mode == "prefer":
        if connected:
            score += 10
            reasons.append(RouteAnchorReason("connected", "connected_signals=prefer", 10))
    elif definition.connected_mode == "avoid" and connected:
        score -= 10

    if definition.wearable_mode == "require":
        if wearable:
            score += 16
            reasons.append(RouteAnchorReason("wearable", "wearable_signals=require", 16))
        else:
            score -= 18
    elif definition.wearable_mode == "prefer":
        if wearable:
            score += 10
            reasons.append(RouteAnchorReason("wearable", "wearable_signals=prefer", 10))
    elif definition.wearable_mode == "avoid" and wearable:
        score -= 12

    if score <= 0:
        return None
    ordered_reasons = tuple(sorted(reasons, key=lambda item: (-item.weight, item.detail)))
    return RouteAnchorCandidate(anchor=anchor, route_family=definition.route_family, score=score, reasons=ordered_reasons)


def _decision_confidence(top: RouteAnchorCandidate, next_candidate: RouteAnchorCandidate | None) -> str:
    gap = top.score - next_candidate.score if next_candidate else top.score
    direct_signals = len(top.reasons)
    if top.score >= 58 and gap >= 14 and direct_signals >= 3:
        return "high"
    if top.score >= 36 and gap >= 8 and direct_signals >= 2:
        return "medium"
    if top.score >= 28 and direct_signals >= 2:
        return "medium"
    return "low"


def resolve_route_anchor(row: dict[str, Any]) -> RouteAnchorDecision:
    boundary_decision = decide_boundary(row)
    explicit = str(row.get("route_anchor") or "").strip()
    explicit_definition = route_anchor_definition(explicit)

    traits = _collect_row_traits(row)
    connected = _has_connected_signals(row, traits)
    wearable = _has_wearable_signals(row, traits)
    family = str(row.get("product_family") or "").strip() or None

    candidates = [
        candidate
        for anchor in _candidate_anchors(row, family=family, boundary_decision=boundary_decision)
        if (candidate := _evaluate_candidate(row, anchor, boundary_decision=boundary_decision, connected=connected, wearable=wearable))
        is not None
    ]
    candidates.sort(key=lambda item: (-item.score, item.anchor))

    if explicit_definition is not None:
        explicit_candidate = next((candidate for candidate in candidates if candidate.anchor == explicit), None)
        explicit_reasons = tuple(reason.detail for reason in (explicit_candidate.reasons[:4] if explicit_candidate else ()))
        return RouteAnchorDecision(
            anchor=explicit,
            route_family=explicit_definition.route_family,
            confidence=_decision_confidence(explicit_candidate, candidates[1] if len(candidates) > 1 and explicit_candidate == candidates[0] else None)
            if explicit_candidate
            else "medium",
            score=explicit_candidate.score if explicit_candidate else 0,
            source="declared",
            reasons=explicit_reasons or ("declared route anchor",),
            alternatives=tuple(candidate.anchor for candidate in candidates[:3] if candidate.anchor != explicit),
            boundary_decision=boundary_decision,
        )

    if not candidates:
        return RouteAnchorDecision(
            anchor=None,
            route_family=str(row.get("route_family") or "").strip() or None,
            confidence="low",
            score=0,
            source="missing",
            reasons=(),
            alternatives=(),
            boundary_decision=boundary_decision,
        )

    top = candidates[0]
    next_candidate = candidates[1] if len(candidates) > 1 else None
    return RouteAnchorDecision(
        anchor=top.anchor,
        route_family=top.route_family,
        confidence=_decision_confidence(top, next_candidate),
        score=top.score,
        source="scored",
        reasons=tuple(reason.detail for reason in top.reasons[:4]),
        alternatives=tuple(candidate.anchor for candidate in candidates[1:4]),
        boundary_decision=boundary_decision,
    )


def infer_route_anchor(row: dict[str, Any]) -> str | None:
    return resolve_route_anchor(row).anchor


def _preferred_primary_from_anchor(definition: RouteAnchorDefinition, codes: list[str]) -> str | None:
    exact_candidates = {candidate.upper() for candidate in definition.exact_primary_candidates}
    for code in codes:
        if code in exact_candidates:
            return code
    for prefix in definition.prefix_primary_candidates:
        normalized_prefix = prefix.upper()
        candidates = [code for code in codes if code.startswith(normalized_prefix)]
        if candidates:
            return sorted(candidates)[0]
    return None


def _should_suppress_auto_primary(
    definition: RouteAnchorDefinition,
    decision: RouteAnchorDecision,
) -> bool:
    boundary = decision.boundary_decision
    if definition.route_family.endswith("_boundary"):
        return True
    if boundary.boundary_class in {
        "medical_wellness",
        "uv_irradiation",
        "body_treatment",
        "power_system",
        "industrial_installation",
        "specialty_agricultural",
        "machinery_system",
    } and decision.confidence == "low":
        return True
    return False


def apply_route_anchor_defaults(row: dict[str, Any]) -> dict[str, Any]:
    enriched = dict(row)
    decision = resolve_route_anchor(enriched)
    boundary = decision.boundary_decision

    if decision.anchor is None:
        enriched["boundary_class"] = boundary.boundary_class
        enriched["boundary_missing_differentiators"] = list(boundary.key_missing_differentiators)
        enriched["route_anchor_source"] = decision.source
        enriched["route_anchor_confidence"] = decision.confidence
        enriched["route_anchor_reasons"] = list(decision.reasons)
        enriched["route_anchor_alternatives"] = list(decision.alternatives)
        return enriched

    definition = route_anchor_definition(decision.anchor)
    if definition is None:
        return enriched

    enriched["route_anchor"] = decision.anchor
    enriched["route_family"] = definition.route_family
    enriched["route_anchor_source"] = decision.source
    enriched["route_anchor_confidence"] = decision.confidence
    enriched["route_anchor_score"] = decision.score
    enriched["route_anchor_reasons"] = list(decision.reasons)
    enriched["route_anchor_alternatives"] = list(decision.alternatives)
    enriched["boundary_class"] = boundary.boundary_class
    enriched["boundary_missing_differentiators"] = list(boundary.key_missing_differentiators)
    enriched["boundary_reason"] = boundary.concise_reason

    codes = normalized_standard_codes(
        _string_list(enriched.get("likely_standards"))
        + _string_list(enriched.get("supporting_standard_codes"))
        + ([str(enriched.get("primary_standard_code")).strip()] if str(enriched.get("primary_standard_code") or "").strip() else [])
    )
    if _should_suppress_auto_primary(definition, decision):
        enriched["primary_standard_code"] = None
    elif not str(enriched.get("primary_standard_code") or "").strip():
        primary = _preferred_primary_from_anchor(definition, codes) or best_primary_standard_for_family(definition.route_family, codes)
        if primary:
            enriched["primary_standard_code"] = primary

    existing_tags = _string_list(enriched.get("boundary_tags"))
    merged_tags: list[str] = []
    seen_tags: set[str] = set()
    for tag in existing_tags + list(definition.boundary_tags) + list(boundary.boundary_tags):
        if tag in seen_tags:
            continue
        seen_tags.add(tag)
        merged_tags.append(tag)
    enriched["boundary_tags"] = merged_tags

    final_max_match_stage = str(enriched.get("max_match_stage") or "").strip() or None
    if definition.max_match_stage == "family" or boundary.max_match_stage == "family":
        final_max_match_stage = "family"
    elif final_max_match_stage is None:
        final_max_match_stage = definition.max_match_stage or boundary.max_match_stage
    if final_max_match_stage is not None:
        enriched["max_match_stage"] = final_max_match_stage

    final_confidence_cap = str(enriched.get("route_confidence_cap") or "").strip() or None
    for requested_cap in (definition.route_confidence_cap, boundary.confidence_cap):
        if requested_cap not in _CONFIDENCE_RANK:
            continue
        if final_confidence_cap not in _CONFIDENCE_RANK:
            final_confidence_cap = requested_cap
            continue
        if _CONFIDENCE_RANK[requested_cap] < _CONFIDENCE_RANK[final_confidence_cap]:
            final_confidence_cap = requested_cap
    if final_confidence_cap is not None:
        enriched["route_confidence_cap"] = final_confidence_cap

    if not str(enriched.get("family_level_reason") or "").strip():
        if boundary.concise_reason and final_max_match_stage == "family":
            enriched["family_level_reason"] = boundary.concise_reason
        elif definition.family_level_reason and final_max_match_stage == "family":
            enriched["family_level_reason"] = definition.family_level_reason

    return enriched


__all__ = [
    "CONNECTED_ROUTE_TRAITS",
    "RouteAnchorCandidate",
    "RouteAnchorDecision",
    "RouteAnchorDefinition",
    "RouteAnchorReason",
    "WEARABLE_ROUTE_TRAITS",
    "apply_route_anchor_defaults",
    "best_primary_standard_for_family",
    "family_from_standard_code",
    "infer_route_anchor",
    "normalized_standard_codes",
    "resolve_route_anchor",
    "route_anchor_definition",
    "route_anchor_rules",
    "route_family_primary_directive_map",
    "route_family_scope_map",
    "route_standard_family_rules",
]
