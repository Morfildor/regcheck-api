from __future__ import annotations

from typing import Any

from app.services.rules.route_anchors import apply_route_anchor_defaults

from .product_inference_debt import apply_inference_debt_metadata
from .product_normalization_compat import apply_compatibility_enrichments
from .taxonomy import get_taxonomy_snapshot, resolve_product_taxonomy


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if isinstance(item, str) and str(item).strip()]


def _merge_unique(*values: Any) -> list[str]:
    merged: list[str] = []
    seen: set[str] = set()
    for value in values:
        for item in _string_list(value):
            if item in seen:
                continue
            seen.add(item)
            merged.append(item)
    return merged


def _apply_taxonomy_governance(row: dict[str, Any], *, allow_legacy_fallback: bool) -> tuple[dict[str, Any], Any]:
    raw_row = dict(row)
    product_id = str(raw_row.get("id") or "").strip()
    taxonomy_resolution = resolve_product_taxonomy(
        product_id=product_id,
        declared_family=str(raw_row.get("product_family") or "").strip() or None,
        declared_subfamily=str(raw_row.get("product_subfamily") or "").strip() or None,
        allow_legacy_fallback=allow_legacy_fallback,
    )

    enriched = dict(raw_row)
    if taxonomy_resolution.family is not None:
        enriched["product_family"] = taxonomy_resolution.family
    if taxonomy_resolution.subfamily is not None:
        enriched["product_subfamily"] = taxonomy_resolution.subfamily

    snapshot = get_taxonomy_snapshot()
    family_definition = snapshot.family_definition(taxonomy_resolution.family)
    if family_definition is not None:
        enriched["family_allowed_route_anchors"] = list(family_definition.allowed_route_anchors)
        enriched["family_required_traits"] = list(family_definition.required_traits)
        enriched["family_boundary_tendencies"] = list(family_definition.boundary_tendencies)
        if not _string_list(enriched.get("genres")) and family_definition.default_genres:
            enriched["genres"] = list(family_definition.default_genres)
            enriched["genre_source"] = "taxonomy_family_default"
    return enriched, taxonomy_resolution


def normalize_product_row(
    row: dict[str, Any],
    *,
    allow_legacy_family_fallback: bool = True,
) -> dict[str, Any]:
    raw_row = dict(row)
    normalized, taxonomy_resolution = _apply_taxonomy_governance(
        raw_row,
        allow_legacy_fallback=allow_legacy_family_fallback,
    )
    normalized = apply_compatibility_enrichments(normalized)
    normalized["genres"] = _merge_unique(normalized.get("genres"))
    normalized["boundary_tags"] = _merge_unique(normalized.get("boundary_tags"))
    normalized = apply_route_anchor_defaults(normalized)
    normalized = apply_inference_debt_metadata(raw_row, normalized, taxonomy_resolution)
    normalized["boundary_tags"] = _merge_unique(normalized.get("boundary_tags"))
    return normalized


__all__ = ["normalize_product_row"]
