from __future__ import annotations

from collections.abc import Sequence
import re
from typing import Any

from app.domain.catalog_types import GenreCatalogRow, ProductCatalogRow, StandardCatalogRow

from .paths import KnowledgeBaseError
from .product_normalization import normalize_product_row
from .validator import (
    ALLOWED_HARMONIZATION_STATUSES,
    _dedupe_keep_order,
    _normalize_likely_standard_refs,
    _string_list,
)


def _normalize_standard_code(code: str) -> str:
    value = re.sub(r"\s+", " ", (code or "").strip())
    if value.startswith("EN EN "):
        value = value.replace("EN EN ", "EN ", 1)
    return value


def _derive_harmonization_status(row: dict[str, Any]) -> str:
    explicit = row.get("harmonization_status")
    if explicit in ALLOWED_HARMONIZATION_STATUSES:
        return explicit
    if row.get("item_type") == "review":
        return "review"
    if row.get("is_harmonized") is True:
        return "harmonized"
    if row.get("is_harmonized") is False:
        return "state_of_the_art"
    return "unknown"


def _genre_map(genres: Sequence[GenreCatalogRow]) -> dict[str, GenreCatalogRow]:
    return {row.id: row for row in genres}


def _expand_genre_product_ids(target_genres: list[str], products: Sequence[ProductCatalogRow]) -> list[str]:
    wanted = set(target_genres)
    return [row.id for row in products if wanted & set(_string_list(row.get("genres")))]


def _enrich_products(rows: list[dict[str, Any]], genres: Sequence[GenreCatalogRow]) -> list[dict[str, Any]]:
    genre_index = _genre_map(genres)
    out: list[dict[str, Any]] = []
    for row in rows:
        enriched = normalize_product_row(row)
        enriched["product_family"] = enriched.get("product_family") or enriched["id"]
        enriched["product_subfamily"] = enriched.get("product_subfamily") or enriched["id"]
        enriched.setdefault("required_clues", [])
        enriched.setdefault("preferred_clues", [])
        enriched.setdefault("exclude_clues", [])
        enriched.setdefault("confusable_with", [])
        enriched.setdefault("family_traits", [])
        enriched.setdefault("subtype_traits", list(enriched.get("implied_traits", [])))
        enriched.setdefault("family_keywords", [])
        enriched.setdefault("genres", [])
        enriched.setdefault("genre_keywords", [])
        enriched.setdefault("genre_traits", [])
        enriched.setdefault("genre_default_traits", [])
        enriched.setdefault("genre_functional_classes", [])
        enriched.setdefault("genre_likely_standards", [])

        for genre_id in enriched["genres"]:
            genre = genre_index.get(genre_id)
            if not genre:
                continue
            enriched["genre_keywords"] = _dedupe_keep_order(_string_list(enriched.get("genre_keywords")) + _string_list(genre.get("keywords")))
            enriched["genre_traits"] = _dedupe_keep_order(_string_list(enriched.get("genre_traits")) + _string_list(genre.get("traits")))
            enriched["genre_default_traits"] = _dedupe_keep_order(_string_list(enriched.get("genre_default_traits")) + _string_list(genre.get("default_traits")))
            enriched["genre_functional_classes"] = _dedupe_keep_order(
                _string_list(enriched.get("genre_functional_classes")) + _string_list(genre.get("functional_classes"))
            )
            enriched["genre_likely_standards"] = _dedupe_keep_order(
                _string_list(enriched.get("genre_likely_standards")) + _string_list(genre.get("likely_standards"))
            )
            enriched["family_keywords"] = _dedupe_keep_order(_string_list(enriched.get("family_keywords")) + _string_list(genre.get("keywords")))
            enriched["family_traits"] = _dedupe_keep_order(_string_list(enriched.get("family_traits")) + _string_list(genre.get("traits")))
            enriched["default_traits"] = _dedupe_keep_order(_string_list(enriched.get("default_traits")) + _string_list(genre.get("default_traits")))

        core_traits = list(enriched.get("core_traits") or [])
        default_traits = list(enriched.get("default_traits") or [])
        if not core_traits and enriched.get("family_traits"):
            core_traits.extend(list(enriched.get("family_traits") or []))
        if not core_traits and enriched.get("subtype_traits"):
            core_traits.extend(list(enriched.get("subtype_traits") or []))
        if not core_traits:
            core_traits.extend(list(enriched.get("implied_traits") or []))
        if not default_traits:
            default_traits.extend(list(enriched.get("implied_traits") or []))
        enriched["core_traits"] = list(dict.fromkeys(core_traits))
        enriched["default_traits"] = [trait for trait in dict.fromkeys(default_traits) if trait not in enriched["core_traits"]]
        enriched["likely_standard_refs"] = _normalize_likely_standard_refs(enriched, f"Product '{enriched['id']}'") if "id" in enriched else []
        enriched["likely_standards"] = [item["ref"] for item in enriched["likely_standard_refs"]]
        out.append(enriched)
    return out


def _enrich_legislations(rows: list[dict[str, Any]], products: Sequence[ProductCatalogRow]) -> list[dict[str, Any]]:
    return [dict(row) for row in rows]


def _enrich_standards(rows: list[dict[str, Any]], products: Sequence[ProductCatalogRow]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    seen_normalized_codes: set[str] = set()
    for row in rows:
        enriched = dict(row)
        enriched["code"] = _normalize_standard_code(enriched.get("code", ""))
        if enriched["code"] in seen_normalized_codes:
            raise KnowledgeBaseError(f"Duplicate normalized standard code in merged standards catalog: {enriched['code']}")
        seen_normalized_codes.add(enriched["code"])
        enriched["standard_family"] = enriched.get("standard_family") or enriched["code"].split(":", 1)[0].strip()
        enriched["harmonization_status"] = _derive_harmonization_status(enriched)
        enriched.setdefault("test_focus", [])
        enriched.setdefault("evidence_hint", [])
        enriched.setdefault("keywords", [])
        enriched.setdefault("selection_group", None)
        enriched.setdefault("selection_priority", 0)
        enriched["required_fact_basis"] = enriched.get("required_fact_basis") or "inferred"
        out.append(enriched)
    return out


def _post_validate_product_standard_links(
    products: Sequence[ProductCatalogRow],
    genres: Sequence[GenreCatalogRow],
    standards: Sequence[StandardCatalogRow],
) -> None:
    known_references = {row.code for row in standards} | {row.standard_family for row in standards if row.standard_family}

    for product in products:
        pid = product.id
        for ref_item in product.get("likely_standard_refs") or _normalize_likely_standard_refs(product, f"Product '{pid}'"):
            reference = ref_item["ref"]
            if reference not in known_references:
                raise KnowledgeBaseError(
                    f"Product '{pid}' references likely_standard '{reference}' that does not match any standard code or family."
                )

    for genre in genres:
        gid = genre.id
        for ref_item in genre.get("likely_standard_refs") or _normalize_likely_standard_refs(genre, f"Genre '{gid}'"):
            reference = ref_item["ref"]
            if reference not in known_references:
                raise KnowledgeBaseError(
                    f"Genre '{gid}' references likely_standard '{reference}' that does not match any standard code or family."
                )


__all__ = [
    "_derive_harmonization_status",
    "_enrich_legislations",
    "_enrich_products",
    "_enrich_standards",
    "_expand_genre_product_ids",
    "_genre_map",
    "_normalize_standard_code",
    "_post_validate_product_standard_links",
]
