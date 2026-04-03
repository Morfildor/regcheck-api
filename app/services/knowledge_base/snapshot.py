from __future__ import annotations

from dataclasses import dataclass, field
import logging
from threading import RLock
from time import perf_counter
from typing import TYPE_CHECKING, Any

from app.core.settings import reset_settings_cache
from app.domain.catalog_types import (
    GenreCatalogRow,
    LegislationCatalogRow,
    ProductCatalogRow,
    StandardCatalogRow,
    TraitCatalogRow,
)
from app.domain.models import KnowledgeBaseMeta, MetadataOptionsResponse, MetadataStandardsResponse

from .enricher import (
    _enrich_legislations,
    _enrich_products,
    _enrich_standards,
    _post_validate_product_standard_links,
)
from .loader import (
    _as_genre_rows,
    _as_legislation_rows,
    _as_product_rows,
    _as_standard_rows,
    _as_trait_rows,
    _legacy_rows,
    _load_genres_catalog,
    _load_legislations_catalog,
    _load_products_catalog,
    _load_standards_catalog,
    _load_traits_catalog,
)
from .metadata import (
    _build_classifier_signal_snapshot,
    _build_classifier_runtime_snapshot,
    _build_metadata_options_payload,
    _build_metadata_standards_payload,
    _kb_meta,
)
from .paths import _resolved_data_paths_for_logging, clear_resolved_data_paths_cache
from .taxonomy import reset_taxonomy_cache

if TYPE_CHECKING:
    from app.services.classifier.matching import ProductMatchingSnapshot
    from app.services.classifier.signal_config import ClassifierSignalSnapshot


@dataclass(frozen=True, slots=True)
class KnowledgeBaseWarmupResult:
    counts: dict[str, int]
    meta: dict[str, Any]
    duration_ms: int


@dataclass(frozen=True, slots=True)
class KnowledgeBaseSnapshot:
    traits: tuple[TraitCatalogRow, ...]
    genres: tuple[GenreCatalogRow, ...]
    products: tuple[ProductCatalogRow, ...]
    legislations: tuple[LegislationCatalogRow, ...]
    standards: tuple[StandardCatalogRow, ...]
    counts: dict[str, int]
    meta: KnowledgeBaseMeta
    metadata_payloads: dict[str, MetadataOptionsResponse | MetadataStandardsResponse] = field(default_factory=dict)
    classifier_runtime: ProductMatchingSnapshot | None = None
    classifier_signal_runtime: ClassifierSignalSnapshot | None = None
    legacy_payloads: dict[str, list[dict[str, Any]]] = field(default_factory=dict)
    meta_payload: dict[str, Any] = field(default_factory=dict)
    load_all_payload: dict[str, Any] = field(default_factory=dict)


logger = logging.getLogger(__name__)

_SNAPSHOT_LOCK = RLock()
_ACTIVE_SNAPSHOT: KnowledgeBaseSnapshot | None = None


def build_knowledge_base_snapshot(*, refresh_paths: bool = False) -> KnowledgeBaseSnapshot:
    if refresh_paths:
        clear_resolved_data_paths_cache()

    raw_traits = _load_traits_catalog()
    traits = _as_trait_rows(raw_traits)
    trait_ids = {row["id"] for row in traits}

    raw_genres = _load_genres_catalog(trait_ids)
    genres = _as_genre_rows(raw_genres)
    genre_ids = {row["id"] for row in genres}

    raw_products = _enrich_products(_load_products_catalog(trait_ids, genre_ids), list(genres))
    products = _as_product_rows(raw_products)
    product_ids = {row["id"] for row in products}

    raw_legislations = _enrich_legislations(_load_legislations_catalog(product_ids, trait_ids, genre_ids), list(products))
    legislations = _as_legislation_rows(raw_legislations)
    legislation_keys = {row["directive_key"] for row in legislations} | {
        "CRA",
        "GDPR",
        "AI_Act",
        "ESPR",
        "OTHER",
        "GPSR",
        "WEEE",
        "TOY",
        "UAS",
        "MDR",
    }

    raw_standards = _enrich_standards(
        _load_standards_catalog(product_ids, trait_ids, legislation_keys, genre_ids),
        list(products),
    )
    standards = _as_standard_rows(raw_standards)
    _post_validate_product_standard_links(products, genres, standards)

    counts = {
        "traits": len(traits),
        "genres": len(genres),
        "products": len(products),
        "legislations": len(legislations),
        "standards": len(standards),
    }

    meta = _kb_meta(counts, standards)
    legacy_payloads = {
        "traits": _legacy_rows(traits),
        "genres": _legacy_rows(genres),
        "products": _legacy_rows(products),
        "legislations": _legacy_rows(legislations),
        "standards": _legacy_rows(standards),
    }
    meta_payload = meta.model_dump()
    load_all_payload = {
        **legacy_payloads,
        "counts": counts,
        "meta": meta_payload,
    }

    return KnowledgeBaseSnapshot(
        traits=traits,
        genres=genres,
        products=products,
        legislations=legislations,
        standards=standards,
        counts=counts,
        meta=meta,
        metadata_payloads={
            "options": _build_metadata_options_payload(traits, genres, products, legislations, meta),
            "standards": _build_metadata_standards_payload(standards, meta),
        },
        classifier_runtime=_build_classifier_runtime_snapshot(products, traits, meta.version),
        classifier_signal_runtime=_build_classifier_signal_snapshot(meta.version, trait_ids),
        legacy_payloads=legacy_payloads,
        meta_payload=meta_payload,
        load_all_payload=load_all_payload,
    )


