from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any

from app.domain.catalog_types import ProductCatalogRow
from app.services.knowledge_base import get_knowledge_base_snapshot, load_products

from .normalization import normalize
from .scoring import (
    ALIAS_FIELD_BONUS,
    ENGINE_VERSION,
    SERVICE_DEPENDENT_TRAITS,
    _alias_score,
    _alias_specificity_bonus,
    _context_bonus,
    _matching_clues,
    _product_family,
    _product_subfamily,
    _string_list,
    _trait_overlap_score,
)


_PRODUCT_TRAIT_BUCKET_CACHE: dict[str, tuple[set[str], set[str]]] = {}


@dataclass(frozen=True, slots=True)
class CompiledPhrase:
    raw: str
    normalized: str
    pattern: re.Pattern
    token_terms: frozenset[str]


@dataclass(frozen=True, slots=True)
class CompiledAlias:
    raw: str
    normalized: str
    field: str
    field_bonus: int
    exact_pattern: re.Pattern
    gap_pattern: re.Pattern | None
    specificity_bonus: int
    token_terms: frozenset[str]


@dataclass(frozen=True, slots=True)
class CompiledProductMatcher:
    id: str
    family: str
    subtype: str
    product: ProductCatalogRow
    aliases: tuple[CompiledAlias, ...]
    family_keywords: tuple[CompiledPhrase, ...]
    required_clues: tuple[CompiledPhrase, ...]
    preferred_clues: tuple[CompiledPhrase, ...]
    exclude_clues: tuple[CompiledPhrase, ...]
    alias_terms: frozenset[str]
    family_keyword_terms: frozenset[str]
    clue_terms: frozenset[str]
    shortlist_traits: frozenset[str]
    core_traits: frozenset[str]
    default_traits: frozenset[str]
    family_traits: frozenset[str]


@dataclass(frozen=True, slots=True)
class ProductMatchingSnapshot:
    catalog_version: str | None
    products: tuple[CompiledProductMatcher, ...]
    by_id: dict[str, CompiledProductMatcher]

def _best_alias_match(text: str, product: dict[str, Any]) -> tuple[str | None, int, list[str]]:
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


def _clue_score(text: str, product: dict[str, Any]) -> tuple[int, list[str], list[str], list[str], bool]:
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


def _family_members(products: list[dict[str, Any]], family: str) -> list[dict[str, Any]]:
    return [product for product in products if _product_family(product) == family]


