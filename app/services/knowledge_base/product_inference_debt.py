from __future__ import annotations

from typing import Any

from .taxonomy import TaxonomyResolution


def _has_value(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def build_inference_debt_flags(
    raw_row: dict[str, Any],
    normalized_row: dict[str, Any],
    taxonomy_resolution: TaxonomyResolution,
) -> list[str]:
    flags: list[str] = []

    if not _has_value(raw_row.get("product_family")):
        flags.append("family_inferred")
    if not _has_value(raw_row.get("product_subfamily")):
        flags.append("subfamily_inferred")
    if not _has_value(raw_row.get("route_anchor")):
        flags.append("route_anchor_inferred")
    if not _has_value(raw_row.get("route_family")):
        flags.append("route_family_inferred")
    if taxonomy_resolution.compatibility_fallback_used:
        flags.append("compatibility_fallback")
    if str(normalized_row.get("route_anchor_confidence") or "").strip() == "low":
        flags.append("route_anchor_low_confidence")
    if str(normalized_row.get("max_match_stage") or "").strip() == "family":
        flags.append("family_level_only")
    if len(normalized_row.get("route_anchor_reasons") or []) <= 1:
        flags.append("route_reason_weak")

    seen: set[str] = set()
    ordered: list[str] = []
    for flag in flags:
        if flag in seen:
            continue
        seen.add(flag)
        ordered.append(flag)
    return ordered


def apply_inference_debt_metadata(
    raw_row: dict[str, Any],
    normalized_row: dict[str, Any],
    taxonomy_resolution: TaxonomyResolution,
) -> dict[str, Any]:
    enriched = dict(normalized_row)
    enriched["family_resolution_source"] = taxonomy_resolution.family_source
    enriched["subfamily_resolution_source"] = taxonomy_resolution.subfamily_source
    enriched["compatibility_fallback_used"] = taxonomy_resolution.compatibility_fallback_used
    enriched["taxonomy_resolution_issues"] = list(taxonomy_resolution.issues)
    enriched["inference_debt_flags"] = build_inference_debt_flags(raw_row, enriched, taxonomy_resolution)
    return enriched


__all__ = [
    "apply_inference_debt_metadata",
    "build_inference_debt_flags",
]
