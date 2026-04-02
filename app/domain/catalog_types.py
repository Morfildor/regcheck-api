from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

FactBasis = Literal["confirmed", "mixed", "inferred"]
HarmonizationStatus = Literal["harmonized", "state_of_the_art", "review", "unknown"]
LegislationBucket = Literal["ce", "non_ce", "framework", "future", "informational"]
LegislationPriority = Literal["core", "product_specific", "conditional", "informational"]
LegislationApplicability = Literal["applicable", "conditional", "not_applicable"]
StandardItemType = Literal["standard", "review"]


class MappingModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="allow")

    def __getitem__(self, key: str) -> Any:
        data = self._mapping_view()
        if key not in data:
            raise KeyError(key)
        return data[key]

    def get(self, key: str, default: Any = None) -> Any:
        return self._mapping_view().get(key, default)

    def items(self) -> list[tuple[str, Any]]:
        return list(self._mapping_view().items())

    def as_legacy_dict(self) -> dict[str, Any]:
        return self.model_dump()

    def _mapping_view(self) -> dict[str, Any]:
        data = {field_name: getattr(self, field_name) for field_name in self.__class__.model_fields}
        if self.model_extra:
            data.update(self.model_extra)
        return data


class LikelyStandardRef(MappingModel):
    ref: str
    kind: str = "unspecified"


class TraitCatalogRow(MappingModel):
    id: str
    label: str
    description: str


class GenreCatalogRow(MappingModel):
    id: str
    label: str
    keywords: list[str] = Field(default_factory=list)
    traits: list[str] = Field(default_factory=list)
    default_traits: list[str] = Field(default_factory=list)
    functional_classes: list[str] = Field(default_factory=list)
    likely_standards: list[str] = Field(default_factory=list)
    likely_standard_refs: list[LikelyStandardRef] = Field(default_factory=list)


class ProductCatalogRow(MappingModel):
    id: str
    label: str
    product_family: str
    product_subfamily: str
    route_family: str | None = None
    primary_standard_code: str | None = None
    supporting_standard_codes: list[str] = Field(default_factory=list)
    genres: list[str] = Field(default_factory=list)
    aliases: list[str] = Field(default_factory=list)
    family_keywords: list[str] = Field(default_factory=list)
    genre_keywords: list[str] = Field(default_factory=list)
    required_clues: list[str] = Field(default_factory=list)
    preferred_clues: list[str] = Field(default_factory=list)
    exclude_clues: list[str] = Field(default_factory=list)
    confusable_with: list[str] = Field(default_factory=list)
    functional_classes: list[str] = Field(default_factory=list)
    genre_functional_classes: list[str] = Field(default_factory=list)
    family_traits: list[str] = Field(default_factory=list)
    subtype_traits: list[str] = Field(default_factory=list)
    genre_traits: list[str] = Field(default_factory=list)
    genre_default_traits: list[str] = Field(default_factory=list)
    core_traits: list[str] = Field(default_factory=list)
    default_traits: list[str] = Field(default_factory=list)
    implied_traits: list[str] = Field(default_factory=list)
    likely_standards: list[str] = Field(default_factory=list)
    genre_likely_standards: list[str] = Field(default_factory=list)
    likely_standard_refs: list[LikelyStandardRef] = Field(default_factory=list)


class LegislationCatalogRow(MappingModel):
    code: str
    title: str
    family: str
    directive_key: str
    legal_form: str = "Other"
    priority: LegislationPriority = "conditional"
    applicability: LegislationApplicability = "conditional"
    bucket: LegislationBucket = "non_ce"
    triggers: list[str] = Field(default_factory=list)
    doc_impacts: list[str] = Field(default_factory=list)
    notes: str | None = None
    applicable_from: str | None = None
    applicable_until: str | None = None
    replaced_by: str | None = None
    jurisdiction: str = "EU"
    all_of_traits: list[str] = Field(default_factory=list)
    any_of_traits: list[str] = Field(default_factory=list)
    none_of_traits: list[str] = Field(default_factory=list)
    all_of_functional_classes: list[str] = Field(default_factory=list)
    any_of_functional_classes: list[str] = Field(default_factory=list)
    none_of_functional_classes: list[str] = Field(default_factory=list)
    any_of_product_types: list[str] = Field(default_factory=list)
    exclude_product_types: list[str] = Field(default_factory=list)
    any_of_genres: list[str] = Field(default_factory=list)
    exclude_genres: list[str] = Field(default_factory=list)


class StandardCatalogRow(MappingModel):
    code: str
    title: str
    category: str
    directives: list[str] = Field(default_factory=list)
    legislation_key: str | None = None
    item_type: StandardItemType = "standard"
    is_harmonized: bool | None = None
    harmonized_under: str | None = None
    harmonized_reference: str | None = None
    version: str | None = None
    dated_version: str | None = None
    supersedes: str | None = None
    harmonization_status: HarmonizationStatus = "unknown"
    standard_family: str | None = None
    test_focus: list[str] = Field(default_factory=list)
    evidence_hint: list[str] = Field(default_factory=list)
    keywords: list[str] = Field(default_factory=list)
    selection_group: str | None = None
    selection_priority: int = 0
    required_fact_basis: FactBasis = "inferred"
    applies_if_all: list[str] = Field(default_factory=list)
    applies_if_any: list[str] = Field(default_factory=list)
    exclude_if: list[str] = Field(default_factory=list)
    applies_if_products: list[str] = Field(default_factory=list)
    exclude_if_products: list[str] = Field(default_factory=list)
    applies_if_genres: list[str] = Field(default_factory=list)
    exclude_if_genres: list[str] = Field(default_factory=list)
