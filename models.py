from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

Status = Literal["PASS", "WARN", "FAIL", "INFO"]
RiskLevel = Literal["LOW", "MEDIUM", "HIGH", "CRITICAL"]
LegislationBucket = Literal["ce", "non_ce", "framework", "future", "informational"]
TimingStatus = Literal["current", "future", "legacy", "informational"]
ConfidenceLevel = Literal["low", "medium", "high"]
ContradictionSeverity = Literal["none", "low", "medium", "high"]
FactBasis = Literal["confirmed", "mixed", "inferred"]
ProductMatchStage = Literal["family", "subtype", "ambiguous"]
TraitEvidenceState = Literal["text_explicit", "text_inferred", "product_core", "product_default", "engine_derived"]
StandardAuditOutcome = Literal["selected", "review", "rejected"]
KnownFactSource = Literal["parsed", "derived"]


class ProductInput(BaseModel):
    model_config = ConfigDict(extra="ignore")

    description: str = Field(min_length=1, max_length=4000)
    category: str = Field(default="", max_length=250)
    directives: list[str] = Field(default_factory=list, max_length=25)
    depth: Literal["quick", "standard", "deep"] = "standard"

    @field_validator("description")
    @classmethod
    def validate_description(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("description must not be blank")
        return cleaned

    @field_validator("category")
    @classmethod
    def validate_category(cls, value: str) -> str:
        return value.strip()

    @field_validator("directives")
    @classmethod
    def validate_directives(cls, value: list[str]) -> list[str]:
        cleaned: list[str] = []
        seen: set[str] = set()
        for item in value:
            if not isinstance(item, str):
                continue
            normalized = item.strip()
            if not normalized or normalized in seen:
                continue
            seen.add(normalized)
            cleaned.append(normalized)
        return cleaned


class ErrorInfo(BaseModel):
    code: str
    message: str
    request_id: str | None = None


class ErrorResponse(BaseModel):
    ok: bool = False
    error: ErrorInfo


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
    family: str | None = None
    subtype: str | None = None
    family_score: int = 0
    subtype_score: int = 0
    score: int = 0
    confidence: ConfidenceLevel = "medium"
    reasons: list[str] = Field(default_factory=list)
    positive_clues: list[str] = Field(default_factory=list)
    negative_clues: list[str] = Field(default_factory=list)
    likely_standards: list[str] = Field(default_factory=list)


class TraitEvidenceItem(BaseModel):
    trait: str
    state: TraitEvidenceState
    fact_basis: FactBasis = "confirmed"
    confirmed: bool = False
    evidence: list[str] = Field(default_factory=list)


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
    evidence_strength: FactBasis = "confirmed"
    is_forced: bool = False
    jurisdiction: str = "EU"
    applicability_state: str = "current"
    applicability_hint: str | None = None


class StandardItem(BaseModel):
    code: str
    title: str
    directive: str
    directives: list[str] = Field(default_factory=list)
    legislation_key: str | None = None
    category: str
    confidence: ConfidenceLevel = "medium"
    item_type: Literal["standard", "review"] = "standard"
    match_basis: Literal["product", "alternate_product", "preferred_product", "genre", "traits"] = "traits"
    fact_basis: FactBasis = "confirmed"
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
    applies_if_genres: list[str] = Field(default_factory=list)
    exclude_if_genres: list[str] = Field(default_factory=list)
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
    keyword_hits: list[str] = Field(default_factory=list)
    selection_group: str | None = None
    selection_priority: int = 0
    required_fact_basis: FactBasis = "inferred"
    jurisdiction: str = "EU"
    applicability_state: str = "current"
    applicability_hint: str | None = None


class StandardSectionItem(StandardItem):
    triggered_by_directive: str
    triggered_by_label: str
    triggered_by_title: str


class StandardAuditItem(BaseModel):
    code: str
    title: str
    outcome: StandardAuditOutcome
    score: int = 0
    confidence: ConfidenceLevel = "medium"
    fact_basis: FactBasis = "confirmed"
    selection_group: str | None = None
    selection_priority: int = 0
    keyword_hits: list[str] = Field(default_factory=list)
    reason: str | None = None


class ProductMatchAudit(BaseModel):
    engine_version: str
    normalized_text: str
    retrieval_basis: list[str] = Field(default_factory=list)
    alias_hits: list[str] = Field(default_factory=list)
    family_keyword_hits: list[str] = Field(default_factory=list)
    clue_hits: list[str] = Field(default_factory=list)
    negations: list[str] = Field(default_factory=list)
    ambiguity_reason: str | None = None


class StandardMatchAudit(BaseModel):
    engine_version: str
    context_tags: list[str] = Field(default_factory=list)
    selected: list[StandardAuditItem] = Field(default_factory=list)
    review: list[StandardAuditItem] = Field(default_factory=list)
    rejected: list[StandardAuditItem] = Field(default_factory=list)


class MissingInformationItem(BaseModel):
    key: str
    message: str
    importance: Literal["high", "medium", "low"] = "medium"
    examples: list[str] = Field(default_factory=list)
    related_traits: list[str] = Field(default_factory=list)
    route_impact: list[str] = Field(default_factory=list)
    next_actions: list[str] = Field(default_factory=list)


class KnownFactItem(BaseModel):
    key: str
    label: str
    value: str
    source: KnownFactSource = "parsed"
    related_traits: list[str] = Field(default_factory=list)


class RiskReason(BaseModel):
    key: str
    scope: Literal["overall", "current", "future"] = "overall"
    level: RiskLevel = "MEDIUM"
    title: str
    detail: str


class RiskBucketSummary(BaseModel):
    level: RiskLevel = "LOW"
    reasons: list[RiskReason] = Field(default_factory=list)


class RiskSummary(BaseModel):
    overall: RiskBucketSummary = Field(default_factory=RiskBucketSummary)
    current: RiskBucketSummary = Field(default_factory=RiskBucketSummary)
    future: RiskBucketSummary = Field(default_factory=RiskBucketSummary)


class HeroSummary(BaseModel):
    title: str = ""
    subtitle: str = ""
    primary_regimes: list[str] = Field(default_factory=list)
    confidence: ConfidenceLevel = "low"
    depth: Literal["quick", "standard", "deep"] = "standard"


class ConfidencePanel(BaseModel):
    confidence: ConfidenceLevel = "low"
    classification_is_ambiguous: bool = True
    classification_confidence_below_threshold: bool = True
    matched_products: list[str] = Field(default_factory=list)
    product_family: str | None = None
    product_genres: list[str] = Field(default_factory=list)
    product_subtype: str | None = None
    product_match_stage: ProductMatchStage = "ambiguous"


class InputGapsPanel(BaseModel):
    items: list[MissingInformationItem] = Field(default_factory=list)
    next_actions: list[str] = Field(default_factory=list)
    high_importance_count: int = 0


class QuickAddItem(BaseModel):
    label: str
    text: str


class RouteContext(BaseModel):
    scope_route: str = "generic"
    scope_reasons: list[str] = Field(default_factory=list)
    context_tags: list[str] = Field(default_factory=list)
    known_fact_keys: list[str] = Field(default_factory=list)
    jurisdiction: str = "EU"
    route_trigger_reasons: list[str] = Field(default_factory=list)
    primary_route_family: str | None = None
    primary_route_standard_code: str | None = None
    primary_route_reason: str = ""
    overlay_routes: list[str] = Field(default_factory=list)
    route_confidence: ConfidenceLevel = "low"


class ShadowDiffItem(BaseModel):
    kind: Literal["trait", "standard"]
    key: str
    has_evidence: bool = False


class AnalysisAudit(BaseModel):
    allowed_directives: list[str] = Field(default_factory=list)
    matched_products: list[str] = Field(default_factory=list)
    routing_matched_products: list[str] = Field(default_factory=list)
    preferred_standards: list[str] = Field(default_factory=list)
    product_genres: list[str] = Field(default_factory=list)
    product_family: str | None = None
    product_subtype: str | None = None
    product_match_stage: ProductMatchStage = "ambiguous"
    classification_is_ambiguous: bool = True
    classification_confidence_below_threshold: bool = True
    depth: Literal["quick", "standard", "deep"] = "standard"
    engine_version: str = "2.0"
    normalized_description: str = ""
    context_tags: list[str] = Field(default_factory=list)
    shadow_diff: list[ShadowDiffItem] = Field(default_factory=list)


class AnalysisStats(BaseModel):
    legislation_count: int = 0
    current_legislation_count: int = 0
    future_legislation_count: int = 0
    standards_count: int = 0
    review_items_count: int = 0
    current_review_items_count: int = 0
    future_review_items_count: int = 0
    harmonized_standards_count: int = 0
    state_of_the_art_standards_count: int = 0
    product_gated_standards_count: int = 0
    ambiguity_flag_count: int = 0
    missing_information_count: int = 0


class KnowledgeBaseMeta(BaseModel):
    traits: int = 0
    genres: int = 0
    products: int = 0
    legislations: int = 0
    standards: int = 0
    harmonized_standards: int = 0
    state_of_the_art_standards: int = 0
    review_items: int = 0
    product_gated_standards: int = 0
    version: str | None = None


class LegislationSection(BaseModel):
    key: str
    title: str
    count: int = 0
    items: list[LegislationItem] = Field(default_factory=list)


class StandardSection(BaseModel):
    key: str
    directive_key: str
    directive_label: str
    directive_title: str
    title: str
    count: int = 0
    items: list[StandardSectionItem] = Field(default_factory=list)


class AnalysisResult(BaseModel):
    product_summary: str
    overall_risk: RiskLevel
    current_compliance_risk: RiskLevel = "LOW"
    future_watchlist_risk: RiskLevel = "LOW"
    summary: str

    analyzed_description: str = ""
    normalized_description: str = ""

    product_type: str | None = None
    product_family: str | None = None
    product_family_confidence: ConfidenceLevel = "low"
    product_subtype: str | None = None
    product_subtype_confidence: ConfidenceLevel = "low"
    product_match_stage: ProductMatchStage = "ambiguous"
    product_match_confidence: ConfidenceLevel = "low"
    classification_is_ambiguous: bool = True
    classification_confidence_below_threshold: bool = True
    classification_summary: str = ""
    primary_uncertainties: list[str] = Field(default_factory=list)
    route_trigger_reasons: list[str] = Field(default_factory=list)
    triggered_routes: list[str] = Field(default_factory=list)
    primary_route_standard_code: str | None = None
    primary_route_reason: str = ""
    overlay_routes: list[str] = Field(default_factory=list)
    route_confidence: ConfidenceLevel = "low"
    product_candidates: list[ProductCandidate] = Field(default_factory=list)
    functional_classes: list[str] = Field(default_factory=list)
    confirmed_functional_classes: list[str] = Field(default_factory=list)

    explicit_traits: list[str] = Field(default_factory=list)
    confirmed_traits: list[str] = Field(default_factory=list)
    inferred_traits: list[str] = Field(default_factory=list)
    assumptions_or_inferred_traits: list[str] = Field(default_factory=list)
    all_traits: list[str] = Field(default_factory=list)

    directives: list[str] = Field(default_factory=list)
    forced_directives: list[str] = Field(default_factory=list)
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
    warnings: list[str] = Field(default_factory=list)
    degraded_mode: bool = False
    degraded_reasons: list[str] = Field(default_factory=list)
    stats: AnalysisStats = Field(default_factory=AnalysisStats)
    knowledge_base_meta: KnowledgeBaseMeta = Field(default_factory=KnowledgeBaseMeta)
    analysis_audit: AnalysisAudit = Field(default_factory=AnalysisAudit)
    api_version: str = "1.0"
    engine_version: str = "2.0"
    catalog_version: str | None = None
    trait_evidence: list[TraitEvidenceItem] = Field(default_factory=list)
    product_match_audit: ProductMatchAudit = Field(
        default_factory=lambda: ProductMatchAudit(engine_version="", normalized_text="")
    )
    standard_match_audit: StandardMatchAudit = Field(
        default_factory=lambda: StandardMatchAudit(engine_version="")
    )

    standard_sections: list[StandardSection] = Field(default_factory=list)
    standards_by_directive: list[StandardSection] = Field(default_factory=list)
    legislation_sections: list[LegislationSection] = Field(default_factory=list)
    risk_reasons: list[RiskReason] = Field(default_factory=list)
    risk_summary: RiskSummary = Field(default_factory=RiskSummary)
    hero_summary: HeroSummary = Field(default_factory=HeroSummary)
    confidence_panel: ConfidencePanel = Field(default_factory=ConfidencePanel)
    input_gaps_panel: InputGapsPanel = Field(default_factory=InputGapsPanel)
    top_actions: list[str] = Field(default_factory=list)
    next_actions: list[str] = Field(default_factory=list)
    current_path: list[str] = Field(default_factory=list)
    future_watchlist: list[str] = Field(default_factory=list)
    suggested_questions: list[str] = Field(default_factory=list)
    suggested_quick_adds: list[QuickAddItem] = Field(default_factory=list)
    known_facts: list[KnownFactItem] = Field(default_factory=list)
    known_fact_keys: list[str] = Field(default_factory=list)
    route_context: RouteContext = Field(default_factory=RouteContext)
    primary_jurisdiction: str = "EU"
    supported_jurisdictions: list[str] = Field(default_factory=lambda: ["EU"])

    findings: list[Finding] = Field(default_factory=list)
