from __future__ import annotations

from dataclasses import dataclass, field

from app.domain.engine_models import ConfidenceLevel


@dataclass(frozen=True, slots=True)
class NormalizedClassifierEvidence:
    product_type: str | None = None
    product_match_stage: str = "ambiguous"
    product_match_confidence: ConfidenceLevel = "low"
    route_traits: set[str] = field(default_factory=set)
    confirmed_traits: set[str] = field(default_factory=set)
    matched_products: set[str] = field(default_factory=set)
    product_genres: set[str] = field(default_factory=set)
    preferred_standard_codes: set[str] = field(default_factory=set)


@dataclass(frozen=True, slots=True)
class RoutePolicyDecision:
    primary_route_family: str | None = None
    directive_overlays: list[str] = field(default_factory=list)
    route_confidence: ConfidenceLevel = "low"
    preferred_standard_codes: list[str] = field(default_factory=list)
    preferred_standard_families: list[str] = field(default_factory=list)
    primary_standard_code: str | None = None
    primary_directive: str | None = None
    rationale: list[str] = field(default_factory=list)
