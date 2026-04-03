from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.domain.catalog_types import ProductCatalogRow
from app.domain.models import ConfidenceLevel, ProductMatchStage


def _list(values: tuple[str, ...] | frozenset[str] | set[str] | list[str]) -> list[str]:
    if isinstance(values, list):
        return list(values)
    return list(values)


@dataclass(frozen=True, slots=True)
class AuditCandidate:
    id: str
    label: str
    family: str | None = None
    subtype: str | None = None
    score: int = 0
    confidence: ConfidenceLevel = "low"
    matched_alias: str | None = None
    positive_clues: tuple[str, ...] = ()
    negative_clues: tuple[str, ...] = ()
    family_keyword_hits: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "label": self.label,
            "family": self.family,
            "subtype": self.subtype,
            "score": self.score,
            "confidence": self.confidence,
            "matched_alias": self.matched_alias,
            "positive_clues": list(self.positive_clues),
            "negative_clues": list(self.negative_clues),
            "family_keyword_hits": list(self.family_keyword_hits),
        }


@dataclass(frozen=True, slots=True)
class SignalSuppression:
    source: str
    reason: str
    traits: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "source": self.source,
            "reason": self.reason,
            "traits": list(self.traits),
        }


@dataclass(frozen=True, slots=True)
class ProductImpliedTraitDecision:
    source: str
    accepted_traits: tuple[str, ...] = ()
    suppressed_traits: tuple[str, ...] = ()
    reason: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "source": self.source,
            "accepted_traits": list(self.accepted_traits),
            "suppressed_traits": list(self.suppressed_traits),
            "reason": self.reason,
        }


@dataclass(frozen=True, slots=True)
class RoleParseAudit:
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

    def to_dict(self) -> dict[str, Any]:
        return {
            "primary_product_phrase": self.primary_product_phrase,
            "primary_product_head": self.primary_product_head,
            "primary_head_candidates": list(self.primary_head_candidates),
            "competing_primary_heads": list(self.competing_primary_heads),
            "accessory_or_attachment": list(self.accessory_or_attachment),
            "target_device": list(self.target_device),
            "controlled_device": list(self.controlled_device),
            "charged_device": list(self.charged_device),
            "powered_device": list(self.powered_device),
            "host_device": list(self.host_device),
            "mounted_on_or_for": list(self.mounted_on_or_for),
            "integrated_feature": list(self.integrated_feature),
            "installation_context": list(self.installation_context),
            "cue_hits": list(self.cue_hits),
            "parse_notes": list(self.parse_notes),
            "primary_head_source": self.primary_head_source,
            "primary_is_accessory": self.primary_is_accessory,
            "primary_head_conflict": self.primary_head_conflict,
        }


@dataclass(frozen=True, slots=True)
class PublicProductCandidate:
    id: str
    label: str
    family: str | None = None
    subtype: str | None = None
    matched_alias: str | None = None
    family_score: int = 0
    subtype_score: int = 0
    score: int = 0
    confidence: ConfidenceLevel = "low"
    reasons: tuple[str, ...] = ()
    positive_clues: tuple[str, ...] = ()
    negative_clues: tuple[str, ...] = ()
    likely_standards: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "label": self.label,
            "family": self.family,
            "subtype": self.subtype,
            "matched_alias": self.matched_alias,
            "family_score": self.family_score,
            "subtype_score": self.subtype_score,
            "score": self.score,
            "confidence": self.confidence,
            "reasons": list(self.reasons),
            "positive_clues": list(self.positive_clues),
            "negative_clues": list(self.negative_clues),
            "likely_standards": list(self.likely_standards),
        }