def activate_knowledge_base_snapshot(snapshot: KnowledgeBaseSnapshot) -> None:
    global _ACTIVE_SNAPSHOT
    with _SNAPSHOT_LOCK:
        _ACTIVE_SNAPSHOT = snapshot


def get_knowledge_base_snapshot() -> KnowledgeBaseSnapshot:
    global _ACTIVE_SNAPSHOT
    snapshot = _ACTIVE_SNAPSHOT
    if snapshot is not None:
        return snapshot

    with _SNAPSHOT_LOCK:
        snapshot = _ACTIVE_SNAPSHOT
        if snapshot is None:
            snapshot = build_knowledge_base_snapshot()
            _ACTIVE_SNAPSHOT = snapshot
        return snapshot


def load_all() -> dict[str, Any]:
    return get_knowledge_base_snapshot().load_all_payload


def load_traits() -> list[dict[str, Any]]:
    return get_knowledge_base_snapshot().legacy_payloads["traits"]


def load_genres() -> list[dict[str, Any]]:
    return get_knowledge_base_snapshot().legacy_payloads["genres"]


def load_products() -> list[dict[str, Any]]:
    return get_knowledge_base_snapshot().legacy_payloads["products"]


def load_legislations() -> list[dict[str, Any]]:
    return get_knowledge_base_snapshot().legacy_payloads["legislations"]


def load_standards() -> list[dict[str, Any]]:
    return get_knowledge_base_snapshot().legacy_payloads["standards"]


def load_meta() -> dict[str, Any]:
    return get_knowledge_base_snapshot().meta_payload


def load_metadata_payload(name: str) -> dict[str, Any]:
    payload = get_knowledge_base_snapshot().metadata_payloads.get(name)
    return payload.model_dump() if payload is not None else {}


def warmup_knowledge_base(*, refresh_paths: bool = False) -> KnowledgeBaseWarmupResult:
    started = perf_counter()
    snapshot = build_knowledge_base_snapshot(refresh_paths=refresh_paths)
    activate_knowledge_base_snapshot(snapshot)
    duration_ms = int((perf_counter() - started) * 1000)
    logger.info(
        "knowledge_base_warmup files=%s version=%s duration_ms=%s",
        _resolved_data_paths_for_logging(),
        snapshot.meta.version,
        duration_ms,
    )
    return KnowledgeBaseWarmupResult(
        counts=dict(snapshot.counts),
        meta=snapshot.meta_payload,
        duration_ms=duration_ms,
    )


def reset_cache() -> None:
    global _ACTIVE_SNAPSHOT
    _ACTIVE_SNAPSHOT = None
    clear_resolved_data_paths_cache()
    reset_taxonomy_cache()
    reset_settings_cache()
    from app.services.classifier import reset_classifier_cache

    reset_classifier_cache()


__all__ = [
    "KnowledgeBaseSnapshot",
    "KnowledgeBaseWarmupResult",
    "activate_knowledge_base_snapshot",
    "build_knowledge_base_snapshot",
    "get_knowledge_base_snapshot",
    "load_all",
    "load_genres",
    "load_legislations",
    "load_meta",
    "load_metadata_payload",
    "load_products",
    "load_standards",
    "load_traits",
    "reset_cache",
    "warmup_knowledge_base",
]
