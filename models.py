from __future__ import annotations

from typing import Literal
from pydantic import BaseModel, Field

Status = Literal["PASS", "WARN", "FAIL", "INFO"]
RiskLevel = Literal["LOW", "MEDIUM", "HIGH", "CRITICAL"]
LegislationBucket = Literal["ce", "non_ce", "framework", "future", "informational"]
TimingStatus = Literal["current", "future", "legacy", "informational"]
ConfidenceLevel = Literal["low", "medium", "high"]
ContradictionSeverity = Literal["none", "low", "medium", "high"]


class ProductInput(BaseModel):
    description: str
    category: str = ""
    directives: list[str] = Field(default_factory=list)
    depth: Literal["quick", "standard", "deep"] = "standard"


class Finding(BaseModel):
    directive: str
    article: str
    status: Status
    finding: str
    action: str | None = None


class ProductCandidate(BaseModel):
    id: str
    label: str
    matched_alias: str | None = None
    score: int = 0
    confidence: ConfidenceLevel = "medium"
    reasons: list[str] = Field(default_factory=list)
    likely_standards: list[str] = Field(default_factory=list)


class LegislationItem(BaseModel):
    code: str
    title: str
    family: str
    legal_form: str = "Other"
    priority: Literal["core", "product_specific", "conditional", "informational"] = "conditional"
    applicability: Literal["applicable", "conditional", "not_applicable"] = "conditional"
    directive_key: str = "OTHER"
    bucket: LegislationBucket = "non_ce"
    timing_status: TimingStatus = "current"
    reason: str | None = None
    triggers: list[str] = Field(default_factory=list)
    doc_impacts: list[str] = Field(default_factory=list)
    notes: str | None = None
    applicable_from: str | None = None
    applicable_until: str | None = None
    replaced_by: str | None = None


class StandardItem(BaseModel):
    code: str
    title: str
    directive: str
    legislation_key: str | None = None
    category: str
    confidence: ConfidenceLevel = "medium"
    item_type: Literal["standard", "review"] = "standard"
    match_basis: Literal["product", "alternate_product", "traits"] = "traits"
    score: int = 0
    reason: str | None = None
    notes: str | None = None
    regime_bucket: LegislationBucket | None = None
    timing_status: TimingStatus = "current"
    matched_traits_all: list[str] = Field(default_factory=list)
    matched_traits_any: list[str] = Field(default_factory=list)
    missing_required_traits: list[str] = Field(default_factory=list)
    excluded_by_traits: list[str] = Field(default_factory=list)
    applies_if_products: list[str] = Field(default_factory=list)
    exclude_if_products: list[str] = Field(default_factory=list)
    product_match_type: str | None = None
    standard_family: str | None = None
    is_harmonized: bool | None = None
    harmonized_under: str | None = None
    harmonization_status: Literal["harmonized", "state_of_the_art", "review", "unknown"] = "unknown"
    harmonized_reference: str | None = None
    version: str | None = None
    dated_version: str | None = None
    supersedes: str | None = None
    test_focus: list[str] = Field(default_factory=list)
    evidence_hint: list[str] = Field(default_factory=list)
    keywords: list[str] = Field(default_factory=list)


class MissingInformationItem(BaseModel):
    key: str
    message: str
    importance: Literal["high", "medium", "low"] = "medium"
    examples: list[str] = Field(default_factory=list)
    related_traits: list[str] = Field(default_factory=list)


class AnalysisStats(BaseModel):
    legislation_count: int = 0
    current_legislation_count: int = 0
    future_legislation_count: int = 0
    standards_count: int = 0
    review_items_count: int = 0
    harmonized_standards_count: int = 0
    state_of_the_art_standards_count: int = 0
    product_gated_standards_count: int = 0
    ambiguity_flag_count: int = 0
    missing_information_count: int = 0


class KnowledgeBaseMeta(BaseModel):
    traits: int = 0
    products: int = 0
    legislations: int = 0
    standards: int = 0
    harmonized_standards: int = 0
    state_of_the_art_standards: int = 0
    review_items: int = 0
    product_gated_standards: int = 0
    version: str | None = None


class AnalysisResult(BaseModel):
    product_summary: str
    overall_risk: RiskLevel
    summary: str

    product_type: str | None = None
    product_match_confidence: ConfidenceLevel = "low"
    product_candidates: list[ProductCandidate] = Field(default_factory=list)
    functional_classes: list[str] = Field(default_factory=list)

    explicit_traits: list[str] = Field(default_factory=list)
    inferred_traits: list[str] = Field(default_factory=list)
    all_traits: list[str] = Field(default_factory=list)

    directives: list[str] = Field(default_factory=list)
    legislations: list[LegislationItem] = Field(default_factory=list)
    ce_legislations: list[LegislationItem] = Field(default_factory=list)
    non_ce_obligations: list[LegislationItem] = Field(default_factory=list)
    framework_regimes: list[LegislationItem] = Field(default_factory=list)
    future_regimes: list[LegislationItem] = Field(default_factory=list)
    informational_items: list[LegislationItem] = Field(default_factory=list)

    standards: list[StandardItem] = Field(default_factory=list)
    review_items: list[StandardItem] = Field(default_factory=list)
    missing_information: list[str] = Field(default_factory=list)
    missing_information_items: list[MissingInformationItem] = Field(default_factory=list)
    contradictions: list[str] = Field(default_factory=list)
    contradiction_severity: ContradictionSeverity = "none"
    diagnostics: list[str] = Field(default_factory=list)
    stats: AnalysisStats = Field(default_factory=AnalysisStats)
    knowledge_base_meta: KnowledgeBaseMeta | None = None

    standard_sections: list[dict] = Field(default_factory=list)
    legislation_sections: list[dict] = Field(default_factory=list)

    findings: list[Finding] = Field(default_factory=list)
