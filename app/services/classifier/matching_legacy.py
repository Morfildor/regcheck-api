from __future__ import annotations

"""Compatibility-only v1 matcher support.

New classifier behavior should go through the compiled v2 path in `matching.py`.
This module remains as a narrow fallback for legacy payload parity and should only
receive low-risk fixes that preserve that compatibility boundary.
"""

from collections.abc import Sequence
from typing import Any

from app.services.knowledge_base import get_knowledge_base_snapshot, load_products

from .matching_runtime import ProductRowLike
from .scoring import (
    ALIAS_FIELD_BONUS,
    _alias_score,
    _alias_specificity_bonus,
    _context_bonus,
    _matching_clues,
    _product_family,
    _product_subfamily,
    _string_list,
    _trait_overlap_score,
)


def _best_alias_match(text: str, product: ProductRowLike) -> tuple[str | None, int, list[str]]:
    best_alias = None
    best_score = 0
    best_reasons: list[str] = []
    seen_aliases: set[str] = set()

    for field, field_bonus in ALIAS_FIELD_BONUS.items():
        for alias in _string_list(product.get(field)):
            if alias in seen_aliases:
                continue
            seen_aliases.add(alias)

            score = _alias_score(text, alias)
            if score <= 0:
                continue

            reasons = [f"matched {field.replace('_', ' ')[:-1]} '{alias}'"]
            alias_bonus = _alias_specificity_bonus(alias)
            if alias_bonus:
                score += alias_bonus
                reasons.append(f"alias specificity {alias_bonus:+d}")
            if field_bonus:
                score += field_bonus
                reasons.append(f"{field} bonus {field_bonus:+d}")

            if best_alias is None or score > best_score:
                best_alias = alias
                best_score = score
                best_reasons = reasons

    return best_alias, best_score, best_reasons


def _family_seed_candidates(text: str, explicit_traits: set[str]) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    for product in get_knowledge_base_snapshot().products:
        best_alias, alias_score, alias_reasons = _best_alias_match(text, product)
        if best_alias is None:
            continue

        family_traits = set(_string_list(product.get("family_traits")) or _string_list(product.get("implied_traits")))
        score = alias_score
        reasons = list(alias_reasons)

        overlap = _trait_overlap_score(explicit_traits, family_traits, weight=5)
        if overlap:
            score += overlap
            reasons.append(f"family trait overlap +{overlap}")

        bonus, bonus_reasons = _context_bonus(text, product, explicit_traits)
        score += bonus
        reasons.extend(bonus_reasons)

        candidates.append(
            {
                "id": product["id"],
                "family": _product_family(product),
                "subtype": _product_subfamily(product),
                "label": product.get("label", product["id"]),
                "product": product,
                "matched_alias": best_alias,
                "score": score,
                "reasons": reasons,
            }
        )

    candidates.sort(key=lambda row: (-row["score"], row["id"]))
    return candidates


def _family_confidence(candidate: dict[str, Any], next_candidate: dict[str, Any] | None) -> str:
    score = candidate["score"]
    gap = score - next_candidate["score"] if next_candidate else score

    if score >= 160 and gap >= 20:
        return "high"
    if score >= 115 and gap >= 8:
        return "medium"
    if score >= 95:
        return "medium"
    return "low"


def _clue_score(text: str, product: ProductRowLike) -> tuple[int, list[str], list[str], list[str], bool]:
    required_hits = _matching_clues(text, _string_list(product.get("required_clues")))
    preferred_hits = _matching_clues(text, _string_list(product.get("preferred_clues")))
    exclude_hits = _matching_clues(text, _string_list(product.get("exclude_clues")))

    score = len(required_hits) * 26 + len(preferred_hits) * 14 - len(exclude_hits) * 34
    reasons = [f"required clue '{clue}'" for clue in required_hits]
    reasons.extend(f"preferred clue '{clue}'" for clue in preferred_hits)
    reasons.extend(f"exclude clue '{clue}'" for clue in exclude_hits)

    required_clues = _string_list(product.get("required_clues"))
    if required_clues and not required_hits:
        score -= 18
        reasons.append("missing required subtype clues")

    decisive = bool(required_hits or len(preferred_hits) >= 2)
    positive_clues = required_hits + preferred_hits
    negative_clues = exclude_hits
    return score, reasons, positive_clues, negative_clues, decisive


def _family_members(products: Sequence[ProductRowLike], family: str) -> list[ProductRowLike]:
    return [product for product in products if _product_family(product) == family]


