from __future__ import annotations

from dataclasses import dataclass, field

from app.domain.engine_models import MissingInformationItem, StandardItem, StandardSection
from app.services.standards_engine.contracts import ItemsAudit, RejectionEntry, SelectionContext


@dataclass(slots=True)
class StandardsPolicyDecision:
    eligibility_codes: list[str] = field(default_factory=list)
    fact_basis_review_codes: list[str] = field(default_factory=list)
    route_family_review_codes: list[str] = field(default_factory=list)
    selection_group_review_codes: list[str] = field(default_factory=list)
    rejection_reasons: list[str] = field(default_factory=list)


@dataclass(slots=True)
class StandardsSelectionResult:
    context: SelectionContext
    standard_items: list[StandardItem]
    review_items: list[StandardItem]
    current_review_items: list[StandardItem]
    missing_items: list[MissingInformationItem]
    standard_sections: list[StandardSection]
    items_audit: ItemsAudit
    rejections: list[RejectionEntry]
    policy: StandardsPolicyDecision = field(default_factory=StandardsPolicyDecision)