@dataclass(frozen=True, slots=True)
class SubtypeCandidate:
    id: str
    label: str
    family: str
    subtype: str
    product: ProductCatalogRow
    genres: tuple[str, ...] = ()
    matched_alias: str | None = None
    matched_alias_field: str | None = None
    matched_alias_generic_terms: tuple[str, ...] = ()
    alias_hits: tuple[str, ...] = ()
    family_keyword_hits: tuple[str, ...] = ()
    positive_clues: tuple[str, ...] = ()
    negative_clues: tuple[str, ...] = ()
    decisive: bool = False
    score: int = 0
    direct_signal_count: int = 0
    reasons: tuple[str, ...] = ()
    core_traits: tuple[str, ...] = ()
    default_traits: tuple[str, ...] = ()
    family_traits: tuple[str, ...] = ()
    subtype_traits: tuple[str, ...] = ()
    functional_classes: tuple[str, ...] = ()
    likely_standards: tuple[str, ...] = ()
    confusable_with: tuple[str, ...] = ()
    route_anchor: str | None = None
    max_match_stage: str | None = None
    boundary_tags: tuple[str, ...] = ()
    head_phrases: tuple[str, ...] = ()
    head_terms: tuple[str, ...] = ()

    def to_audit_candidate(self, *, confidence: ConfidenceLevel) -> AuditCandidate:
        return AuditCandidate(
            id=self.id,
            label=self.label,
            family=self.family,
            subtype=self.subtype,
            score=self.score,
            confidence=confidence,
            matched_alias=self.matched_alias,
            positive_clues=self.positive_clues,
            negative_clues=self.negative_clues,
            family_keyword_hits=self.family_keyword_hits,
        )

    def to_public_candidate(self, *, confidence: ConfidenceLevel, family_score: int) -> PublicProductCandidate:
        return PublicProductCandidate(
            id=self.id,
            label=self.label,
            family=self.family,
            subtype=self.subtype,
            matched_alias=self.matched_alias,
            family_score=family_score,
            subtype_score=self.score,
            score=self.score,
            confidence=confidence,
            reasons=self.reasons,
            positive_clues=self.positive_clues,
            negative_clues=self.negative_clues,
            likely_standards=self.likely_standards,
        )


@dataclass(frozen=True, slots=True)
class FamilySeedCandidate:
    family: str
    representative: SubtypeCandidate
    score: int
    confidence: ConfidenceLevel = "low"

    @property
    def label(self) -> str:
        return self.representative.label

    @property
    def id(self) -> str:
        return self.representative.id

    @property
    def matched_alias(self) -> str | None:
        return self.representative.matched_alias

    @property
    def direct_signal_count(self) -> int:
        return self.representative.direct_signal_count

    def to_audit_candidate(self) -> AuditCandidate:
        return AuditCandidate(
            id=self.representative.id,
            label=self.representative.label,
            family=self.family,
            subtype=self.representative.subtype,
            score=self.score,
            confidence=self.confidence,
            matched_alias=self.representative.matched_alias,
            positive_clues=self.representative.positive_clues,
            negative_clues=self.representative.negative_clues,
            family_keyword_hits=self.representative.family_keyword_hits,
        )


@dataclass(slots=True)
class ClassifierMatchAudit:
    engine_version: str
    normalized_text: str
    normalized_text_summary: str = ""
    retrieval_basis: list[str] = field(default_factory=list)
    shortlist_basis: list[str] = field(default_factory=list)
    filtered_out: list[str] = field(default_factory=list)
    alias_hits: list[str] = field(default_factory=list)
    matched_aliases: list[str] = field(default_factory=list)
    family_keyword_hits: list[str] = field(default_factory=list)
    clue_hits: list[str] = field(default_factory=list)
    strongest_positive_clues: list[str] = field(default_factory=list)
    strongest_negative_clues: list[str] = field(default_factory=list)
    rerank_reasons: list[str] = field(default_factory=list)
    accessory_gate_reasons: list[str] = field(default_factory=list)
    generic_alias_penalties: list[str] = field(default_factory=list)
    negations: list[str] = field(default_factory=list)
    negation_suppressions: list[SignalSuppression] = field(default_factory=list)
    product_implied_traits: list[ProductImpliedTraitDecision] = field(default_factory=list)
    top_family_candidates: list[AuditCandidate] = field(default_factory=list)
    top_subtype_candidates: list[AuditCandidate] = field(default_factory=list)
    role_parse: RoleParseAudit | None = None
    final_match_stage: ProductMatchStage = "ambiguous"
    final_match_reason: str | None = None
    ambiguity_reason: str | None = None
    family_level_limiter: str | None = None
    confidence_limiter: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "engine_version": self.engine_version,
            "normalized_text": self.normalized_text,
            "normalized_text_summary": self.normalized_text_summary or self.normalized_text,
            "retrieval_basis": list(self.retrieval_basis),
            "shortlist_basis": list(self.shortlist_basis),
            "filtered_out": list(self.filtered_out),
            "alias_hits": list(self.alias_hits),
            "matched_aliases": list(self.matched_aliases or self.alias_hits),
            "family_keyword_hits": list(self.family_keyword_hits),
            "clue_hits": list(self.clue_hits),
            "strongest_positive_clues": list(self.strongest_positive_clues),
            "strongest_negative_clues": list(self.strongest_negative_clues),
            "rerank_reasons": list(self.rerank_reasons),
            "accessory_gate_reasons": list(self.accessory_gate_reasons),
            "generic_alias_penalties": list(self.generic_alias_penalties),
            "negations": list(self.negations),
            "negation_suppressions": [item.to_dict() for item in self.negation_suppressions],
            "product_implied_traits": [item.to_dict() for item in self.product_implied_traits],
            "top_family_candidates": [item.to_dict() for item in self.top_family_candidates],
            "top_subtype_candidates": [item.to_dict() for item in self.top_subtype_candidates],
            "role_parse": self.role_parse.to_dict() if self.role_parse is not None else {},
            "final_match_stage": self.final_match_stage,
            "final_match_reason": self.final_match_reason,
            "ambiguity_reason": self.ambiguity_reason,
            "family_level_limiter": self.family_level_limiter,
            "confidence_limiter": self.confidence_limiter,
        }


