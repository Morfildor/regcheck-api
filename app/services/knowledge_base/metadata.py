from __future__ import annotations

from collections.abc import Sequence
import hashlib
import os
from typing import TYPE_CHECKING

from app.core.settings import get_settings
from app.domain.catalog_types import (
    GenreCatalogRow,
    LegislationCatalogRow,
    ProductCatalogRow,
    StandardCatalogRow,
    TraitCatalogRow,
)
from app.domain.models import (
    KnowledgeBaseMeta,
    MetadataGenreOption,
    MetadataLegislationOption,
    MetadataOptionsResponse,
    MetadataProductOption,
    MetadataStandardOption,
    MetadataStandardsResponse,
    MetadataTraitOption,
)

from .paths import ALL_DATA_FILES, KnowledgeBaseError, _resolve_catalog_sources

if TYPE_CHECKING:
    from app.services.classifier.matching import ProductMatchingSnapshot
    from app.services.classifier.signal_config import ClassifierSignalSnapshot


def _catalog_version() -> str:
    settings = get_settings()
    explicit_version = os.getenv(settings.catalog_version_env, "").strip()
    if explicit_version:
        return explicit_version

    build_metadata = os.getenv(settings.build_metadata_env, "").strip()
    if build_metadata:
        return f"build:{build_metadata}"

    digest = hashlib.sha256()
    for filename in ALL_DATA_FILES:
        digest.update(filename.encode("utf-8"))
        digest.update(b"\0")
        bundle = _resolve_catalog_sources(filename, required=False)
        if bundle is None or not bundle.paths:
            digest.update(b"<missing>")
            digest.update(b"\0")
            continue
        for path in bundle.paths:
            try:
                digest.update(path.name.encode("utf-8"))
                digest.update(b"\0")
                digest.update(path.read_bytes())
            except OSError as exc:
                raise KnowledgeBaseError(f"Could not read knowledge-base file: {path}") from exc
            digest.update(b"\0")
    return f"sha256:{digest.hexdigest()[:12]}"


def _kb_meta(counts: dict[str, int], standards: Sequence[StandardCatalogRow]) -> KnowledgeBaseMeta:
    return KnowledgeBaseMeta(
        **counts,
        harmonized_standards=sum(1 for row in standards if row.harmonization_status == "harmonized"),
        state_of_the_art_standards=sum(1 for row in standards if row.harmonization_status == "state_of_the_art"),
        review_items=sum(1 for row in standards if row.item_type == "review"),
        product_gated_standards=sum(1 for row in standards if row.applies_if_products or row.applies_if_genres),
        version=_catalog_version(),
    )


def _trait_option(row: TraitCatalogRow) -> MetadataTraitOption:
    return MetadataTraitOption(id=row.id, label=row.label, description=row.description)


def _genre_option(row: GenreCatalogRow) -> MetadataGenreOption:
    return MetadataGenreOption(
        id=row.id,
        label=row.label,
        keywords=list(row.keywords),
        traits=list(row.traits),
        default_traits=list(row.default_traits),
        functional_classes=list(row.functional_classes),
        likely_standards=list(row.likely_standards),
    )


def _product_option(row: ProductCatalogRow) -> MetadataProductOption:
    return MetadataProductOption(
        id=row.id,
        label=row.label,
        product_family=row.product_family,
        product_subfamily=row.product_subfamily,
        genres=list(row.genres),
        aliases=list(row.aliases),
        family_keywords=list(row.family_keywords),
        genre_keywords=list(row.genre_keywords),
        required_clues=list(row.required_clues),
        preferred_clues=list(row.preferred_clues),
        exclude_clues=list(row.exclude_clues),
        confusable_with=list(row.confusable_with),
        functional_classes=list(row.functional_classes),
        genre_functional_classes=list(row.genre_functional_classes),
        family_traits=list(row.family_traits),
        genre_traits=list(row.genre_traits),
        genre_default_traits=list(row.genre_default_traits),
        subtype_traits=list(row.subtype_traits),
        core_traits=list(row.core_traits),
        default_traits=list(row.default_traits),
        implied_traits=list(row.implied_traits),
        likely_standards=list(row.likely_standards),
        genre_likely_standards=list(row.genre_likely_standards),
    )


