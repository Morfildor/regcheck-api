from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
import functools
import re
from typing import Any, Literal, overload

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
    generic_terms: frozenset[str]


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
    head_phrases: tuple[CompiledPhrase, ...]
    head_terms: frozenset[str]
    shortlist_traits: frozenset[str]
    core_traits: frozenset[str]
    default_traits: frozenset[str]
    family_traits: frozenset[str]
    family_required_traits: frozenset[str]
    route_anchor: str | None
    allowed_route_anchors: tuple[str, ...]
    boundary_tags: tuple[str, ...]
    boundary_tendencies: tuple[str, ...]
    max_match_stage: str | None


@dataclass(frozen=True, slots=True)
class ProductMatchingSnapshot:
    catalog_version: str | None
    products: tuple[CompiledProductMatcher, ...]
    by_id: dict[str, CompiledProductMatcher]
    head_phrases: tuple[CompiledPhrase, ...]
    head_terms: frozenset[str]


def _product_family_keywords(product: ProductRowLike) -> list[str]:
    keywords = _string_list(product.get("family_keywords"))
    family_phrase = _product_family(product).replace("_", " ")
    if family_phrase and family_phrase != product["id"] and family_phrase not in keywords:
        keywords.append(family_phrase)
    return keywords


PRODUCT_HEAD_TERMS = frozenset(
    {
        "adapter",
        "alarm",
        "arm",
        "backup",
        "box",
        "bracket",
        "cable",
        "camera",
        "charger",
        "connector",
        "controller",
        "display",
        "dock",
        "gateway",
        "headset",
        "hub",
        "injector",
        "intercom",
        "keypad",
        "lamp",
        "mirror",
        "mask",
        "module",
        "monitor",
        "mount",
        "operator",
        "panel",
        "player",
        "printer",
        "reader",
        "receiver",
        "scanner",
        "speaker",
        "stand",
        "station",
        "switch",
        "terminal",
        "transmitter",
        "ups",
        "unit",
        "visualizer",
    }
)
PRODUCT_MULTIWORD_HEADS = frozenset(
    {
        "access point",
        "access keypad",
        "access panel",
        "alarm keypad",
        "alarm keypad panel",
        "backup unit",
        "battery charger",
        "battery backup",
        "carbon monoxide alarm",
        "control module",
        "control panel",
        "document camera",
        "document camera visualizer",
        "digital signage player",
        "docking station",
        "door controller",
        "entry panel",
        "eye mask",
        "external power supply",
        "grow light",
        "grow light strip",
        "garage door controller",
        "garage opener controller",
        "heated belt",
        "heated neck wrap",
        "heated shoulder wrap",
        "heating pad controller",
        "induction hot plate",
        "induction cooker",
        "keypad panel",
        "kiosk display",
        "kvm switch",
        "load balancing meter",
        "meter module",
        "mini pc",
        "microphone receiver",
        "monitor arm",
        "monitor stand",
        "poe injector",
        "power bank",
        "power station",
        "portable power station",
        "smart meter display",
        "smart meter gateway",
        "smart intercom",
        "ring light",
        "smart smoke alarm",
        "smart display",
        "smart speaker",
        "smoke co alarm",
        "studio light",
        "terminal display",
        "thin client",
        "underblanket controller",
        "ups backup unit",
        "usb hub",
        "video intercom",
        "wireless microphone receiver",
    }
)


def _is_head_phrase(normalized: str) -> bool:
    tokens = normalized.split()
    if not tokens or len(tokens) > 4 or {"for", "with"} & set(tokens):
        return False
    if normalized in PRODUCT_MULTIWORD_HEADS:
        return True
    if len(tokens) >= 2 and " ".join(tokens[-2:]) in PRODUCT_MULTIWORD_HEADS:
        return True
    return tokens[-1] in PRODUCT_HEAD_TERMS


def _head_phrase_variants(normalized: str) -> tuple[str, ...]:
    tokens = normalized.split()
    if not tokens:
        return ()

    variants: list[str] = []
    for size in range(min(len(tokens), 4), 0, -1):
        phrase = " ".join(tokens[-size:])
        if _is_head_phrase(phrase):
            variants.append(phrase)
    return tuple(variants)


def _compile_head_phrases(product: ProductRowLike) -> tuple[CompiledPhrase, ...]:
    raw_values = (
        _string_list(product.get("strong_aliases"))
        + _string_list(product.get("aliases"))
        + _string_list(product.get("family_keywords"))
        + [str(product.get("label") or ""), _product_subfamily(product).replace("_", " ")]
    )
    phrases: list[CompiledPhrase] = []
    seen: set[str] = set()
    for raw in raw_values:
        normalized = normalize(raw)
        for variant in _head_phrase_variants(normalized):
            if variant in seen:
                continue
            seen.add(variant)
            compiled = _compile_phrase(variant)
            if compiled is not None:
                phrases.append(compiled)
    return tuple(phrases)


