from __future__ import annotations

from app.domain.models import ConfidenceLevel, MissingInformationItem, ProductMatchStage, StandardItem
from app.services.classifier import normalize

from .routing import DIRECTIVE_TITLES, RADIO_ROUTE_TRAITS, _has_wireless_fact_signal


def _build_summary(
    directives: list[str],
    standards: list[StandardItem],
    review_items: list[StandardItem],
    traits: set[str],
    description: str = "",
) -> str:
    parts: list[str] = []
    if standards:
        parts.append(f"{len(standards)} standard routes identified")
    if review_items:
        parts.append(f"{len(review_items)} review-dependent routes identified")
    if directives:
        readable = ", ".join(DIRECTIVE_TITLES.get(d, (d, d))[0] for d in directives)
        parts.append(f"primary legislation: {readable}")
    if "radio" in traits and "RED_CYBER" in directives:
        parts.append("RED cybersecurity gating is active because connected radio functionality was detected")
    if "external_psu" in traits:
        parts.append("external power supply route retained because adapter or charger evidence was explicitly detected")
    if description and not _has_wireless_fact_signal(normalize(description)) and not (RADIO_ROUTE_TRAITS & traits):
        parts.append("no Wi-Fi or radio connectivity was stated in the description")
    return ". ".join(parts).strip().rstrip(".") + "."


def _directive_label(key: str) -> str:
    return DIRECTIVE_TITLES.get(key, (key, key))[0]

def _classification_summary(
    *,
    product_type: str | None,
    product_family: str | None,
    product_subtype: str | None,
    product_match_stage: ProductMatchStage,
    product_match_confidence: ConfidenceLevel,
    classification_is_ambiguous: bool,
) -> str:
    if product_match_stage == "subtype" and product_subtype:
        return f"Classified as {product_subtype} with {product_match_confidence} confidence."
    if product_match_stage == "family" and product_family:
        return f"Matched to the {product_family} family with {product_match_confidence} confidence; subtype remains unresolved."
    if product_type:
        return f"Detected product signal leans toward {product_type}, but the result remains provisional."
    if classification_is_ambiguous:
        return "The description does not provide enough product-specific evidence for a stable product match."
    return "Classification completed."


def _primary_uncertainties(
    contradictions: list[str],
    missing_items: list[MissingInformationItem],
    degraded_reasons: list[str],
    warnings: list[str],
) -> list[str]:
    items: list[str] = []
    seen: set[str] = set()
    for value in contradictions:
        if value and value not in seen:
            seen.add(value)
            items.append(value)
    for item in missing_items:
        if item.message and item.message not in seen:
            seen.add(item.message)
            items.append(item.message)
    for value in warnings + degraded_reasons:
        if value and value not in seen:
            seen.add(value)
            items.append(value)
    return items[:8]


__all__ = [
    "_build_summary",
    "_classification_summary",
    "_directive_label",
    "_primary_uncertainties",
]