def _legislation_option(row: LegislationCatalogRow) -> MetadataLegislationOption:
    return MetadataLegislationOption(
        code=row.code,
        title=row.title,
        directive_key=row.directive_key,
        family=row.family,
        priority=row.priority,
        bucket=row.bucket,
    )


def _build_metadata_options_payload(
    traits: Sequence[TraitCatalogRow],
    genres: Sequence[GenreCatalogRow],
    products: Sequence[ProductCatalogRow],
    legislations: Sequence[LegislationCatalogRow],
    meta: KnowledgeBaseMeta,
) -> MetadataOptionsResponse:
    return MetadataOptionsResponse(
        traits=[_trait_option(row) for row in traits],
        genres=[_genre_option(row) for row in genres],
        products=[_product_option(row) for row in products],
        legislations=[_legislation_option(row) for row in legislations],
        knowledge_base_meta=meta,
    )


def _standard_directives(row: StandardCatalogRow) -> list[str]:
    if row.directives:
        return list(row.directives)
    if row.legislation_key:
        return [row.legislation_key]
    return ["OTHER"]


def _standard_option(row: StandardCatalogRow) -> MetadataStandardOption:
    directives = _standard_directives(row)
    return MetadataStandardOption(
        directive=directives[0],
        directives=directives,
        code=row.code,
        title=row.title,
        category=row.category,
        legislation_key=row.legislation_key,
        item_type=row.item_type,
        standard_family=row.standard_family,
        harmonization_status=row.harmonization_status,
        is_harmonized=row.is_harmonized,
        harmonized_under=row.harmonized_under,
        harmonized_reference=row.harmonized_reference,
        version=row.version,
        dated_version=row.dated_version,
        supersedes=row.supersedes,
        test_focus=list(row.test_focus),
        evidence_hint=list(row.evidence_hint),
        keywords=list(row.keywords),
        selection_group=row.selection_group,
        selection_priority=row.selection_priority,
        required_fact_basis=row.required_fact_basis,
        applies_if_products=list(row.applies_if_products),
        applies_if_genres=list(row.applies_if_genres),
        applies_if_all=list(row.applies_if_all),
        applies_if_any=list(row.applies_if_any),
        exclude_if_genres=list(row.exclude_if_genres),
    )


def _build_metadata_standards_payload(
    standards: Sequence[StandardCatalogRow],
    meta: KnowledgeBaseMeta,
) -> MetadataStandardsResponse:
    return MetadataStandardsResponse(
        knowledge_base_meta=meta,
        standards=[_standard_option(row) for row in standards],
    )


def _build_classifier_runtime_snapshot(
    products: Sequence[ProductCatalogRow],
    traits: Sequence[TraitCatalogRow],
    catalog_version: str | None,
) -> ProductMatchingSnapshot:
    from app.services.classifier import build_product_matching_snapshot

    return build_product_matching_snapshot(
        products=products,
        trait_ids={row["id"] for row in traits},
        catalog_version=catalog_version,
    )


def _build_classifier_signal_snapshot(
    catalog_version: str | None,
    trait_ids: set[str],
) -> ClassifierSignalSnapshot:
    from app.services.classifier.signal_config import build_classifier_signal_snapshot

    return build_classifier_signal_snapshot(catalog_version=catalog_version, trait_ids=trait_ids)


__all__ = [
    "_build_classifier_runtime_snapshot",
    "_build_classifier_signal_snapshot",
    "_build_metadata_options_payload",
    "_build_metadata_standards_payload",
    "_catalog_version",
    "_kb_meta",
    "_standard_directives",
]
