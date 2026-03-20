from __future__ import annotations

from typing import Any

from knowledge_base import load_standards


def _standard_item_type(standard: dict) -> str:
    item_type = standard.get("item_type")
    if item_type in {"standard", "review"}:
        return item_type
    code = standard.get("code", "").lower()
    title = standard.get("title", "").lower()
    return "review" if "review" in code or "review" in title else "standard"


def _product_hit_type(
    standard: dict,
    product_type: str | None,
    matched_products: list[str] | None,
) -> str | None:
    applies_if_products = set(standard.get("applies_if_products", []))
    exclude_if_products = set(standard.get("exclude_if_products", []))
    matched_products = matched_products or []

    if product_type and product_type in exclude_if_products:
        return None
    if any(pid in exclude_if_products for pid in matched_products):
        return None

    if not applies_if_products:
        return "not_product_gated"

    if product_type and product_type in applies_if_products:
        return "primary_product"

    if any(pid in applies_if_products for pid in matched_products):
        return "alternate_product"

    return None


def _trait_gate_passes(standard: dict, traits: set[str]) -> bool:
    applies_if_all = set(standard.get("applies_if_all", []))
    applies_if_any = set(standard.get("applies_if_any", []))
    exclude_if = set(standard.get("exclude_if", []))

    if exclude_if & traits:
        return False
    if applies_if_all and not applies_if_all.issubset(traits):
        return False
    if applies_if_any and not (applies_if_any & traits):
        return False
    return True


def _build_reason(
    standard: dict,
    traits: set[str],
    product_type: str | None,
    matched_products: list[str],
    product_hit_type: str | None,
) -> tuple[str, str]:
    parts: list[str] = []
    match_basis = "traits"

    if product_hit_type == "primary_product" and product_type:
        parts.append(f"exact product match: {product_type.replace('_', ' ')}")
        match_basis = "product"
    elif product_hit_type == "alternate_product":
        parts.append("matched through alternate detected product candidate")
        match_basis = "alternate_product"

    all_hits = [t for t in standard.get("applies_if_all", []) if t in traits]
    any_hits = [t for t in standard.get("applies_if_any", []) if t in traits]
    if all_hits:
        parts.append("required traits matched: " + ", ".join(all_hits))
    if any_hits:
        parts.append("additional traits matched: " + ", ".join(any_hits))

    if standard.get("notes"):
        parts.append(standard["notes"])

    return ". ".join(parts), match_basis


def _score_standard(
    standard: dict,
    traits: set[str],
    product_hit_type: str | None,
) -> int:
    score = 0
    if product_hit_type == "primary_product":
        score += 300
    elif product_hit_type == "alternate_product":
        score += 220

    score += len([t for t in standard.get("applies_if_all", []) if t in traits]) * 35
    score += len([t for t in standard.get("applies_if_any", []) if t in traits]) * 12

    if _standard_item_type(standard) == "standard":
        score += 40
    else:
        score -= 10

    confidence = standard.get("confidence", "medium")
    if confidence == "high":
        score += 20
    elif confidence == "low":
        score -= 5

    return score


def find_applicable_items(
    traits: set[str],
    directives: list[str],
    product_type: str | None = None,
    matched_products: list[str] | None = None,
) -> dict[str, list[dict[str, Any]]]:
    standards = load_standards()
    matched_products = matched_products or []

    results: list[dict[str, Any]] = []
    for standard in standards:
        standard_directives = standard.get("directives", [])
        if directives and standard_directives and not any(d in directives for d in standard_directives):
            continue

        product_hit_type = _product_hit_type(standard, product_type, matched_products)
        if product_hit_type is None:
            continue

        if not _trait_gate_passes(standard, traits):
            continue

        enriched = dict(standard)
        reason, match_basis = _build_reason(standard, traits, product_type, matched_products, product_hit_type)
        enriched["reason"] = reason
        enriched["match_basis"] = match_basis
        enriched["item_type"] = _standard_item_type(standard)
        enriched["score"] = _score_standard(standard, traits, product_hit_type)
        results.append(enriched)

    deduped: dict[str, dict] = {}
    for row in results:
        code = row.get("code", "")
        existing = deduped.get(code)
        if existing is None or row["score"] > existing["score"]:
            deduped[code] = row

    final = list(deduped.values())
    final.sort(key=lambda x: (-x["score"], x.get("code", "")))

    return {
        "standards": [row for row in final if row["item_type"] == "standard"],
        "review_items": [row for row in final if row["item_type"] == "review"],
    }


def find_applicable_standards(
    traits: set[str],
    directives: list[str],
    product_type: str | None = None,
    matched_products: list[str] | None = None,
) -> list[dict[str, Any]]:
    return find_applicable_items(
        traits=traits,
        directives=directives,
        product_type=product_type,
        matched_products=matched_products,
    )["standards"]
