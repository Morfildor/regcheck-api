from __future__ import annotations

from dataclasses import dataclass, field
from time import perf_counter
from typing import Literal

from app.domain.models import ConfidenceLevel, LegislationItem, LegislationSection, MissingInformationItem, ProductMatchStage, StandardItem, StandardSection

from .contracts import ClassifierTraitsSnapshot, NormalizedTraitStateMap
from app.services.standards_engine.contracts import ItemsAudit, RejectionEntry, SelectionContext

AnalysisDepth = Literal["quick", "standard", "deep"]


@dataclass(slots=True)
class RoutePlan:
    primary_route_family: str | None = None
    primary_standard_code: str | None = None
    supporting_standard_codes: list[str] = field(default_factory=list)
    primary_directive: str | None = None
    reason: str = ""
    confidence: ConfidenceLevel = "low"
    scope_route: str = "generic"


@dataclass(slots=True)
class PreparedAnalysis:
    depth: AnalysisDepth
    normalized_description: str
    traits_data: ClassifierTraitsSnapshot
    diagnostics: list[str]
    degraded_reasons: list[str]
    warnings: list[str]
    matched_products: set[str]
    routing_matched_products: set[str]
    product_genres: set[str]
    product_type: str | None
    product_match_stage: ProductMatchStage
    routing_product_type: str | None
    likely_standards: set[str]
    trait_set: set[str]
    route_traits: set[str]
    confirmed_traits: set[str]
    functional_classes: set[str]
    raw_state_map: NormalizedTraitStateMap
    route_plan: RoutePlan


@dataclass(slots=True)
class LegislationSelection:
    items: list[LegislationItem]
    sections: list[LegislationSection]
    detected_directives: list[str]
    forced_directives: list[str]
    allowed_directives: set[str]
    legislation_by_directive: dict[str, LegislationItem]


@dataclass(slots=True)
class StandardsSelection:
    context: SelectionContext
    standard_items: list[StandardItem]
    review_items: list[StandardItem]
    current_review_items: list[StandardItem]
    missing_items: list[MissingInformationItem]
    standard_sections: list[StandardSection]
    items_audit: ItemsAudit
    rejections: list[RejectionEntry]


@dataclass(slots=True)
class AnalysisTrace:
    request_id: str | None = None
    stage_timings_ms: dict[str, int] = field(default_factory=dict)

    def record_stage(self, stage: str, started_at: float) -> None:
        self.stage_timings_ms[stage] = int((perf_counter() - started_at) * 1000)


__all__ = [
    "AnalysisDepth",
    "AnalysisTrace",
    "LegislationSelection",
    "PreparedAnalysis",
    "RoutePlan",
    "StandardsSelection",
]
