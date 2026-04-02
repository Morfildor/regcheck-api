from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any, Literal, TypeAlias, cast

from app.domain.models import ConfidenceLevel, ContradictionSeverity, ProductCandidate, ProductMatchStage

TraitEvidenceBucket = Literal["text_explicit", "text_inferred", "product_core", "product_default", "engine_derived"]
NormalizedTraitStateMap: TypeAlias = dict[TraitEvidenceBucket, dict[str, list[str]]]


def _string_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, str) and item]


def _confidence_level(value: object, default: ConfidenceLevel = "low") -> ConfidenceLevel:
    if value in {"low", "medium", "high"}:
        return cast(ConfidenceLevel, value)
    return default


def _contradiction_severity(value: object) -> ContradictionSeverity:
    if value in {"low", "medium", "high"}:
        return cast(ContradictionSeverity, value)
    return "none"


def _product_match_stage(value: object) -> ProductMatchStage:
    if value in {"family", "subtype"}:
        return cast(ProductMatchStage, value)
    return "ambiguous"


@dataclass(frozen=True, slots=True)
class ClassifierTraitsSnapshot:
    product_type: str | None = None
    product_family: str | None = None
    product_family_confidence: ConfidenceLevel = "low"
    product_subtype: str | None = None
    product_subtype_confidence: ConfidenceLevel = "low"
    product_match_stage: ProductMatchStage = "ambiguous"
    product_match_confidence: ConfidenceLevel = "low"
    matched_products: list[str] = field(default_factory=list)
    routing_matched_products: list[str] = field(default_factory=list)
    confirmed_products: list[str] = field(default_factory=list)
    product_genres: list[str] = field(default_factory=list)
    preferred_standard_codes: list[str] = field(default_factory=list)
    product_candidates: list[ProductCandidate] = field(default_factory=list)
    functional_classes: list[str] = field(default_factory=list)
    confirmed_functional_classes: list[str] = field(default_factory=list)
    explicit_traits: list[str] = field(default_factory=list)
    confirmed_traits: list[str] = field(default_factory=list)
    inferred_traits: list[str] = field(default_factory=list)
    all_traits: list[str] = field(default_factory=list)
    contradictions: list[str] = field(default_factory=list)
    contradiction_severity: ContradictionSeverity = "none"
    diagnostics: list[str] = field(default_factory=list)
    trait_state_map: NormalizedTraitStateMap = field(
        default_factory=lambda: {
            "text_explicit": {},
            "text_inferred": {},
            "product_core": {},
            "product_default": {},
            "engine_derived": {},
        }
    )
    product_match_audit_payload: dict[str, object] | None = None

    @classmethod
    def from_mapping(cls, raw: Mapping[str, Any]) -> ClassifierTraitsSnapshot:
        product_candidates: list[ProductCandidate] = []
        for item in raw.get("product_candidates", []):
            if not isinstance(item, Mapping):
                continue
            product_candidates.append(ProductCandidate.model_validate(dict(item)))

        trait_state_map: NormalizedTraitStateMap = {
            "text_explicit": {},
            "text_inferred": {},
            "product_core": {},
            "product_default": {},
            "engine_derived": {},
        }
        raw_state_map = raw.get("trait_state_map")
        if isinstance(raw_state_map, Mapping):
            for state in trait_state_map:
                state_value = raw_state_map.get(state)
                if not isinstance(state_value, Mapping):
                    continue
                for trait, evidence in state_value.items():
                    if not isinstance(trait, str):
                        continue
                    if isinstance(evidence, list):
                        trait_state_map[state][trait] = [item for item in evidence if isinstance(item, str)]
                    elif isinstance(evidence, str):
                        trait_state_map[state][trait] = [evidence]

        product_match_audit_payload: dict[str, object] | None = None
        audit_payload = raw.get("product_match_audit") or raw.get("audit")
        if isinstance(audit_payload, Mapping):
            product_match_audit_payload = dict(audit_payload)

        return cls(
            product_type=str(raw.get("product_type") or "") or None,
            product_family=str(raw.get("product_family") or "") or None,
            product_family_confidence=_confidence_level(raw.get("product_family_confidence"), default="low"),
            product_subtype=str(raw.get("product_subtype") or "") or None,
            product_subtype_confidence=_confidence_level(raw.get("product_subtype_confidence"), default="low"),
            product_match_stage=_product_match_stage(raw.get("product_match_stage")),
            product_match_confidence=_confidence_level(raw.get("product_match_confidence"), default="low"),
            matched_products=_string_list(raw.get("matched_products")),
            routing_matched_products=_string_list(raw.get("routing_matched_products")),
            confirmed_products=_string_list(raw.get("confirmed_products")),
            product_genres=_string_list(raw.get("product_genres")),
            preferred_standard_codes=_string_list(raw.get("preferred_standard_codes")),
            product_candidates=product_candidates,
            functional_classes=_string_list(raw.get("functional_classes")),
            confirmed_functional_classes=_string_list(raw.get("confirmed_functional_classes")),
            explicit_traits=_string_list(raw.get("explicit_traits")),
            confirmed_traits=_string_list(raw.get("confirmed_traits")),
            inferred_traits=_string_list(raw.get("inferred_traits")),
            all_traits=_string_list(raw.get("all_traits")),
            contradictions=_string_list(raw.get("contradictions")),
            contradiction_severity=_contradiction_severity(raw.get("contradiction_severity")),
            diagnostics=_string_list(raw.get("diagnostics")),
            trait_state_map=trait_state_map,
            product_match_audit_payload=product_match_audit_payload,
        )

    def to_legacy_dict(self) -> dict[str, object]:
        return {
            "product_type": self.product_type,
            "product_family": self.product_family,
            "product_family_confidence": self.product_family_confidence,
            "product_subtype": self.product_subtype,
            "product_subtype_confidence": self.product_subtype_confidence,
            "product_match_stage": self.product_match_stage,
            "product_match_confidence": self.product_match_confidence,
            "matched_products": list(self.matched_products),
            "routing_matched_products": list(self.routing_matched_products),
            "confirmed_products": list(self.confirmed_products),
            "product_genres": list(self.product_genres),
            "preferred_standard_codes": list(self.preferred_standard_codes),
            "product_candidates": [item.model_dump() for item in self.product_candidates],
            "functional_classes": list(self.functional_classes),
            "confirmed_functional_classes": list(self.confirmed_functional_classes),
            "explicit_traits": list(self.explicit_traits),
            "confirmed_traits": list(self.confirmed_traits),
            "inferred_traits": list(self.inferred_traits),
            "all_traits": list(self.all_traits),
            "contradictions": list(self.contradictions),
            "contradiction_severity": self.contradiction_severity,
            "diagnostics": list(self.diagnostics),
            "trait_state_map": {
                state: {trait: list(evidence) for trait, evidence in values.items()}
                for state, values in self.trait_state_map.items()
            },
            "product_match_audit": dict(self.product_match_audit_payload or {}),
        }


__all__ = [
    "ClassifierTraitsSnapshot",
    "NormalizedTraitStateMap",
    "TraitEvidenceBucket",
]
