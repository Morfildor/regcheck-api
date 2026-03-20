from __future__ import annotations

from typing import Any, TypedDict, cast

from knowledge_base import load_standards


class TraitGateDetails(TypedDict):
    passes: bool
    matched_required: list[str]
    matched_any: list[str]
    missing_required: list[str]
    excluded_hits: list[str]


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


def _trait_gate_details(standard: dict, traits: set[str]) -> TraitGateDetails:
    applies_if_all = set(cast(list[str], standard.get("applies_if_all", [])))
    applies_if_any = set(cast(list[str], standard.get("applies_if_any", [])))
    exclude_if = set(cast(list[str], standard.get("exclude_if", [])))

    missing_required = sorted(applies_if_all - traits)
    matched_required = sorted(applies_if_all & traits)
    matched_any = sorted(applies_if_any & traits)
    excluded_hits = sorted(exclude_if & traits)

    passes = not excluded_hits and not missing_required and (not applies_if_any or bool(matched_any))

    return {
        "passes": passes,
        "matched_required": matched_required,
        "matched_any": matched_any,
        "missing_required": missing_required,
        "excluded_hits": excluded_hits,
    }


def _build_reason(
    standard: dict,
    details: TraitGateDetails,
    product_type: str | None,
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

    matched_required = details["matched_required"]
    matched_any = details["matched_any"]

    if matched_required:
        parts.append("required traits matched: " + ", ".join(matched_required))
    if matched_any:
        parts.append("additional traits matched: " + ", ".join(matched_any))

    notes = standard.get("notes")
    if isinstance(notes, str) and notes.strip():
        parts.append(notes)

    return ". ".join(parts), match_basis


def _score_standard(
    standard: dict,
    details: TraitGateDetails,
    product_hit_type: str | None,
) -> int:
    score = 0
    if product_hit_type == "primary_product":
        score += 300
    elif product_hit_type == "alternate_product":
        score += 220

    score += len(details["matched_required"]) * 35
    score += len(details["matched_any"]) * 12

    if _standard_item_type(standard) == "standard":
        score += 40
    else:
        score -= 10

    confidence = standard.get("confidence", "medium")
    if confidence == "high":
        score += 20
    elif confidence == "low":
        score -= 5

    if standard.get("harmonization_status") == "harmonized":
        score += 15
    elif standard.get("harmonization_status") == "state_of_the_art":
        score += 5

    return score


def _enrich_standard(
    standard: dict,
    details: TraitGateDetails,
    product_type: str | None,
    product_hit_type: str | None,
) -> dict[str, Any]:
    enriched = dict(standard)
    reason, match_basis = _build_reason(standard, details, product_type, product_hit_type)
    enriched["reason"] = reason
    enriched["match_basis"] = match_basis
    enriched["item_type"] = _standard_item_type(standard)
    enriched["score"] = _score_standard(standard, details, product_hit_type)
    enriched["matched_traits_all"] = details["matched_required"]
    enriched["matched_traits_any"] = details["matched_any"]
    enriched["missing_required_traits"] = details["missing_required"]
    enriched["excluded_by_traits"] = details["excluded_hits"]
    enriched["product_match_type"] = product_hit_type
    enriched.setdefault("applies_if_products", [])
    enriched.setdefault("exclude_if_products", [])
    enriched.setdefault("test_focus", [])
    enriched.setdefault("evidence_hint", [])
    enriched.setdefault("keywords", [])
    return enriched


def find_applicable_items(
    traits: set[str],
    directives: list[str],
    product_type: str | None = None,
    matched_products: list[str] | None = None,
) -> dict[str, list[dict[str, Any]]]:
    standards = load_standards()
    matched_products = matched_products or []

    results: list[dict[str, Any]] = []
    rejections: list[dict[str, Any]] = []

    for standard in standards:
        standard_directives = cast(list[str], standard.get("directives", []))
        if directives and standard_directives and not any(d in directives for d in standard_directives):
            continue

        product_hit_type = _product_hit_type(standard, product_type, matched_products)
        if product_hit_type is None:
            rejections.append({"code": standard.get("code"), "reason": "product gate failed"})
            continue

        details = _trait_gate_details(standard, traits)
        if not details["passes"]:
            rejections.append(
                {
                    "code": standard.get("code"),
                    "reason": "trait gate failed",
                    "missing_required": details["missing_required"],
                    "excluded_hits": details["excluded_hits"],
                }
            )
            continue

        results.append(_enrich_standard(standard, details, product_type, product_hit_type))

    deduped: dict[str, dict[str, Any]] = {}
    for row in results:
        code = str(row.get("code", ""))
        existing = deduped.get(code)
        if existing is None or int(row["score"]) > int(existing["score"]):
            deduped[code] = row

    final = list(deduped.values())
    final.sort(key=lambda x: (-int(x["score"]), str(x.get("code", ""))))

    return {
        "standards": [row for row in final if row["item_type"] == "standard"],
        "review_items": [row for row in final if row["item_type"] == "review"],
        "rejections": rejections,
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