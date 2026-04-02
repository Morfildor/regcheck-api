from __future__ import annotations

from collections.abc import Sequence
from dataclasses import replace

from .matching_legacy import _hierarchical_product_match, _select_matched_products
from .matching_runtime import (
    CompiledAlias,
    CompiledPhrase,
    CompiledProductMatcher,
    ProductMatchingSnapshot,
    _compiled_phrase_hits,
    _product_matching_snapshot,
    _shortlist_product_matchers_v2,
    build_product_matching_snapshot,
    reset_matching_cache,
)
from .models import ClassifierMatchAudit, ClassifierMatchOutcome, FamilySeedCandidate, SubtypeCandidate
from .scoring import (
    ENGINE_VERSION,
    _context_bonus,
    _matching_clues,
    _string_list,
    _trait_overlap_score,
)


def _compiled_alias_score(text: str, alias: CompiledAlias) -> int:
    if alias.exact_pattern.search(text):
        score = 100 + len(alias.normalized) * 3 + len(alias.normalized.split()) * 22
        if alias.normalized == text:
            score += 80
        return score

    if alias.gap_pattern is not None and alias.gap_pattern.search(text):
        return 42 + len(alias.normalized.split()) * 12

    return 0


def _best_alias_match_v2(text: str, compiled: CompiledProductMatcher) -> tuple[str | None, int, list[str]]:
    best_alias = None
    best_score = 0
    best_reasons: list[str] = []

    for alias in compiled.aliases:
        score = _compiled_alias_score(text, alias)
        if score <= 0:
            continue

        reasons = [f"matched {alias.field.replace('_', ' ')[:-1]} '{alias.raw}'"]
        if alias.specificity_bonus:
            score += alias.specificity_bonus
            reasons.append(f"alias specificity {alias.specificity_bonus:+d}")
        if alias.field_bonus:
            score += alias.field_bonus
            reasons.append(f"{alias.field} bonus {alias.field_bonus:+d}")

        if best_alias is None or score > best_score:
            best_alias = alias.raw
            best_score = score
            best_reasons = reasons

    return best_alias, best_score, best_reasons


def _compiled_clue_score(
    text: str,
    compiled: CompiledProductMatcher,
) -> tuple[int, list[str], list[str], list[str], bool]:
    required_hits = _compiled_phrase_hits(text, compiled.required_clues)
    preferred_hits = _compiled_phrase_hits(text, compiled.preferred_clues)
    exclude_hits = _compiled_phrase_hits(text, compiled.exclude_clues)

    score = len(required_hits) * 26 + len(preferred_hits) * 14 - len(exclude_hits) * 34
    reasons = [f"required clue '{clue}'" for clue in required_hits]
    reasons.extend(f"preferred clue '{clue}'" for clue in preferred_hits)
    reasons.extend(f"exclude clue '{clue}'" for clue in exclude_hits)

    if compiled.required_clues and not required_hits:
        score -= 18
        reasons.append("missing required subtype clues")

    decisive = bool(required_hits or len(preferred_hits) >= 2)
    positive_clues = required_hits + preferred_hits
    negative_clues = exclude_hits
    return score, reasons, positive_clues, negative_clues, decisive


def _candidate_confidence_v2(
    candidate: SubtypeCandidate | FamilySeedCandidate,
    next_candidate: SubtypeCandidate | FamilySeedCandidate | None = None,
) -> str:
    score = candidate.score
    gap = score - next_candidate.score if next_candidate else score
    direct_signals = candidate.direct_signal_count
    if score >= 150 and gap >= 16 and direct_signals >= 2:
        return "high"
    if score >= 110 and gap >= 8 and direct_signals >= 1:
        return "medium"
    if score >= 85 and direct_signals >= 2:
        return "medium"
    return "low"


def _common_strings(rows: Sequence[SubtypeCandidate], field: str) -> list[str]:
    if not rows:
        return []
    common = set(getattr(rows[0], field))
    for row in rows[1:]:
        common &= set(getattr(row, field))
    return sorted(common)