def _subtype_candidates(
    text: str,
    explicit_traits: set[str],
    family_score: int,
    family_products: Sequence[ProductRowLike],
) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    for product in family_products:
        best_alias, alias_score, alias_reasons = _best_alias_match(text, product)
        clue_score, clue_reasons, positive_clues, negative_clues, decisive = _clue_score(text, product)
        family_overlap = _trait_overlap_score(explicit_traits, set(_string_list(product.get("family_traits"))), weight=4)
        subtype_overlap = _trait_overlap_score(
            explicit_traits,
            set(_string_list(product.get("subtype_traits")) or _string_list(product.get("implied_traits"))),
            weight=7,
        )
        bonus, bonus_reasons = _context_bonus(text, product, explicit_traits)

        if best_alias is None and not positive_clues and subtype_overlap == 0 and family_overlap == 0:
            continue

        score = alias_score + clue_score + family_overlap + subtype_overlap + bonus
        reasons = list(alias_reasons)
        if family_overlap:
            reasons.append(f"family trait overlap +{family_overlap}")
        if subtype_overlap:
            reasons.append(f"subtype trait overlap +{subtype_overlap}")
        reasons.extend(clue_reasons)
        reasons.extend(bonus_reasons)

        candidates.append(
            {
                "id": product["id"],
                "label": product.get("label", product["id"]),
                "family": _product_family(product),
                "subtype": _product_subfamily(product),
                "matched_alias": best_alias,
                "family_score": family_score,
                "subtype_score": score,
                "score": score,
                "reasons": reasons,
                "positive_clues": positive_clues,
                "negative_clues": negative_clues,
                "decisive": decisive,
                "implied_traits": _string_list(product.get("implied_traits")),
                "family_traits": _string_list(product.get("family_traits")),
                "subtype_traits": _string_list(product.get("subtype_traits")) or _string_list(product.get("implied_traits")),
                "functional_classes": _string_list(product.get("functional_classes")),
                "likely_standards": _string_list(product.get("likely_standards")),
                "confusable_with": _string_list(product.get("confusable_with")),
            }
        )

    candidates.sort(key=lambda row: (-row["score"], row["id"]))
    return candidates


def _candidate_confidence(index: int, candidate: dict[str, Any], next_candidate: dict[str, Any] | None) -> str:
    score = candidate["score"]
    gap = score - next_candidate["score"] if next_candidate else score

    if index == 0 and score >= 155 and gap >= 22:
        return "high"
    if index == 0 and score >= 120 and gap >= 10:
        return "medium"
    if score >= 105:
        return "medium"
    return "low"


def _common_strings(rows: list[dict[str, Any]], field: str) -> list[str]:
    if not rows:
        return []

    common = set(_string_list(rows[0].get(field)))
    for row in rows[1:]:
        common &= set(_string_list(row.get(field)))
    return sorted(common)


def _resolve_family_stage(
    top_family: dict[str, Any],
    next_family: dict[str, Any] | None,
    top_row: dict[str, Any],
    next_subtype: dict[str, Any] | None,
    subtype_band: list[dict[str, Any]],
    subtype_confidence: str,
    same_family_gap: int,
    decisive_medium: bool,
    family_products: list[Any],
) -> tuple[str, list[str]]:
    contradictions: list[str] = []

    cross_family_ambiguous = bool(
        next_family
        and top_family["score"] - next_family["score"] < 8
        and next_family["family"] != top_family["family"]
    )
    if cross_family_ambiguous and next_family is not None:
        contradictions.append(
            "Product identification is ambiguous between "
            f"{top_family['representative']['id'].replace('_', ' ')} and "
            f"{next_family['representative']['id'].replace('_', ' ')}."
        )
        return "ambiguous", contradictions
    if next_subtype and top_row["negative_clues"] and next_subtype.get("positive_clues"):
        return "family", contradictions
    if len(subtype_band) > 1 and same_family_gap < 12:
        return "family", contradictions
    if subtype_confidence == "high" or decisive_medium or len(family_products) == 1:
        return "subtype", contradictions
    return "family", contradictions