@dataclass(slots=True)
class ClassifierMatchOutcome:
    product_family: str | None
    product_family_confidence: ConfidenceLevel = "low"
    product_subtype: str | None = None
    product_subtype_confidence: ConfidenceLevel = "low"
    product_match_stage: ProductMatchStage = "ambiguous"
    product_type: str | None = None
    product_match_confidence: ConfidenceLevel = "low"
    product_candidates: list[PublicProductCandidate] = field(default_factory=list)
    matched_products: list[str] = field(default_factory=list)
    routing_matched_products: list[str] = field(default_factory=list)
    confirmed_products: list[str] = field(default_factory=list)
    product_core_traits: set[str] = field(default_factory=set)
    product_default_traits: set[str] = field(default_factory=set)
    product_genres: set[str] = field(default_factory=set)
    preferred_standard_codes: list[str] = field(default_factory=list)
    functional_classes: set[str] = field(default_factory=set)
    confirmed_functional_classes: set[str] = field(default_factory=set)
    diagnostics: list[str] = field(default_factory=list)
    contradictions: list[str] = field(default_factory=list)
    audit: ClassifierMatchAudit = field(default_factory=lambda: ClassifierMatchAudit(engine_version="", normalized_text=""))
    family_seed_candidates: list[FamilySeedCandidate] = field(default_factory=list)
    subtype_candidates: list[SubtypeCandidate] = field(default_factory=list)

    def clear_weak_guess(self, reason: str) -> None:
        self.product_family = None
        self.product_family_confidence = "low"
        self.product_subtype = None
        self.product_subtype_confidence = "low"
        self.product_type = None
        self.product_match_confidence = "low"
        self.product_candidates = []
        self.matched_products = []
        self.routing_matched_products = []
        self.confirmed_products = []
        self.product_core_traits = set()
        self.product_default_traits = set()
        self.product_genres = set()
        self.preferred_standard_codes = []
        self.functional_classes = set()
        self.confirmed_functional_classes = set()
        self.audit.final_match_reason = reason

    def to_dict(self) -> dict[str, Any]:
        return {
            "product_family": self.product_family,
            "product_family_confidence": self.product_family_confidence,
            "product_subtype": self.product_subtype,
            "product_subtype_confidence": self.product_subtype_confidence,
            "product_match_stage": self.product_match_stage,
            "product_type": self.product_type,
            "product_match_confidence": self.product_match_confidence,
            "product_candidates": [item.to_dict() for item in self.product_candidates],
            "matched_products": list(self.matched_products),
            "routing_matched_products": list(self.routing_matched_products),
            "confirmed_products": list(self.confirmed_products),
            "product_core_traits": set(self.product_core_traits),
            "product_default_traits": set(self.product_default_traits),
            "product_genres": set(self.product_genres),
            "preferred_standard_codes": list(self.preferred_standard_codes),
            "functional_classes": set(self.functional_classes),
            "confirmed_functional_classes": set(self.confirmed_functional_classes),
            "diagnostics": list(self.diagnostics),
            "contradictions": list(self.contradictions),
            "audit": self.audit.to_dict(),
        }


__all__ = [
    "AuditCandidate",
    "ClassifierMatchAudit",
    "ClassifierMatchOutcome",
    "FamilySeedCandidate",
    "ProductImpliedTraitDecision",
    "PublicProductCandidate",
    "SignalSuppression",
    "SubtypeCandidate",
]