def _common_sets(rows: Sequence[SubtypeCandidate], field: str) -> set[str]:
    if not rows:
        return set()
    common = set(getattr(rows[0], field))
    for row in rows[1:]:
        common &= set(getattr(row, field))
    return common


def _top_unique(items: list[str], *, limit: int = 5) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for item in items:
        if not item or item in seen:
            continue
        seen.add(item)
        ordered.append(item)
        if len(ordered) >= limit:
            break
    return ordered


def _normalized_text_summary(text: str, *, limit: int = 160) -> str:
    if len(text) <= limit:
        return text
    return text[: limit - 3].rstrip() + "..."


def _build_empty_match_outcome(text: str) -> ClassifierMatchOutcome:
    return ClassifierMatchOutcome(
        product_family=None,
        product_family_confidence="low",
        product_subtype=None,
        product_subtype_confidence="low",
        product_match_stage="ambiguous",
        product_type=None,
        product_match_confidence="low",
        diagnostics=[
            "product_shortlist_candidates=0",
            f"product_shortlist_catalog={len(_product_matching_snapshot().products)}",
            "product_winner=none",
        ],
        audit=ClassifierMatchAudit(
            engine_version=ENGINE_VERSION,
            normalized_text=text,
            normalized_text_summary=_normalized_text_summary(text),
        ),
    )


def _build_product_candidate_v2(
    text: str,
    signal_traits: set[str],
    compiled: CompiledProductMatcher,
) -> SubtypeCandidate | None:
    product = compiled.product
    blocked_phrases = _matching_clues(text, _string_list(product.get("not_when_text_contains")))

    forbidden_traits = set(_string_list(product.get("forbidden_traits")))
    if forbidden_traits & signal_traits:
        return None

    best_alias, alias_score, alias_reasons = _best_alias_match_v2(text, compiled)
    family_keyword_hits = _compiled_phrase_hits(text, compiled.family_keywords)
    clue_score, clue_reasons, positive_clues, negative_clues, decisive = _compiled_clue_score(text, compiled)
    core_traits = set(compiled.core_traits)
    default_traits = set(compiled.default_traits)
    family_traits = set(compiled.family_traits) or core_traits
    family_overlap = _trait_overlap_score(signal_traits, family_traits, weight=4)
    core_overlap = _trait_overlap_score(signal_traits, core_traits, weight=6)
    default_overlap = _trait_overlap_score(signal_traits, default_traits, weight=3)
    bonus, bonus_reasons = _context_bonus(text, product, signal_traits)

    score = alias_score + clue_score + family_overlap + core_overlap + default_overlap + bonus
    score += len(family_keyword_hits) * 24

    direct_signal_count = int(bool(best_alias)) + len(positive_clues) + len(family_keyword_hits)
    score_boost_traits = set(_string_list(product.get("score_boost_if_traits")))
    score_penalty_traits = set(_string_list(product.get("score_penalty_if_traits")))
    boost_hits = sorted(score_boost_traits & signal_traits)
    penalty_hits = sorted(score_penalty_traits & signal_traits)
    required_any_traits = set(_string_list(product.get("required_any_traits")))
    required_any_missing = bool(required_any_traits and not (required_any_traits & signal_traits))
    score += len(boost_hits) * 8
    score -= len(penalty_hits) * 18
    score -= len(blocked_phrases) * 60
    if required_any_missing:
        score -= 18

    minimum_match_score = int(product.get("minimum_match_score", 0) or 0)
    if direct_signal_count == 0:
        return None
    if required_any_missing and best_alias is None:
        return None
    if score < minimum_match_score:
        return None

    reasons = list(alias_reasons)
    reasons.extend(f"family keyword '{hit}'" for hit in family_keyword_hits)
    reasons.extend(clue_reasons)
    if family_overlap:
        reasons.append(f"family trait overlap +{family_overlap}")
    if core_overlap:
        reasons.append(f"product core overlap +{core_overlap}")
    if default_overlap:
        reasons.append(f"product default overlap +{default_overlap}")
    reasons.extend(f"blocked phrase '{phrase}'" for phrase in blocked_phrases)
    reasons.extend(f"metadata boost '{trait}'" for trait in boost_hits)
    reasons.extend(f"metadata penalty '{trait}'" for trait in penalty_hits)
    if required_any_missing:
        reasons.append("missing required routing traits")
    reasons.extend(bonus_reasons)

    return SubtypeCandidate(
        id=product["id"],
        label=product.get("label", product["id"]),
        family=compiled.family,
        subtype=compiled.subtype,
        genres=tuple(_string_list(product.get("genres"))),
        product=product,
        matched_alias=best_alias,
        alias_hits=(best_alias,) if best_alias else (),
        family_keyword_hits=tuple(family_keyword_hits),
        positive_clues=tuple(positive_clues),
        negative_clues=tuple(negative_clues),
        decisive=decisive or (best_alias is not None and alias_score >= 115) or bool(family_keyword_hits),
        score=score,
        direct_signal_count=direct_signal_count,
        reasons=tuple(reasons),
        core_traits=tuple(sorted(core_traits)),
        default_traits=tuple(sorted(default_traits)),
        family_traits=tuple(sorted(family_traits)),
        subtype_traits=tuple(_string_list(product.get("subtype_traits")) or _string_list(product.get("implied_traits"))),
        functional_classes=tuple(_string_list(product.get("functional_classes"))),
        likely_standards=tuple(_string_list(product.get("likely_standards"))),
        confusable_with=tuple(_string_list(product.get("confusable_with"))),
    )