def _collect_result_products(
    family_stage: str,
    top_row: dict[str, Any],
    subtype_band: list[dict[str, Any]],
    next_subtype: dict[str, Any] | None,
    top_family: dict[str, Any],
    next_family: dict[str, Any] | None,
    family_confidence: str,
    subtype_confidence: str,
    common_classes: list[str],
    common_standards: list[str],
) -> dict[str, Any]:
    functional_classes: set[str] = set(_string_list(top_row.get("functional_classes")))
    confirmed_functional_classes: set[str] = set()
    preferred_standard_codes: list[str] = []
    confirmed_products: list[str] = []
    matched_products = [row["id"] for row in subtype_band]
    routing_matched_products: list[str] = []
    product_subtype = top_row["id"] if family_stage == "subtype" else None
    product_match_confidence = subtype_confidence

    if family_stage == "ambiguous" and next_family is not None:
        matched_products = [top_family["representative"]["id"], next_family["representative"]["id"]]
        functional_classes = set()
        product_match_confidence = "low"
    elif family_stage == "family":
        functional_classes = set(common_classes)
        if family_confidence == "high":
            confirmed_functional_classes.update(common_classes)
        preferred_standard_codes = common_standards
        product_match_confidence = "medium" if family_confidence == "high" else family_confidence
    else:
        routing_matched_products = [top_row["id"]]
        preferred_standard_codes = _string_list(top_row.get("likely_standards"))
        if subtype_confidence == "high":
            confirmed_products = [top_row["id"]]
            confirmed_functional_classes.update(_string_list(top_row.get("functional_classes")))
        elif common_classes:
            confirmed_functional_classes.update(common_classes)

    return {
        "product_subtype": product_subtype,
        "product_match_confidence": product_match_confidence,
        "matched_products": matched_products,
        "routing_matched_products": routing_matched_products,
        "confirmed_products": confirmed_products,
        "functional_classes": functional_classes,
        "confirmed_functional_classes": confirmed_functional_classes,
        "preferred_standard_codes": preferred_standard_codes,
    }


def _build_product_candidates_list(
    subtype_candidates: list[dict[str, Any]],
    cross_family_ambiguous: bool,
    top_family: dict[str, Any],
    next_family: dict[str, Any] | None,
) -> list[dict[str, Any]]:
    public_candidates = list(subtype_candidates[:5])
    if cross_family_ambiguous and next_family is not None:
        representative = next_family["representative"]
        public_candidates = public_candidates + [
            {
                "id": representative["id"],
                "label": representative["label"],
                "family": representative["family"],
                "subtype": representative["subtype"],
                "matched_alias": representative["matched_alias"],
                "family_score": next_family["score"],
                "subtype_score": representative["score"],
                "score": representative["score"],
                "reasons": representative["reasons"],
                "positive_clues": [],
                "negative_clues": [],
                "likely_standards": _string_list(representative["product"].get("likely_standards")),
            }
        ]

    product_candidates = []
    for idx, candidate in enumerate(public_candidates[:5]):
        confidence = _candidate_confidence(
            idx,
            candidate,
            public_candidates[idx + 1] if idx + 1 < len(public_candidates) else None,
        )
        product_candidates.append(
            {
                "id": candidate["id"],
                "label": candidate["label"],
                "family": candidate.get("family"),
                "subtype": candidate.get("subtype"),
                "matched_alias": candidate.get("matched_alias"),
                "family_score": int(candidate.get("family_score", candidate.get("score", 0))),
                "subtype_score": int(candidate.get("subtype_score", candidate.get("score", 0))),
                "score": int(candidate.get("score", 0)),
                "confidence": confidence,
                "reasons": candidate.get("reasons", []),
                "positive_clues": candidate.get("positive_clues", []),
                "negative_clues": candidate.get("negative_clues", []),
                "likely_standards": candidate.get("likely_standards", []),
            }
        )
    return product_candidates


