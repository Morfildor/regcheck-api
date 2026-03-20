from __future__ import annotations

from typing import Any

from knowledge_base import load_standards

DIRECTIVE_ORDER = {
    "LVD": 0,
    "EMC": 1,
    "RED": 2,
    "RED_CYBER": 3,
    "ROHS": 4,
    "REACH": 5,
    "GDPR": 6,
    "FCM": 7,
    "FCM_PLASTIC": 8,
    "BATTERY": 9,
    "ECO": 10,
    "ESPR": 11,
    "CRA": 12,
    "AI_Act": 13,
    "MD": 14,
    "MACH_REG": 15,
    "OTHER": 99,
}


def _standard_item_type(standard: dict) -> str:
    item_type = standard.get("item_type")
    if item_type in {"standard", "review"}:
        return item_type
    code = standard.get("code", "").lower()
    title = standard.get("title", "").lower()
    return "review" if "review" in code or "review" in title else "standard"


def _directive_sort_key(standard: dict[str, Any]) -> tuple[int, str]:
    directive = (standard.get("directives") or [standard.get("legislation_key") or "OTHER"])[0]
    return DIRECTIVE_ORDER.get(directive, 99), standard.get("code", "")


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


def _trait_gate_details(standard: dict, traits: set[str]) -> dict[str, list[str] | bool]:
    applies_if_all = set(standard.get("applies_if_all", []))
    applies_if_any = set(standard.get("applies_if_any", []))
    exclude_if = set(standard.get("exclude_if", []))

    excluded_by_traits = sorted(exclude_if & traits)
    matched_traits_all = sorted(applies_if_all & traits)
    matched_traits_any = sorted(applies_if_any & traits)
    missing_required_traits = sorted(applies_if_all - traits)
    missing_any_group = sorted(applies_if_any) if applies_if_any and not matched_traits_any else []

    passes = not excluded_by_traits and not missing_required_traits and not missing_any_group
    return {
        "passes": passes,
        "matched_traits_all": matched_traits_all,
        "matched_traits_any": matched_traits_any,
        "missing_required_traits": missing_required_traits,
        "missing_any_group": missing_any_group,
        "excluded_by_traits": excluded_by_traits,
    }


def _rejection_reason(product_hit_type: str | None, gate: dict[str, list[str] | bool]) -> str:
    if product_hit_type is None:
        return "product gating failed"
    if gate["excluded_by_traits"]:
        return "excluded by traits: " + ", ".join(gate["excluded_by_traits"])
    if gate["missing_required_traits"]:
        return "missing required traits: " + ", ".join(gate["missing_required_traits"])
    if gate["missing_any_group"]:
        return "missing one-of traits: " + ", ".join(gate["missing_any_group"])
    return "not applicable"


def _build_reason(
    standard: dict,
    traits: set[str],
    product_type: str | None,
    matched_products: list[str],
    product_hit_type: str | None,
    gate: dict[str, list[str] | bool],
) -> tuple[str, str]:
    parts: list[str] = []
    match_basis = "traits"

    if product_hit_type == "primary_product" and product_type:
        parts.append(f"exact product match: {product_type.replace('_', ' ')}")
        match_basis = "product"
    elif product_hit_type == "alternate_product":
        matched_list = ", ".join(pid.replace("_", " ") for pid in matched_products)
        parts.append(f"matched through alternate detected product candidate: {matched_list}")
        match_basis = "alternate_product"

    matched_all = gate.get("matched_traits_all", [])
    matched_any = gate.get("matched_traits_any", [])
    if matched_all:
        parts.append("required traits matched: " + ", ".join(matched_all))
    if matched_any:
        parts.append("additional traits matched: " + ", ".join(matched_any))

    if standard.get("notes"):
        parts.append(standard["notes"])

    return ". ".join(parts), match_basis


def _score_standard(
    standard: dict,
    gate: dict[str, list[str] | bool],
    product_hit_type: str | None,
) -> int:
    score = 0
    if product_hit_type == "primary_product":
        score += 300
    elif product_hit_type == "alternate_product":
        score += 220

    score += len(gate.get("matched_traits_all", [])) * 35
    score += len(gate.get("matched_traits_any", [])) * 14

    if _standard_item_type(standard) == "standard":
        score += 40
    else:
        score -= 10

    confidence = standard.get("confidence", "medium")
    if confidence == "high":
        score += 20
    elif confidence == "low":
        score -= 5

    harmonization_status = standard.get("harmonization_status")
    if harmonization_status == "harmonized":
        score += 10
    elif harmonization_status == "review":
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
    rejections: list[dict[str, Any]] = []
    for standard in standards:
        standard_directives = standard.get("directives", [])
        if directives and standard_directives and not any(d in directives for d in standard_directives):
            rejections.append(
                {
                    "code": standard.get("code"),
                    "reason": "directive filter mismatch",
                }
            )
            continue

        product_hit_type = _product_hit_type(standard, product_type, matched_products)
        gate = _trait_gate_details(standard, traits)
        if product_hit_type is None or not gate["passes"]:
            rejections.append(
                {
                    "code": standard.get("code"),
                    "reason": _rejection_reason(product_hit_type, gate),
                }
            )
            continue

        enriched = dict(standard)
        reason, match_basis = _build_reason(standard, traits, product_type, matched_products, product_hit_type, gate)
        enriched["reason"] = reason
        enriched["match_basis"] = match_basis
        enriched["item_type"] = _standard_item_type(standard)
        enriched["score"] = _score_standard(standard, gate, product_hit_type)
        enriched["matched_traits_all"] = gate["matched_traits_all"]
        enriched["matched_traits_any"] = gate["matched_traits_any"]
        enriched["missing_required_traits"] = gate["missing_required_traits"]
        enriched["excluded_by_traits"] = gate["excluded_by_traits"]
        enriched["product_match_type"] = product_hit_type
        results.append(enriched)

    deduped: dict[str, dict] = {}
    for row in results:
        code = row.get("code", "")
        existing = deduped.get(code)
        if existing is None or row["score"] > existing["score"]:
            deduped[code] = row

    final = list(deduped.values())
    final.sort(key=lambda x: (-x["score"], *_directive_sort_key(x)))

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