def _resolve_stage(
    *,
    top_family: FamilySeedCandidate,
    next_family: FamilySeedCandidate | None,
    top_subtype: SubtypeCandidate,
    next_subtype: SubtypeCandidate | None,
    family_confidence: str,
    subtype_confidence: str,
) -> tuple[str, str, list[str], str | None]:
    contradictions: list[str] = []
    ambiguity_reason: str | None = None

    family_gap = top_family.score - next_family.score if next_family else top_family.score
    subtype_gap = top_subtype.score - next_subtype.score if next_subtype else top_subtype.score
    close_family_competition = bool(next_family and family_gap < 8 and next_family.family != top_family.family)
    close_subtype_competition = bool(next_subtype and subtype_gap < 10)

    if close_family_competition and next_family is not None:
        ambiguity_reason = (
            f"Product identification remains ambiguous between {top_family.id.replace('_', ' ')} "
            f"and {next_family.id.replace('_', ' ')}."
        )
        contradictions.append(ambiguity_reason)
        return "ambiguous", "cross-family candidates remain too close to resolve safely", contradictions, ambiguity_reason

    if next_subtype and top_subtype.negative_clues and next_subtype.positive_clues:
        ambiguity_reason = f"Confusable subtype clues remain unresolved within family {top_family.family.replace('_', ' ')}."
        return "family", "top subtype has exclusion clues while a close runner-up has positive subtype clues", contradictions, ambiguity_reason

    if close_subtype_competition:
        ambiguity_reason = f"Subtype evidence is too close within family {top_family.family.replace('_', ' ')}."
        return "family", "family match is stable but subtype candidates remain too close to confirm", contradictions, ambiguity_reason

    if subtype_confidence == "high" or (subtype_confidence == "medium" and top_subtype.decisive):
        return "subtype", "decisive alias or clue support confirmed the subtype", contradictions, ambiguity_reason

    if family_confidence in {"high", "medium"}:
        return "family", "family evidence is strong enough, but subtype evidence is not decisive", contradictions, ambiguity_reason

    ambiguity_reason = f"Product evidence for {top_family.label} is too weak to confirm a subtype."
    return "ambiguous", "family evidence remained below the subtype confirmation threshold", contradictions, ambiguity_reason