def _hierarchical_product_match(text: str, explicit_traits: set[str]) -> dict[str, Any]:
    products = load_products()
    seed_candidates = _family_seed_candidates(text, explicit_traits)
    if not seed_candidates:
        return {
            "product_family": None,
            "product_family_confidence": "low",
            "product_subtype": None,
            "product_subtype_confidence": "low",
            "product_match_stage": "ambiguous",
            "product_type": None,
            "product_match_confidence": "low",
            "product_candidates": [],
            "matched_products": [],
            "routing_matched_products": [],
            "confirmed_products": [],
            "family_traits": set(),
            "subtype_traits": set(),
            "preferred_standard_codes": [],
            "functional_classes": set(),
            "confirmed_functional_classes": set(),
            "diagnostics": ["product_winner=none"],
            "contradictions": [],
        }

    by_family: dict[str, dict[str, Any]] = {}
    for row in seed_candidates:
        family = row["family"]
        existing = by_family.get(family)
        if existing is None or row["score"] > existing["score"]:
            by_family[family] = {"family": family, "score": row["score"], "representative": row}

    family_candidates = sorted(by_family.values(), key=lambda row: (-row["score"], row["family"]))
    top_family = family_candidates[0]
    next_family = family_candidates[1] if len(family_candidates) > 1 else None
    family_confidence = _family_confidence(top_family, next_family)
    cross_family_ambiguous = bool(
        next_family
        and top_family["score"] - next_family["score"] < 8
        and next_family["family"] != top_family["family"]
    )

    family_products = _family_members(products, top_family["family"])
    subtype_candidates = _subtype_candidates(text, explicit_traits, top_family["score"], family_products)
    if not subtype_candidates:
        subtype_candidates = [
            {
                **top_family["representative"],
                "family_score": top_family["score"],
                "subtype_score": top_family["score"],
                "positive_clues": [],
                "negative_clues": [],
                "decisive": False,
                "implied_traits": _string_list(top_family["representative"]["product"].get("implied_traits")),
                "family_traits": _string_list(top_family["representative"]["product"].get("family_traits")),
                "subtype_traits": _string_list(top_family["representative"]["product"].get("subtype_traits")),
                "functional_classes": _string_list(top_family["representative"]["product"].get("functional_classes")),
                "likely_standards": _string_list(top_family["representative"]["product"].get("likely_standards")),
                "confusable_with": _string_list(top_family["representative"]["product"].get("confusable_with")),
            }
        ]

    top_row = subtype_candidates[0]
    next_subtype = subtype_candidates[1] if len(subtype_candidates) > 1 else None
    subtype_confidence = _candidate_confidence(0, top_row, next_subtype)
    same_family_gap = top_row["score"] - next_subtype["score"] if next_subtype else top_row["score"]
    subtype_band = [row for row in subtype_candidates if top_row["score"] - row["score"] <= 12][:3]
    decisive_medium = subtype_confidence == "medium" and (top_row["decisive"] or bool(top_row["matched_alias"]))

    family_stage, contradictions = _resolve_family_stage(
        top_family,
        next_family,
        top_row,
        next_subtype,
        subtype_band,
        subtype_confidence,
        same_family_gap,
        decisive_medium,
        family_products,
    )
    if family_stage == "family" and next_subtype and next_subtype["id"] not in {row["id"] for row in subtype_band}:
        subtype_band = [top_row, next_subtype]

    common_classes = _common_strings(subtype_band, "functional_classes")
    common_standards = _common_strings(subtype_band, "likely_standards")
    stage_result = _collect_result_products(
        family_stage,
        top_row,
        subtype_band,
        next_subtype,
        top_family,
        next_family,
        family_confidence,
        subtype_confidence,
        common_classes,
        common_standards,
    )

    family_traits = set(_string_list(family_products[0].get("family_traits")) if family_products else [])
    subtype_traits = set(_string_list(top_row.get("subtype_traits")))

    product_candidates = _build_product_candidates_list(
        subtype_candidates,
        cross_family_ambiguous,
        top_family,
        next_family,
    )

    diagnostics = [
        f"product_family={top_family['family']}",
        f"product_family_confidence={family_confidence}",
        f"product_subtype_candidate={top_row['id']}",
        f"product_subtype_confidence={subtype_confidence}",
        f"product_match_stage={family_stage}",
    ]

    return {
        "product_family": top_family["family"],
        "product_family_confidence": family_confidence,
        "product_subtype": stage_result["product_subtype"],
        "product_subtype_confidence": subtype_confidence,
        "product_match_stage": family_stage,
        "product_type": top_row["id"],
        "product_match_confidence": stage_result["product_match_confidence"],
        "product_candidates": product_candidates,
        "matched_products": stage_result["matched_products"],
        "routing_matched_products": stage_result["routing_matched_products"],
        "confirmed_products": stage_result["confirmed_products"],
        "family_traits": family_traits,
        "subtype_traits": subtype_traits if family_stage == "subtype" else set(),
        "preferred_standard_codes": stage_result["preferred_standard_codes"],
        "functional_classes": stage_result["functional_classes"],
        "confirmed_functional_classes": stage_result["confirmed_functional_classes"],
        "diagnostics": diagnostics,
        "contradictions": contradictions,
    }


def _select_matched_products(product_candidates: list[dict[str, Any]]) -> list[str]:
    if not product_candidates:
        return []

    top_score = product_candidates[0]["score"]
    selected: list[str] = []

    for idx, candidate in enumerate(product_candidates[:4]):
        within_primary_band = top_score - candidate["score"] <= 18
        close_medium_alternative = idx > 0 and candidate["confidence"] != "low" and top_score - candidate["score"] <= 12
        if idx == 0 or within_primary_band or close_medium_alternative:
            selected.append(candidate["id"])

    return selected[:3] or [product_candidates[0]["id"]]


__all__ = [
    "_hierarchical_product_match",
    "_select_matched_products",
]