@functools.lru_cache(maxsize=4096)
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


@functools.lru_cache(maxsize=4096)
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
        generic_terms=frozenset(token for token in tokens if token in GENERIC_SHORTLIST_TERMS),
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
    global_head_phrases: dict[str, CompiledPhrase] = {}
    global_head_terms: set[str] = set()

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
        head_phrases = _compile_head_phrases(product)

        family_keyword_terms = {term for phrase in family_keywords for term in phrase.token_terms}
        clue_terms = {
            term
            for phrase in required_clues + preferred_clues + exclude_clues
            for term in phrase.token_terms
        }
        head_terms = {phrase.normalized.split()[-1] for phrase in head_phrases if phrase.token_terms}
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
            head_phrases=head_phrases,
            head_terms=frozenset(head_terms),
            shortlist_traits=frozenset((core_traits | default_traits | family_traits) & trait_ids),
            core_traits=frozenset(core_traits),
            default_traits=frozenset(default_traits),
            family_traits=frozenset(family_traits),
            family_required_traits=frozenset(_string_list(product.get("family_required_traits"))),
            route_anchor=str(product.get("route_anchor") or "").strip() or None,
            allowed_route_anchors=tuple(_string_list(product.get("family_allowed_route_anchors"))),
            boundary_tags=tuple(_string_list(product.get("boundary_tags"))),
            boundary_tendencies=tuple(_string_list(product.get("family_boundary_tendencies"))),
            max_match_stage=str(product.get("max_match_stage") or "").strip() or None,
        )
        compiled_products.append(compiled)
        compiled_by_id[compiled.id] = compiled
        global_head_terms.update(head_terms)
        for phrase in head_phrases:
            global_head_phrases.setdefault(phrase.normalized, phrase)

    return ProductMatchingSnapshot(
        catalog_version=catalog_version,
        products=tuple(compiled_products),
        by_id=compiled_by_id,
        head_phrases=tuple(sorted(global_head_phrases.values(), key=lambda row: (-len(row.token_terms), row.normalized))),
        head_terms=frozenset(global_head_terms),
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


GENERIC_SHORTLIST_TERMS = frozenset(
    {
        "alarm",
        "camera",
        "charger",
        "controller",
        "display",
        "hub",
        "monitor",
        "player",
        "receiver",
        "station",
        "switch",
        "terminal",
    }
)


def _best_shortlist_phrase_score(
    phrases: tuple[CompiledAlias, ...] | tuple[CompiledPhrase, ...],
    text_terms: set[str],
) -> tuple[int, str | None]:
    best_score = 0
    best_reason: str | None = None

    for phrase in phrases:
        if not phrase.token_terms or not phrase.token_terms <= text_terms:
            continue
        token_count = len(phrase.token_terms)
        if isinstance(phrase, CompiledAlias):
            score = 10 + token_count * 8 + max(phrase.field_bonus, 0) + max(phrase.specificity_bonus, 0)
            if token_count == 1 and phrase.generic_terms:
                score -= 14
            elif token_count == 1:
                score -= 2
            best_field = phrase.field.replace("_", " ")
            reason = f"{best_field} phrase '{phrase.raw}'"
        else:
            score = 8 + token_count * 7
            if token_count == 1:
                score -= 3
            reason = f"phrase '{phrase.raw}'"
        if score > best_score:
            best_score = score
            best_reason = reason

    return best_score, best_reason


def _route_anchor_shortlist_score(compiled: CompiledProductMatcher, signal_traits: set[str]) -> tuple[int, str | None]:
    route_anchor = compiled.route_anchor or ""
    if not route_anchor:
        return 0, None
    connected_traits = {"account", "app_control", "authentication", "bluetooth", "cloud", "ota", "radio", "wifi", "zigbee"}
    wired_traits = {"display", "ethernet", "hdmi_interface", "office_peripheral", "usb_hub_function", "wired_networking"}

    if route_anchor.endswith("_connected") and connected_traits & signal_traits:
        return 6, f"route anchor {route_anchor} fits connected traits"
    if route_anchor.endswith("_core") and wired_traits & signal_traits:
        return 4, f"route anchor {route_anchor} fits local or wired traits"
    return 0, None


def _shortlist_score_details(
    compiled: CompiledProductMatcher,
    *,
    text_terms: set[str],
    signal_traits: set[str],
) -> tuple[int, list[str]]:
    reasons: list[str] = []
    score = 0

    alias_score, alias_reason = _best_shortlist_phrase_score(compiled.aliases, text_terms)
    if alias_score:
        score += alias_score
        if alias_reason:
            reasons.append(alias_reason)

    family_score, family_reason = _best_shortlist_phrase_score(compiled.family_keywords, text_terms)
    if family_score:
        score += family_score
        if family_reason:
            reasons.append("family " + family_reason)

    required_hits = sum(1 for phrase in compiled.required_clues if phrase.token_terms and phrase.token_terms <= text_terms)
    preferred_hits = sum(1 for phrase in compiled.preferred_clues if phrase.token_terms and phrase.token_terms <= text_terms)
    exclude_hits = sum(1 for phrase in compiled.exclude_clues if phrase.token_terms and phrase.token_terms <= text_terms)
    if required_hits:
        score += required_hits * 14
        reasons.append(f"required clues x{required_hits}")
    if preferred_hits:
        score += preferred_hits * 9
        reasons.append(f"preferred clues x{preferred_hits}")
    if exclude_hits:
        score -= exclude_hits * 12
        reasons.append(f"exclude clues x{exclude_hits}")

    generic_alias_term_hits = len({term for alias in compiled.aliases if alias.token_terms <= text_terms for term in alias.generic_terms})
    if generic_alias_term_hits:
        score -= generic_alias_term_hits * 5
        reasons.append(f"generic alias terms x{generic_alias_term_hits}")

    trait_hits = len(compiled.shortlist_traits & signal_traits)
    if trait_hits:
        score += min(trait_hits, 5) * 3
        reasons.append(f"trait priors x{min(trait_hits, 5)}")

    required_family_traits = compiled.family_required_traits
    if required_family_traits and required_family_traits <= signal_traits:
        score += 8
        reasons.append("family required traits fit")

    route_score, route_reason = _route_anchor_shortlist_score(compiled, signal_traits)
    if route_score:
        score += route_score
        if route_reason:
            reasons.append(route_reason)

    return score, reasons


@overload
def _shortlist_product_matchers_v2(
    text: str,
    signal_traits: set[str],
    *,
    include_reasons: Literal[False] = False,
) -> tuple[tuple[CompiledProductMatcher, ...], dict[str, int]]: ...


@overload
def _shortlist_product_matchers_v2(
    text: str,
    signal_traits: set[str],
    *,
    include_reasons: Literal[True],
) -> tuple[tuple[CompiledProductMatcher, ...], dict[str, int], dict[str, tuple[str, ...]]]: ...


def _shortlist_product_matchers_v2(
    text: str,
    signal_traits: set[str],
    *,
    include_reasons: bool = False,
) -> (
    tuple[tuple[CompiledProductMatcher, ...], dict[str, int]]
    | tuple[tuple[CompiledProductMatcher, ...], dict[str, int], dict[str, tuple[str, ...]]]
):
    snapshot = _product_matching_snapshot()
    text_terms = set(text.split())
    shortlist_scoring: dict[str, int] = {}
    shortlist_reasons: dict[str, tuple[str, ...]] = {}
    shortlisted: list[CompiledProductMatcher] = []

    for compiled in snapshot.products:
        cheap_score, reasons = _shortlist_score_details(
            compiled,
            text_terms=text_terms,
            signal_traits=signal_traits,
        )
        if cheap_score <= 0:
            continue

        shortlist_scoring[compiled.id] = cheap_score
        shortlist_reasons[compiled.id] = tuple(reasons)
        shortlisted.append(compiled)

    if not shortlisted:
        fallback = tuple(snapshot.products)
        fallback_scores = {compiled.id: 0 for compiled in fallback}
        fallback_reasons: dict[str, tuple[str, ...]] = {compiled.id: () for compiled in fallback}
        if include_reasons:
            return fallback, fallback_scores, fallback_reasons
        return fallback, fallback_scores

    shortlisted.sort(
        key=lambda compiled: (
            -shortlist_scoring[compiled.id],
            -len([alias for alias in compiled.aliases if alias.token_terms and alias.token_terms <= text_terms]),
            -len([phrase for phrase in compiled.family_keywords if phrase.token_terms and phrase.token_terms <= text_terms]),
            -len(compiled.shortlist_traits & signal_traits),
            compiled.id,
        )
    )

    max_candidates = 120
    if len(shortlisted) > max_candidates:
        shortlisted = shortlisted[:max_candidates]
        shortlist_scoring = {compiled.id: shortlist_scoring[compiled.id] for compiled in shortlisted}
        shortlist_reasons = {compiled.id: shortlist_reasons[compiled.id] for compiled in shortlisted}

    if include_reasons:
        return tuple(shortlisted), shortlist_scoring, shortlist_reasons
    return tuple(shortlisted), shortlist_scoring


def _compute_product_trait_buckets(product: ProductRowLike) -> tuple[set[str], set[str]]:
    from .trait_inference_helpers import _expand_related_traits

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
    _compile_phrase.cache_clear()
    _compile_alias.cache_clear()


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