def _hierarchical_product_match_v2(text: str, signal_traits: set[str]) -> ClassifierMatchOutcome:
    shortlisted_matchers, shortlist_scoring = _shortlist_product_matchers_v2(text, signal_traits)
    candidates = [
        candidate
        for matcher in shortlisted_matchers
        if (candidate := _build_product_candidate_v2(text, signal_traits, matcher)) is not None
    ]
    candidates.sort(key=lambda row: (-row.score, row.id))

    if not candidates:
        return _build_empty_match_outcome(text)

    family_map: dict[str, FamilySeedCandidate] = {}
    for candidate in candidates:
        existing = family_map.get(candidate.family)
        if existing is None or candidate.score > existing.score:
            family_map[candidate.family] = FamilySeedCandidate(
                family=candidate.family,
                representative=candidate,
                score=candidate.score,
            )

    ordered_family_candidates = sorted(family_map.values(), key=lambda row: (-row.score, row.family))
    family_candidates = [
        replace(
            row,
            confidence=_candidate_confidence_v2(
                row,
                ordered_family_candidates[idx + 1] if idx + 1 < len(ordered_family_candidates) else None,
            ),
        )
        for idx, row in enumerate(ordered_family_candidates)
    ]
    top_family = family_candidates[0]
    next_family = family_candidates[1] if len(family_candidates) > 1 else None

    family_rows = [row for row in candidates if row.family == top_family.family]
    top_subtype = family_rows[0]
    next_subtype = family_rows[1] if len(family_rows) > 1 else None
    family_confidence = top_family.confidence
    subtype_confidence = _candidate_confidence_v2(top_subtype, next_subtype)
    family_stage, stage_reason, contradictions, ambiguity_reason = _resolve_stage(
        top_family=top_family,
        next_family=next_family,
        top_subtype=top_subtype,
        next_subtype=next_subtype,
        family_confidence=family_confidence,
        subtype_confidence=subtype_confidence,
    )

    subtype_band = [row for row in family_rows if top_subtype.score - row.score <= 10][:3]
    if family_stage == "family" and next_subtype and next_subtype.id not in {row.id for row in subtype_band}:
        subtype_band = [top_subtype, next_subtype]

    common_classes = _common_strings(subtype_band, "functional_classes")
    common_standards = _common_strings(subtype_band, "likely_standards")
    common_core_traits = _common_sets(subtype_band, "core_traits")
    common_default_traits = _common_sets(subtype_band, "default_traits")
    common_genres = _common_sets(subtype_band, "genres")

    product_core_traits = set(top_subtype.core_traits)
    product_default_traits = set(top_subtype.default_traits)
    product_genres = set(top_subtype.genres)
    functional_classes = set(top_subtype.functional_classes)
    confirmed_functional_classes: set[str] = set()
    preferred_standard_codes: list[str] = []
    confirmed_products: list[str] = []
    matched_products = [row.id for row in subtype_band]
    routing_matched_products: list[str] = []
    product_subtype = top_subtype.id if family_stage == "subtype" else None
    product_type = top_subtype.id
    product_match_confidence = subtype_confidence

    if family_stage == "ambiguous" and next_family is not None:
        matched_products = [top_family.id, next_family.id]
        functional_classes = set()
        product_core_traits = set()
        product_default_traits = set()
        product_genres = set()
        product_match_confidence = "low"
    elif family_stage == "family":
        functional_classes = set(common_classes)
        product_core_traits = set(common_core_traits)
        product_default_traits = set(common_default_traits)
        product_genres = set(common_genres)
        preferred_standard_codes = common_standards
        product_match_confidence = "medium" if family_confidence == "high" else family_confidence
        if family_confidence == "high":
            confirmed_functional_classes.update(common_classes)
    else:
        routing_matched_products = [top_subtype.id]
        preferred_standard_codes = list(top_subtype.likely_standards)
        if subtype_confidence == "high":
            confirmed_products = [top_subtype.id]
            confirmed_functional_classes.update(top_subtype.functional_classes)
        elif common_classes:
            confirmed_functional_classes.update(common_classes)

    public_rows = family_rows[:5]
    close_family_competition = bool(next_family and top_family.score - next_family.score < 8 and next_family.family != top_family.family)
    if close_family_competition and next_family is not None and next_family.representative not in public_rows:
        public_rows = public_rows + [next_family.representative]

    product_candidates = [
        candidate.to_public_candidate(
            confidence=_candidate_confidence_v2(
                candidate,
                public_rows[idx + 1] if idx + 1 < len(public_rows) else None,
            ),
            family_score=family_map[candidate.family].score if candidate.family in family_map else candidate.score,
        )
        for idx, candidate in enumerate(public_rows[:5])
    ]

    audit_rows = subtype_band if family_stage == "family" else [top_subtype]
    alias_hits = _top_unique([hit for row in audit_rows for hit in row.alias_hits], limit=5)
    family_keyword_hits = _top_unique([hit for row in audit_rows for hit in row.family_keyword_hits], limit=5)
    clue_hits = _top_unique([hit for row in audit_rows for hit in row.positive_clues], limit=5)
    strongest_negative_clues = _top_unique([hit for row in audit_rows for hit in row.negative_clues], limit=5)
    top_family_audit = [row.to_audit_candidate() for row in family_candidates[:3]]
    top_subtype_audit = [
        row.to_audit_candidate(
            confidence=_candidate_confidence_v2(
                row,
                candidates[idx + 1] if idx + 1 < len(candidates) else None,
            )
        )
        for idx, row in enumerate(candidates[:5])
    ]

    diagnostics = [
        f"product_shortlist_candidates={len(shortlisted_matchers)}",
        f"product_shortlist_catalog={len(_product_matching_snapshot().products)}",
        f"product_family={top_family.family}",
        f"product_family_confidence={family_confidence}",
        f"product_subtype_candidate={top_subtype.id}",
        f"product_subtype_confidence={subtype_confidence}",
        f"product_match_stage={family_stage}",
    ]
    top_shortlist = sorted(shortlist_scoring.items(), key=lambda item: (-item[1], item[0]))[:5]
    if top_shortlist:
        diagnostics.append(
            "product_shortlist_top="
            + ",".join(f"{product_id}:{score}" for product_id, score in top_shortlist)
        )

    top_row_reasons = list(top_subtype.reasons[:8])
    audit = ClassifierMatchAudit(
        engine_version=ENGINE_VERSION,
        normalized_text=text,
        normalized_text_summary=_normalized_text_summary(text),
        retrieval_basis=top_row_reasons,
        alias_hits=alias_hits,
        matched_aliases=alias_hits,
        family_keyword_hits=family_keyword_hits,
        clue_hits=clue_hits,
        strongest_positive_clues=clue_hits,
        strongest_negative_clues=strongest_negative_clues,
        top_family_candidates=top_family_audit,
        top_subtype_candidates=top_subtype_audit,
        final_match_stage=family_stage,
        final_match_reason=stage_reason,
        ambiguity_reason=ambiguity_reason,
    )

    return ClassifierMatchOutcome(
        product_family=top_family.family,
        product_family_confidence=family_confidence,
        product_subtype=product_subtype,
        product_subtype_confidence=subtype_confidence,
        product_match_stage=family_stage,
        product_type=product_type,
        product_match_confidence=product_match_confidence,
        product_candidates=product_candidates,
        matched_products=matched_products,
        routing_matched_products=routing_matched_products,
        confirmed_products=confirmed_products,
        product_core_traits=product_core_traits,
        product_default_traits=product_default_traits,
        product_genres=product_genres,
        preferred_standard_codes=preferred_standard_codes,
        functional_classes=functional_classes,
        confirmed_functional_classes=confirmed_functional_classes,
        diagnostics=diagnostics,
        contradictions=contradictions,
        audit=audit,
        family_seed_candidates=family_candidates,
        subtype_candidates=candidates,
    )


__all__ = [
    "CompiledAlias",
    "CompiledPhrase",
    "CompiledProductMatcher",
    "ProductMatchingSnapshot",
    "_hierarchical_product_match",
    "_hierarchical_product_match_v2",
    "_select_matched_products",
    "_shortlist_product_matchers_v2",
    "build_product_matching_snapshot",
    "reset_matching_cache",
]
