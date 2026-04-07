from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.services.knowledge_base.taxonomy import BoundaryRuleDefinition, get_taxonomy_snapshot
from app.services.standard_codes import normalized_standard_codes


_CONFIDENCE_RANK = {"low": 0, "medium": 1, "high": 2}


@dataclass(frozen=True, slots=True)
class BoundaryReason:
    kind: str
    detail: str
    weight: int


@dataclass(frozen=True, slots=True)
class BoundaryCandidate:
    rule: BoundaryRuleDefinition
    score: int
    reasons: tuple[BoundaryReason, ...]


@dataclass(frozen=True, slots=True)
class BoundaryDecision:
    boundary_class: str | None
    preferred_route_anchor: str | None
    boundary_tags: tuple[str, ...]
    max_match_stage: str | None
    confidence_cap: str | None
    concise_reason: str | None
    reasons: tuple[str, ...]
    key_missing_differentiators: tuple[str, ...]
    matched_rule_ids: tuple[str, ...]
    score: int = 0
    source: str = "none"


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if isinstance(item, str) and str(item).strip()]


def _normalized_standard_codes(row: dict[str, Any]) -> list[str]:
    codes = (
        _string_list(row.get("likely_standards"))
        + _string_list(row.get("supporting_standard_codes"))
        + ([str(row.get("primary_standard_code")).strip()] if str(row.get("primary_standard_code") or "").strip() else [])
    )
    return normalized_standard_codes(codes)


def _cap_confidence(current: str | None, requested: str | None) -> str | None:
    if requested not in _CONFIDENCE_RANK:
        return current
    if current not in _CONFIDENCE_RANK:
        return requested
    return current if _CONFIDENCE_RANK[current] <= _CONFIDENCE_RANK[requested] else requested


def _evaluate_boundary_rule(rule: BoundaryRuleDefinition, row: dict[str, Any]) -> BoundaryCandidate | None:
    family = str(row.get("product_family") or "").strip()
    subfamily = str(row.get("product_subfamily") or "").strip()
    product_id = str(row.get("id") or "").strip()
    genres = set(_string_list(row.get("genres")))
    traits = {
        trait
        for field in ("implied_traits", "core_traits", "default_traits", "family_traits", "subtype_traits", "boundary_tags")
        for trait in _string_list(row.get(field))
    }
    boundary_tags = set(_string_list(row.get("boundary_tags")))
    codes = _normalized_standard_codes(row)

    score = 0
    reasons: list[BoundaryReason] = []

    if family and family in rule.families_any:
        score += 30
        reasons.append(BoundaryReason("family", f"family={family}", 30))
    if subfamily and subfamily in rule.subfamilies_any:
        score += 34
        reasons.append(BoundaryReason("subfamily", f"subfamily={subfamily}", 34))

    genre_hits = sorted(genres & set(rule.genres_any))
    for genre in genre_hits[:3]:
        score += 12
        reasons.append(BoundaryReason("genre", f"genre={genre}", 12))

    trait_hits = sorted(traits & set(rule.traits_any))
    for trait in trait_hits[:3]:
        score += 14
        reasons.append(BoundaryReason("trait", f"trait={trait}", 14))

    tag_hits = sorted(boundary_tags & set(rule.boundary_tags_any))
    for tag in tag_hits[:3]:
        score += 16
        reasons.append(BoundaryReason("boundary_tag", f"boundary_tag={tag}", 16))

    prefix_hits = [prefix for prefix in rule.standard_prefixes_any if any(code.startswith(prefix.upper()) for code in codes)]
    for prefix in prefix_hits[:2]:
        score += 18
        reasons.append(BoundaryReason("standard", f"standard_prefix={prefix}", 18))

    token_hits = [token for token in rule.id_tokens_any if token and token in product_id]
    for token in token_hits[:2]:
        score += 8
        reasons.append(BoundaryReason("id_token", f"id_token={token}", 8))

    if score <= 0:
        return None
    return BoundaryCandidate(rule=rule, score=score, reasons=tuple(reasons))


def decide_boundary(row: dict[str, Any]) -> BoundaryDecision:
    snapshot = get_taxonomy_snapshot()
    candidates = [candidate for rule in snapshot.boundary_rules if (candidate := _evaluate_boundary_rule(rule, row)) is not None]
    candidates.sort(key=lambda item: (-item.score, -item.rule.priority, item.rule.id))

    existing_tags = _string_list(row.get("boundary_tags"))
    existing_max_match_stage = str(row.get("max_match_stage") or "").strip() or None
    existing_confidence_cap = str(row.get("route_confidence_cap") or "").strip() or None
    existing_reason = str(row.get("family_level_reason") or "").strip() or None

    if not candidates:
        return BoundaryDecision(
            boundary_class=None,
            preferred_route_anchor=None,
            boundary_tags=tuple(existing_tags),
            max_match_stage=existing_max_match_stage,
            confidence_cap=existing_confidence_cap,
            concise_reason=existing_reason,
            reasons=(),
            key_missing_differentiators=(),
            matched_rule_ids=(),
            score=0,
            source="declared" if (existing_tags or existing_reason or existing_confidence_cap or existing_max_match_stage) else "none",
        )

    top = candidates[0]
    merged_tags: list[str] = []
    seen_tags: set[str] = set()
    for tag in existing_tags + [tag for candidate in candidates for tag in candidate.rule.add_boundary_tags]:
        if tag in seen_tags:
            continue
        seen_tags.add(tag)
        merged_tags.append(tag)

    max_match_stage = existing_max_match_stage
    if any(candidate.rule.max_match_stage == "family" for candidate in candidates):
        max_match_stage = "family"
    elif max_match_stage is None:
        max_match_stage = top.rule.max_match_stage

    confidence_cap = existing_confidence_cap
    for candidate in candidates:
        confidence_cap = _cap_confidence(confidence_cap, candidate.rule.confidence_cap)

    concise_reason = existing_reason or top.rule.concise_reason
    structured_reasons = tuple(reason.detail for reason in top.reasons)

    return BoundaryDecision(
        boundary_class=top.rule.boundary_class,
        preferred_route_anchor=top.rule.preferred_route_anchor,
        boundary_tags=tuple(merged_tags),
        max_match_stage=max_match_stage,
        confidence_cap=confidence_cap,
        concise_reason=concise_reason,
        reasons=structured_reasons,
        key_missing_differentiators=top.rule.key_missing_differentiators,
        matched_rule_ids=tuple(candidate.rule.id for candidate in candidates),
        score=top.score,
        source="algorithmic",
    )


__all__ = [
    "BoundaryCandidate",
    "BoundaryDecision",
    "BoundaryReason",
    "decide_boundary",
]
