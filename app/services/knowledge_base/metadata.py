from __future__ import annotations

from collections.abc import Sequence
import hashlib
import os
from typing import Any

from app.core.settings import get_settings
from app.domain.catalog_types import (
    GenreCatalogRow,
    LegislationCatalogRow,
    ProductCatalogRow,
    StandardCatalogRow,
    TraitCatalogRow,
)
from app.domain.models import KnowledgeBaseMeta, MetadataOptionsResponse, MetadataStandardsResponse

from .paths import ALL_DATA_FILES, KnowledgeBaseError, _resolve_data_path


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
        path = _resolve_data_path(filename, required=False)
        digest.update(filename.encode("utf-8"))
        digest.update(b"\0")
        if path is None:
            digest.update(b"<missing>")
            digest.update(b"\0")
            continue
        try:
            digest.update(path.read_bytes())
        except OSError as exc:
            raise KnowledgeBaseError(f"Could not read knowledge-base file: {path}") from exc
        digest.update(b"\0")
    return f"sha256:{digest.hexdigest()[:12]}"


def _kb_meta(counts: dict[str, int], standards: Sequence[StandardCatalogRow]) -> dict[str, Any]:
    return KnowledgeBaseMeta(
        **counts,
        harmonized_standards=sum(1 for row in standards if row.get("harmonization_status") == "harmonized"),
        state_of_the_art_standards=sum(1 for row in standards if row.get("harmonization_status") == "state_of_the_art"),
        review_items=sum(1 for row in standards if row.get("item_type") == "review"),
        product_gated_standards=sum(1 for row in standards if row.get("applies_if_products") or row.get("applies_if_genres")),
        version=_catalog_version(),
    ).model_dump()


def _build_metadata_options_payload(
    traits: Sequence[TraitCatalogRow],
    genres: Sequence[GenreCatalogRow],
    products: Sequence[ProductCatalogRow],
    legislations: Sequence[LegislationCatalogRow],
    meta: dict[str, Any],
) -> dict[str, Any]:
    return MetadataOptionsResponse(
        traits=[{"id": row["id"], "label": row["label"], "description": row["description"]} for row in traits],
        genres=[
            {
                "id": row["id"],
                "label": row["label"],
                "keywords": row.get("keywords", []),
                "traits": row.get("traits", []),
                "default_traits": row.get("default_traits", []),
                "functional_classes": row.get("functional_classes", []),
                "likely_standards": row.get("likely_standards", []),
            }
            for row in genres
        ],
        products=[
            {
                "id": row["id"],
                "label": row["label"],
                "product_family": row.get("product_family"),
                "product_subfamily": row.get("product_subfamily"),
                "genres": row.get("genres", []),
                "aliases": row.get("aliases", []),
                "family_keywords": row.get("family_keywords", []),
                "genre_keywords": row.get("genre_keywords", []),
                "required_clues": row.get("required_clues", []),
                "preferred_clues": row.get("preferred_clues", []),
                "exclude_clues": row.get("exclude_clues", []),
                "confusable_with": row.get("confusable_with", []),
                "functional_classes": row.get("functional_classes", []),
                "genre_functional_classes": row.get("genre_functional_classes", []),
                "family_traits": row.get("family_traits", []),
                "genre_traits": row.get("genre_traits", []),
                "genre_default_traits": row.get("genre_default_traits", []),
                "subtype_traits": row.get("subtype_traits", []),
                "core_traits": row.get("core_traits", []),
                "default_traits": row.get("default_traits", []),
                "implied_traits": row.get("implied_traits", []),
                "likely_standards": row.get("likely_standards", []),
                "genre_likely_standards": row.get("genre_likely_standards", []),
            }
            for row in products
        ],
        legislations=[
            {
                "code": row["code"],
                "title": row["title"],
                "directive_key": row["directive_key"],
                "family": row["family"],
                "priority": row.get("priority", "conditional"),
                "bucket": row.get("bucket", "non_ce"),
            }
            for row in legislations
        ],
        knowledge_base_meta=meta,
    ).model_dump()


def _standard_directives(row: dict[str, Any]) -> list[str]:
    directives = row.get("directives")
    if isinstance(directives, list):
        values = [item for item in directives if isinstance(item, str) and item]
        if values:
            return values

    legislation_key = row.get("legislation_key")
    if isinstance(legislation_key, str) and legislation_key:
        return [legislation_key]

    return ["OTHER"]


def _build_metadata_standards_payload(standards: Sequence[StandardCatalogRow], meta: dict[str, Any]) -> dict[str, Any]:
    return MetadataStandardsResponse(
        knowledge_base_meta=meta,
        standards=[
            {
                "directive": _standard_directives(row)[0],
                "directives": _standard_directives(row),
                "code": row["code"],
                "title": row["title"],
                "category": row["category"],
                "legislation_key": row.get("legislation_key"),
                "item_type": row.get("item_type", "standard"),
                "standard_family": row.get("standard_family"),
                "harmonization_status": row.get("harmonization_status", "unknown"),
                "is_harmonized": row.get("is_harmonized"),
                "harmonized_under": row.get("harmonized_under"),
                "harmonized_reference": row.get("harmonized_reference"),
                "version": row.get("version"),
                "dated_version": row.get("dated_version"),
                "supersedes": row.get("supersedes"),
                "test_focus": row.get("test_focus", []),
                "evidence_hint": row.get("evidence_hint", []),
                "keywords": row.get("keywords", []),
                "selection_group": row.get("selection_group"),
                "selection_priority": row.get("selection_priority", 0),
                "required_fact_basis": row.get("required_fact_basis", "inferred"),
                "applies_if_products": row.get("applies_if_products", []),
                "applies_if_genres": row.get("applies_if_genres", []),
                "applies_if_all": row.get("applies_if_all", []),
                "applies_if_any": row.get("applies_if_any", []),
                "exclude_if_genres": row.get("exclude_if_genres", []),
            }
            for row in standards
        ],
    ).model_dump()


def _build_classifier_runtime_snapshot(
    products: Sequence[ProductCatalogRow],
    traits: Sequence[TraitCatalogRow],
    catalog_version: str | None,
) -> Any:
    from app.services.classifier import build_product_matching_snapshot

    return build_product_matching_snapshot(
        products=list(products),
        trait_ids={row["id"] for row in traits},
        catalog_version=catalog_version,
    )


__all__ = [
    "_build_classifier_runtime_snapshot",
    "_build_metadata_options_payload",
    "_build_metadata_standards_payload",
    "_catalog_version",
    "_kb_meta",
    "_standard_directives",
]
