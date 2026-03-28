from __future__ import annotations

from collections.abc import Sequence
from typing import Any

import yaml
from pydantic import ValidationError

from app.domain.catalog_types import (
    GenreCatalogRow,
    LegislationCatalogRow,
    ProductCatalogRow,
    StandardCatalogRow,
    TraitCatalogRow,
)

from .paths import KnowledgeBaseError, _resolve_data_path
from .validator import (
    _materialize_likely_standard_refs,
    _validate_genres,
    _validate_legislations,
    _validate_products,
    _validate_standards,
    _validate_traits,
)


def _require_list(parent: dict[str, Any], key: str, filename: str) -> list[Any]:
    value = parent.get(key)
    if not isinstance(value, list):
        raise KnowledgeBaseError(f"{filename} must contain a top-level '{key}' list.")
    return value


def _optional_list(parent: dict[str, Any], key: str) -> list[Any]:
    value = parent.get(key)
    if value is None:
        return []
    if not isinstance(value, list):
        raise KnowledgeBaseError(f"Optional key '{key}' must be a list when present.")
    return value

def _load_yaml_raw(filename: str, *, required: bool = True) -> dict[str, Any]:
    path = _resolve_data_path(filename, required=required)
    if path is None:
        return {}

    try:
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
    except yaml.YAMLError as exc:
        raise KnowledgeBaseError(f"Invalid YAML in {path.name}: {exc}") from exc
    except OSError as exc:
        raise KnowledgeBaseError(f"Could not read knowledge-base file: {path}") from exc

    if data is None:
        return {}
    if not isinstance(data, dict):
        raise KnowledgeBaseError(f"{path.name} must contain a top-level mapping.")
    return data


def _as_trait_rows(rows: list[dict[str, Any]]) -> tuple[TraitCatalogRow, ...]:
    try:
        return tuple(TraitCatalogRow.model_validate(row) for row in rows)
    except ValidationError as exc:
        raise KnowledgeBaseError(f"Typed trait catalog validation failed: {exc}") from exc


def _as_genre_rows(rows: list[dict[str, Any]]) -> tuple[GenreCatalogRow, ...]:
    try:
        return tuple(GenreCatalogRow.model_validate(row) for row in _materialize_likely_standard_refs(rows))
    except ValidationError as exc:
        raise KnowledgeBaseError(f"Typed genre catalog validation failed: {exc}") from exc


def _as_product_rows(rows: list[dict[str, Any]]) -> tuple[ProductCatalogRow, ...]:
    try:
        return tuple(ProductCatalogRow.model_validate(row) for row in _materialize_likely_standard_refs(rows))
    except ValidationError as exc:
        raise KnowledgeBaseError(f"Typed product catalog validation failed: {exc}") from exc


def _as_legislation_rows(rows: list[dict[str, Any]]) -> tuple[LegislationCatalogRow, ...]:
    try:
        return tuple(LegislationCatalogRow.model_validate(row) for row in rows)
    except ValidationError as exc:
        raise KnowledgeBaseError(f"Typed legislation catalog validation failed: {exc}") from exc


def _as_standard_rows(rows: list[dict[str, Any]]) -> tuple[StandardCatalogRow, ...]:
    try:
        return tuple(StandardCatalogRow.model_validate(row) for row in rows)
    except ValidationError as exc:
        raise KnowledgeBaseError(f"Typed standards catalog validation failed: {exc}") from exc


def _legacy_rows(rows: Sequence[TraitCatalogRow | GenreCatalogRow | ProductCatalogRow | LegislationCatalogRow | StandardCatalogRow]) -> list[dict[str, Any]]:
    return [row.as_legacy_dict() for row in rows]

def _load_traits_catalog() -> list[dict[str, Any]]:
    base = _load_yaml_raw("traits.yaml")
    return _validate_traits(base)


def _load_genres_catalog(trait_ids: set[str]) -> list[dict[str, Any]]:
    raw = _load_yaml_raw("product_genres.yaml")
    return _validate_genres(raw, trait_ids)


def _load_products_catalog(trait_ids: set[str], genre_ids: set[str]) -> list[dict[str, Any]]:
    base = _load_yaml_raw("products.yaml")
    return _validate_products(base, trait_ids, genre_ids)


def _load_legislations_catalog(product_ids: set[str], trait_ids: set[str], genre_ids: set[str]) -> list[dict[str, Any]]:
    base = _load_yaml_raw("legislation_catalog.yaml")
    return _validate_legislations(base, product_ids, trait_ids, genre_ids)


def _load_standards_catalog(product_ids: set[str], trait_ids: set[str], legislation_keys: set[str], genre_ids: set[str]) -> list[dict[str, Any]]:
    base = _load_yaml_raw("standards.yaml")
    return _validate_standards(base, product_ids, trait_ids, legislation_keys, genre_ids)


__all__ = [
    "_as_genre_rows",
    "_as_legislation_rows",
    "_as_product_rows",
    "_as_standard_rows",
    "_as_trait_rows",
    "_legacy_rows",
    "_load_genres_catalog",
    "_load_legislations_catalog",
    "_load_products_catalog",
    "_load_standards_catalog",
    "_load_traits_catalog",
    "_load_yaml_raw",
    "_materialize_likely_standard_refs",
]
