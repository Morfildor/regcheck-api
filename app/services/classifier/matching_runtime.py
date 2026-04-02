from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
import re
from typing import Any

from app.domain.catalog_types import ProductCatalogRow
from app.services.knowledge_base import get_knowledge_base_snapshot

from .normalization import normalize
from .scoring import (
    ALIAS_FIELD_BONUS,
    SERVICE_DEPENDENT_TRAITS,
    _alias_specificity_bonus,
    _product_family,
    _product_subfamily,
    _string_list,
)


_PRODUCT_TRAIT_BUCKET_CACHE: dict[str, tuple[set[str], set[str]]] = {}
ProductRowLike = ProductCatalogRow | Mapping[str, Any]


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


def _product_family_keywords(product: ProductRowLike) -> list[str]:
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
    products: Sequence[ProductCatalogRow],
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
        catalog_version=snapshot.meta.version,
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


def _compute_product_trait_buckets(product: ProductRowLike) -> tuple[set[str], set[str]]:
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


def _product_trait_buckets(product: ProductRowLike) -> tuple[set[str], set[str]]:
    pid = product["id"]
    cached = _PRODUCT_TRAIT_BUCKET_CACHE.get(pid)
    if cached is not None:
        return cached

    result = _compute_product_trait_buckets(product)
    _PRODUCT_TRAIT_BUCKET_CACHE[pid] = result
    return result


def reset_matching_cache() -> None:
    _PRODUCT_TRAIT_BUCKET_CACHE.clear()


__all__ = [
    "CompiledAlias",
    "CompiledPhrase",
    "CompiledProductMatcher",
    "ProductMatchingSnapshot",
    "ProductRowLike",
    "_compiled_phrase_hits",
    "_product_matching_snapshot",
    "_product_trait_buckets",
    "_shortlist_product_matchers_v2",
    "build_product_matching_snapshot",
    "reset_matching_cache",
]
