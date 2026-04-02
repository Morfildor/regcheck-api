from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any, Literal, TypedDict

from app.domain.catalog_types import StandardCatalogRow
from app.domain.models import ConfidenceLevel, FactBasis, StandardAuditItem

StandardItemType = Literal["standard", "review"]
ProductHitType = Literal["not_product_gated", "primary_product", "alternate_product", "primary_genre"]
StandardAuditOutcome = Literal["selected", "review", "rejected"]
MatchBasis = Literal["product", "alternate_product", "preferred_product", "genre", "traits"]


class ApplicableItems(TypedDict):
    standards: list[StandardCatalogRow]
    review_items: list[StandardCatalogRow]
    rejections: list[dict[str, object]]
    audit: dict[str, list[dict[str, object]]]


@dataclass(frozen=True, slots=True)
class RejectionEntry:
    code: str | None
    title: str | None
    reason: str

    def as_dict(self) -> dict[str, object]:
        return {
            "code": self.code,
            "title": self.title,
            "reason": self.reason,
        }


@dataclass(frozen=True, slots=True)
class ItemsAudit:
    selected: list[StandardAuditItem] = field(default_factory=list)
    review: list[StandardAuditItem] = field(default_factory=list)
    rejected: list[StandardAuditItem] = field(default_factory=list)

    def as_dict(self) -> dict[str, list[dict[str, object]]]:
        return {
            "selected": [item.model_dump() for item in self.selected],
            "review": [item.model_dump() for item in self.review],
            "rejected": [item.model_dump() for item in self.rejected],
        }


@dataclass(frozen=True, slots=True)
class SelectionContext:
    scope_route: str = "generic"
    scope_reasons: list[str] = field(default_factory=list)
    text: str = ""
    context_tags: set[str] = field(default_factory=set)
    primary_route_family: str | None = None
    primary_standard_code: str | None = None
    primary_route_reason: str = ""
    route_confidence: ConfidenceLevel = "low"
    has_external_psu: bool = False
    has_portable_battery: bool = False
    has_laser_source: bool = False
    has_photobiological_source: bool = False
    has_body_contact: bool = False
    has_personal_or_health_data: bool = False
    has_connected_radio: bool = False
    has_medical_boundary: bool = False
    prefer_specific_red_emf: bool = False
    prefer_62233: bool = False
    prefer_62311: bool = False

    @classmethod
    def from_mapping(cls, raw: Mapping[str, Any] | SelectionContext | None) -> SelectionContext:
        if isinstance(raw, SelectionContext):
            return raw
        if raw is None:
            return cls()
        scope_reasons = [
            item for item in raw.get("scope_reasons", [])
            if isinstance(item, str) and item
        ]
        context_tags = {
            item for item in raw.get("context_tags", [])
            if isinstance(item, str) and item
        }
        confidence = raw.get("route_confidence")
        route_confidence: ConfidenceLevel = "low"
        if confidence in {"low", "medium", "high"}:
            route_confidence = confidence
        return cls(
            scope_route=str(raw.get("scope_route") or "generic"),
            scope_reasons=scope_reasons,
            text=str(raw.get("text") or ""),
            context_tags=context_tags,
            primary_route_family=str(raw.get("primary_route_family") or "") or None,
            primary_standard_code=str(raw.get("primary_standard_code") or "") or None,
            primary_route_reason=str(raw.get("primary_route_reason") or ""),
            route_confidence=route_confidence,
            has_external_psu=bool(raw.get("has_external_psu")),
            has_portable_battery=bool(raw.get("has_portable_battery")),
            has_laser_source=bool(raw.get("has_laser_source")),
            has_photobiological_source=bool(raw.get("has_photobiological_source")),
            has_body_contact=bool(raw.get("has_body_contact")),
            has_personal_or_health_data=bool(raw.get("has_personal_or_health_data")),
            has_connected_radio=bool(raw.get("has_connected_radio")),
            has_medical_boundary=bool(raw.get("has_medical_boundary")),
            prefer_specific_red_emf=bool(raw.get("prefer_specific_red_emf")),
            prefer_62233=bool(raw.get("prefer_62233")),
            prefer_62311=bool(raw.get("prefer_62311")),
        )

    def as_mapping(self) -> dict[str, object]:
        return {
            "scope_route": self.scope_route,
            "scope_reasons": list(self.scope_reasons),
            "text": self.text,
            "context_tags": set(self.context_tags),
            "primary_route_family": self.primary_route_family,
            "primary_standard_code": self.primary_standard_code,
            "primary_route_reason": self.primary_route_reason,
            "route_confidence": self.route_confidence,
            "has_external_psu": self.has_external_psu,
            "has_portable_battery": self.has_portable_battery,
            "has_laser_source": self.has_laser_source,
            "has_photobiological_source": self.has_photobiological_source,
            "has_body_contact": self.has_body_contact,
            "has_personal_or_health_data": self.has_personal_or_health_data,
            "has_connected_radio": self.has_connected_radio,
            "has_medical_boundary": self.has_medical_boundary,
            "prefer_specific_red_emf": self.prefer_specific_red_emf,
            "prefer_62233": self.prefer_62233,
            "prefer_62311": self.prefer_62311,
        }


__all__ = [
    "ApplicableItems",
    "FactBasis",
    "ItemsAudit",
    "MatchBasis",
    "ProductHitType",
    "RejectionEntry",
    "SelectionContext",
    "StandardAuditOutcome",
    "StandardItemType",
]