def _subtype_candidates(
    text: str,
    explicit_traits: set[str],
    family_score: int,
    family_products: list[dict[str, Any]],
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
    """Determine whether matching resolved to subtype, family, or ambiguous.

    Returns (stage, contradictions).
    """
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
    """Collect products, traits, and confidence based on the resolved stage."""
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
    else:  # subtype
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
    """Build the public-facing product_candidates list."""
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

    # --- Stage 1: resolve best family from seed candidates ---
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

    # --- Stage 2: resolve best subtype within the winning family ---
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

    # --- Determine match stage (subtype / family / ambiguous) ---
    family_stage, contradictions = _resolve_family_stage(
        top_family, next_family,
        top_row, next_subtype,
        subtype_band, subtype_confidence, same_family_gap,
        decisive_medium, family_products,
    )
    if family_stage == "family" and next_subtype and next_subtype["id"] not in {row["id"] for row in subtype_band}:
        subtype_band = [top_row, next_subtype]

    common_classes = _common_strings(subtype_band, "functional_classes")
    common_standards = _common_strings(subtype_band, "likely_standards")

    # --- Collect products, traits, and confidence for the resolved stage ---
    stage_result = _collect_result_products(
        family_stage, top_row, subtype_band, next_subtype,
        top_family, next_family, family_confidence, subtype_confidence,
        common_classes, common_standards,
    )

    family_traits = set(_string_list(family_products[0].get("family_traits")) if family_products else [])
    subtype_traits = set(_string_list(top_row.get("subtype_traits")))

    product_candidates = _build_product_candidates_list(
        subtype_candidates, cross_family_ambiguous, top_family, next_family
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

def _product_family_keywords(product: dict[str, Any]) -> list[str]:
    keywords = _string_list(product.get("family_keywords"))
    family_phrase = _product_family(product).replace("_", " ")
    if family_phrase and family_phrase != product["id"] and family_phrase not in keywords:
        keywords.append(family_phrase)
    return keywords


def _compile_phrase(raw: str) -> CompiledPhrase | None:
    normalized = normalize(raw)
    if not normalized:
        return None
    return CompiledPhrase(
        raw=raw,
        normalized=normalized,
        pattern=re.compile(rf"(?<!\w){re.escape(normalized)}(?!\w)"),
        token_terms=frozenset(normalized.split()),
    )


def _compile_phrases(raw_values: list[str]) -> tuple[CompiledPhrase, ...]:
    phrases: list[CompiledPhrase] = []
    for raw in raw_values:
        compiled_phrase = _compile_phrase(raw)
        if compiled_phrase is not None:
            phrases.append(compiled_phrase)
    return tuple(phrases)


def _compile_alias(raw: str, field: str, field_bonus: int) -> CompiledAlias | None:
    normalized = normalize(raw)
    if not normalized:
        return None
    tokens = normalized.split()
    gap_pattern = (
        re.compile(r"\b" + r"\b(?:\s+\w+){0,2}\s+\b".join(re.escape(token) for token in tokens) + r"\b")
        if len(tokens) >= 2
        else None
    )
    return CompiledAlias(
        raw=raw,
        normalized=normalized,
        field=field,
        field_bonus=field_bonus,
        exact_pattern=re.compile(rf"(?<!\w){re.escape(normalized)}(?!\w)"),
        gap_pattern=gap_pattern,
        specificity_bonus=_alias_specificity_bonus(raw),
        token_terms=frozenset(tokens),
    )


def _compiled_phrase_hits(text: str, phrases: tuple[CompiledPhrase, ...]) -> list[str]:
    return [phrase.raw for phrase in phrases if phrase.pattern.search(text)]


def build_product_matching_snapshot(
    products: list[dict[str, Any]],
    trait_ids: set[str],
    catalog_version: str | None = None,
) -> ProductMatchingSnapshot:
    compiled_products: list[CompiledProductMatcher] = []
    compiled_by_id: dict[str, CompiledProductMatcher] = {}

    for product in products:
        aliases: list[CompiledAlias] = []
        alias_terms: set[str] = set()
        seen_aliases: set[str] = set()
        for field, field_bonus in ALIAS_FIELD_BONUS.items():
            for alias in _string_list(product.get(field)):
                compiled_alias = _compile_alias(alias, field, field_bonus)
                if compiled_alias is None or compiled_alias.normalized in seen_aliases:
                    continue
                seen_aliases.add(compiled_alias.normalized)
                aliases.append(compiled_alias)
                alias_terms.update(compiled_alias.token_terms)

        family_keywords = _compile_phrases(_product_family_keywords(product))
        required_clues = _compile_phrases(_string_list(product.get("required_clues")))
        preferred_clues = _compile_phrases(_string_list(product.get("preferred_clues")))
        exclude_clues = _compile_phrases(_string_list(product.get("exclude_clues")))

        family_keyword_terms = {term for phrase in family_keywords for term in phrase.token_terms}
        clue_terms = {
            term
            for phrase in required_clues + preferred_clues + exclude_clues
            for term in phrase.token_terms
        }
        core_traits, default_traits = _compute_product_trait_buckets(product)
        family_traits = set(_string_list(product.get("family_traits"))) or set(core_traits)

        compiled = CompiledProductMatcher(
            id=product["id"],
            family=_product_family(product),
            subtype=_product_subfamily(product),
            product=product,
            aliases=tuple(aliases),
            family_keywords=family_keywords,
            required_clues=required_clues,
            preferred_clues=preferred_clues,
            exclude_clues=exclude_clues,
            alias_terms=frozenset(alias_terms),
            family_keyword_terms=frozenset(family_keyword_terms),
            clue_terms=frozenset(clue_terms),
            shortlist_traits=frozenset((core_traits | default_traits | family_traits) & trait_ids),
            core_traits=frozenset(core_traits),
            default_traits=frozenset(default_traits),
            family_traits=frozenset(family_traits),
        )
        compiled_products.append(compiled)
        compiled_by_id[compiled.id] = compiled

    return ProductMatchingSnapshot(
        catalog_version=catalog_version,
        products=tuple(compiled_products),
        by_id=compiled_by_id,
    )


def _product_matching_snapshot() -> ProductMatchingSnapshot:
    snapshot = get_knowledge_base_snapshot()
    compiled = snapshot.classifier_runtime
    if isinstance(compiled, ProductMatchingSnapshot):
        return compiled
    return build_product_matching_snapshot(
        products=snapshot.products,
        trait_ids={row["id"] for row in snapshot.traits},
        catalog_version=snapshot.meta.get("version"),
    )


def _shortlist_product_matchers_v2(text: str, signal_traits: set[str]) -> tuple[tuple[CompiledProductMatcher, ...], dict[str, int]]:
    snapshot = _product_matching_snapshot()
    text_terms = set(text.split())
    shortlist_scoring: dict[str, int] = {}
    shortlisted: list[CompiledProductMatcher] = []

    for compiled in snapshot.products:
        alias_term_hits = len(compiled.alias_terms & text_terms)
        family_term_hits = len(compiled.family_keyword_terms & text_terms)
        clue_term_hits = len(compiled.clue_terms & text_terms)
        trait_hits = len(compiled.shortlist_traits & signal_traits)

        cheap_score = alias_term_hits * 5 + family_term_hits * 4 + clue_term_hits * 3 + min(trait_hits, 4)
        if cheap_score <= 0:
            continue

        shortlist_scoring[compiled.id] = cheap_score
        shortlisted.append(compiled)

    if not shortlisted:
        fallback = tuple(snapshot.products)
        return fallback, {compiled.id: 0 for compiled in fallback}

    shortlisted.sort(
        key=lambda compiled: (
            -shortlist_scoring[compiled.id],
            -len(compiled.alias_terms & text_terms),
            -len(compiled.family_keyword_terms & text_terms),
            -len(compiled.shortlist_traits & signal_traits),
            compiled.id,
        )
    )

    max_candidates = 120
    if len(shortlisted) > max_candidates:
        shortlisted = shortlisted[:max_candidates]
        shortlist_scoring = {compiled.id: shortlist_scoring[compiled.id] for compiled in shortlisted}

    return tuple(shortlisted), shortlist_scoring


def _compute_product_trait_buckets(product: dict[str, Any]) -> tuple[set[str], set[str]]:
    from .traits import _expand_related_traits

    implied_traits = set(_string_list(product.get("implied_traits")))
    family_traits = set(_string_list(product.get("family_traits")))
    subtype_traits = set(_string_list(product.get("subtype_traits")) or _string_list(product.get("implied_traits")))
    raw_core = set(_string_list(product.get("core_traits")))
    raw_default = set(_string_list(product.get("default_traits")))

    if not raw_core:
        raw_core = set(family_traits | subtype_traits or implied_traits)
    if not raw_default:
        raw_default = implied_traits - raw_core

    raw_default |= raw_core & SERVICE_DEPENDENT_TRAITS
    raw_core -= SERVICE_DEPENDENT_TRAITS
    raw_default |= implied_traits - raw_core

    core_traits = _expand_related_traits(raw_core)
    default_traits = _expand_related_traits(raw_default) - core_traits
    return core_traits, default_traits


def _product_trait_buckets(product: dict[str, Any]) -> tuple[set[str], set[str]]:
    pid = product["id"]
    cached = _PRODUCT_TRAIT_BUCKET_CACHE.get(pid)
    if cached is not None:
        return cached

    result = _compute_product_trait_buckets(product)
    _PRODUCT_TRAIT_BUCKET_CACHE[pid] = result
    return result


def _candidate_confidence_v2(candidate: dict[str, Any], next_candidate: dict[str, Any] | None = None) -> str:
    score = int(candidate.get("score", 0))
    gap = score - int(next_candidate.get("score", 0)) if next_candidate else score
    direct_signals = int(candidate.get("direct_signal_count", 0))
    if score >= 150 and gap >= 16 and direct_signals >= 2:
        return "high"
    if score >= 110 and gap >= 8 and direct_signals >= 1:
        return "medium"
    if score >= 85 and direct_signals >= 2:
        return "medium"
    return "low"


def _build_product_candidate_v2(
    text: str,
    signal_traits: set[str],
    compiled: CompiledProductMatcher,
) -> dict[str, Any] | None:
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

    return {
        "id": product["id"],
        "label": product.get("label", product["id"]),
        "family": compiled.family,
        "subtype": compiled.subtype,
        "genres": _string_list(product.get("genres")),
        "product": product,
        "matched_alias": best_alias,
        "alias_hits": [best_alias] if best_alias else [],
        "family_keyword_hits": family_keyword_hits,
        "positive_clues": positive_clues,
        "negative_clues": negative_clues,
        "decisive": decisive or (best_alias is not None and alias_score >= 115) or bool(family_keyword_hits),
        "score": score,
        "direct_signal_count": direct_signal_count,
        "reasons": reasons,
        "core_traits": sorted(core_traits),
        "default_traits": sorted(default_traits),
        "family_traits": sorted(family_traits),
        "subtype_traits": _string_list(product.get("subtype_traits")) or _string_list(product.get("implied_traits")),
        "functional_classes": _string_list(product.get("functional_classes")),
        "likely_standards": _string_list(product.get("likely_standards")),
        "confusable_with": _string_list(product.get("confusable_with")),
    }


def _common_sets(rows: list[dict[str, Any]], field: str) -> set[str]:
    if not rows:
        return set()
    common = set(_string_list(rows[0].get(field)))
    for row in rows[1:]:
        common &= set(_string_list(row.get(field)))
    return common


def _hierarchical_product_match_v2(text: str, signal_traits: set[str]) -> dict[str, Any]:
    shortlisted_matchers, shortlist_scoring = _shortlist_product_matchers_v2(text, signal_traits)
    candidates = [
        candidate
        for matcher in shortlisted_matchers
        if (candidate := _build_product_candidate_v2(text, signal_traits, matcher)) is not None
    ]
    candidates.sort(key=lambda row: (-int(row["score"]), row["id"]))

    if not candidates:
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
            "product_core_traits": set(),
            "product_default_traits": set(),
            "product_genres": set(),
            "preferred_standard_codes": [],
            "functional_classes": set(),
            "confirmed_functional_classes": set(),
            "diagnostics": [
                "product_shortlist_candidates=0",
                f"product_shortlist_catalog={len(_product_matching_snapshot().products)}",
                "product_winner=none",
            ],
            "contradictions": [],
            "audit": {
                "engine_version": ENGINE_VERSION,
                "normalized_text": text,
                "retrieval_basis": [],
                "alias_hits": [],
                "family_keyword_hits": [],
                "clue_hits": [],
                "negations": [],
                "ambiguity_reason": None,
            },
        }

    families: dict[str, dict[str, Any]] = {}
    for row in candidates:
        family = row["family"]
        existing = families.get(family)
        if existing is None or int(row["score"]) > int(existing["score"]):
            families[family] = row

    family_candidates = sorted(families.values(), key=lambda row: (-int(row["score"]), row["family"]))
    top_family = family_candidates[0]
    next_family = family_candidates[1] if len(family_candidates) > 1 else None
    family_confidence = _candidate_confidence_v2(top_family, next_family)

    family_rows = [row for row in candidates if row["family"] == top_family["family"]]
    top_row = family_rows[0]
    next_subtype = family_rows[1] if len(family_rows) > 1 else None
    subtype_confidence = _candidate_confidence_v2(top_row, next_subtype)
    contradictions: list[str] = []
    ambiguity_reason: str | None = None

    family_gap = int(top_family["score"]) - int(next_family["score"]) if next_family else int(top_family["score"])
    subtype_gap = int(top_row["score"]) - int(next_subtype["score"]) if next_subtype else int(top_row["score"])
    close_family_competition = bool(next_family and family_gap < 8 and next_family["family"] != top_family["family"])
    close_subtype_competition = bool(next_subtype and subtype_gap < 10)

    if close_family_competition:
        assert next_family is not None
        family_stage = "ambiguous"
        ambiguity_reason = (
            f"Product identification remains ambiguous between {top_family['id'].replace('_', ' ')} "
            f"and {next_family['id'].replace('_', ' ')}."
        )
        contradictions.append(ambiguity_reason)
    elif next_subtype and top_row.get("negative_clues") and next_subtype.get("positive_clues"):
        family_stage = "family"
        ambiguity_reason = f"Confusable subtype clues remain unresolved within family {top_family['family'].replace('_', ' ')}."
    elif close_subtype_competition:
        family_stage = "family"
        ambiguity_reason = f"Subtype evidence is too close within family {top_family['family'].replace('_', ' ')}."
    elif subtype_confidence == "high" or (subtype_confidence == "medium" and top_row["decisive"]):
        family_stage = "subtype"
    elif family_confidence in {"high", "medium"}:
        family_stage = "family"
    else:
        family_stage = "ambiguous"
        ambiguity_reason = f"Product evidence for {top_family['label']} is too weak to confirm a subtype."

    subtype_band = [row for row in family_rows if int(top_row["score"]) - int(row["score"]) <= 10][:3]
    if family_stage == "family" and next_subtype and next_subtype["id"] not in {row["id"] for row in subtype_band}:
        subtype_band = [top_row, next_subtype]

    common_classes = _common_strings(subtype_band, "functional_classes")
    common_standards = _common_strings(subtype_band, "likely_standards")
    common_core_traits = _common_sets(subtype_band, "core_traits")
    common_default_traits = _common_sets(subtype_band, "default_traits")
    common_genres = _common_sets(subtype_band, "genres")

    product_core_traits = set(_string_list(top_row.get("core_traits")))
    product_default_traits = set(_string_list(top_row.get("default_traits")))
    product_genres = set(_string_list(top_row.get("genres")))
    functional_classes = set(_string_list(top_row.get("functional_classes")))
    confirmed_functional_classes: set[str] = set()
    preferred_standard_codes: list[str] = []
    confirmed_products: list[str] = []
    matched_products = [row["id"] for row in subtype_band]
    routing_matched_products: list[str] = []
    product_subtype = top_row["id"] if family_stage == "subtype" else None
    product_type = top_row["id"]
    product_match_confidence = subtype_confidence

    if family_stage == "ambiguous" and next_family is not None:
        matched_products = [top_family["id"], next_family["id"]]
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
        routing_matched_products = [top_row["id"]]
        preferred_standard_codes = _string_list(top_row.get("likely_standards"))
        if subtype_confidence == "high":
            confirmed_products = [top_row["id"]]
            confirmed_functional_classes.update(_string_list(top_row.get("functional_classes")))
        elif common_classes:
            confirmed_functional_classes.update(common_classes)

    public_candidates = family_rows[:5]
    if close_family_competition and next_family is not None and next_family not in public_candidates:
        public_candidates = public_candidates + [next_family]

    product_candidates: list[dict[str, Any]] = []
    for idx, candidate in enumerate(public_candidates[:5]):
        confidence = _candidate_confidence_v2(
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
                "family_score": int(families[candidate["family"]]["score"]) if candidate["family"] in families else int(candidate["score"]),
                "subtype_score": int(candidate.get("score", 0)),
                "score": int(candidate.get("score", 0)),
                "confidence": confidence,
                "reasons": candidate.get("reasons", []),
                "positive_clues": candidate.get("positive_clues", []),
                "negative_clues": candidate.get("negative_clues", []),
                "likely_standards": candidate.get("likely_standards", []),
            }
        )

    audit_rows = subtype_band if family_stage == "family" else [top_row]
    alias_hits = sorted({hit for row in audit_rows for hit in row.get("alias_hits", []) if hit})
    family_keyword_hits = sorted({hit for row in audit_rows for hit in row.get("family_keyword_hits", []) if hit})
    clue_hits = sorted({hit for row in audit_rows for hit in row.get("positive_clues", []) if hit})

    diagnostics = [
        f"product_shortlist_candidates={len(shortlisted_matchers)}",
        f"product_shortlist_catalog={len(_product_matching_snapshot().products)}",
        f"product_family={top_family['family']}",
        f"product_family_confidence={family_confidence}",
        f"product_subtype_candidate={top_row['id']}",
        f"product_subtype_confidence={subtype_confidence}",
        f"product_match_stage={family_stage}",
    ]
    top_shortlist = sorted(shortlist_scoring.items(), key=lambda item: (-item[1], item[0]))[:5]
    if top_shortlist:
        diagnostics.append(
            "product_shortlist_top="
            + ",".join(f"{product_id}:{score}" for product_id, score in top_shortlist)
        )

    return {
        "product_family": top_family["family"],
        "product_family_confidence": family_confidence,
        "product_subtype": product_subtype,
        "product_subtype_confidence": subtype_confidence,
        "product_match_stage": family_stage,
        "product_type": product_type,
        "product_match_confidence": product_match_confidence,
        "product_candidates": product_candidates,
        "matched_products": matched_products,
        "routing_matched_products": routing_matched_products,
        "confirmed_products": confirmed_products,
        "product_core_traits": product_core_traits,
        "product_default_traits": product_default_traits,
        "product_genres": product_genres,
        "preferred_standard_codes": preferred_standard_codes,
        "functional_classes": functional_classes,
        "confirmed_functional_classes": confirmed_functional_classes,
        "diagnostics": diagnostics,
        "contradictions": contradictions,
        "audit": {
            "engine_version": ENGINE_VERSION,
            "normalized_text": text,
            "retrieval_basis": top_row.get("reasons", []),
            "alias_hits": alias_hits,
            "family_keyword_hits": family_keyword_hits,
            "clue_hits": clue_hits,
            "negations": [],
            "ambiguity_reason": ambiguity_reason,
        },
    }


def reset_matching_cache() -> None:
    _PRODUCT_TRAIT_BUCKET_CACHE.clear()


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
