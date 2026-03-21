from __future__ import annotations

from typing import Any, Literal, TypedDict, cast

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

StandardItemType = Literal["standard", "review"]
ProductHitType = Literal["not_product_gated", "primary_product", "alternate_product"]
MatchBasis = Literal["product", "alternate_product", "preferred_product", "traits"]
FactBasis = Literal["confirmed", "mixed", "inferred"]


class TraitGate(TypedDict):
    passes: bool
    soft_missing_any: bool
    soft_inferred_match: bool
    matched_traits_all: list[str]
    matched_traits_any: list[str]
    confirmed_traits_all: list[str]
    confirmed_traits_any: list[str]
    missing_required_traits: list[str]
    missing_any_group: list[str]
    excluded_by_traits: list[str]
    fact_basis: FactBasis


class ApplicableItems(TypedDict):
    standards: list[dict[str, Any]]
    review_items: list[dict[str, Any]]
    rejections: list[dict[str, Any]]


BASE_STANDARD_PRIORITY = {
    "EN 60335-1": 260,
    "EN 60335-2": 240,
    "EN 55014-1": 220,
    "EN 55014-2": 215,
    "EN 61000-3-2": 210,
    "EN 61000-3-3": 205,
    "EN 61000-3-11": 200,
    "EN 300 328": 190,
    "EN 301 489-1": 185,
    "EN 301 489-17": 180,
    "EN 301 893": 175,
    "EN 62311": 170,
    "EN 62479": 165,
    "EN 62209-1528": 160,
    "EN 18031-1": 150,
    "EN 18031-2": 145,
    "EN 18031-3": 140,
    "EN 63000": 130,
}


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, str)]


def _primary_directive(standard: dict[str, Any]) -> str:
    directives = _string_list(standard.get("directives"))
    if directives:
        return directives[0]
    legislation_key = standard.get("legislation_key")
    return legislation_key if isinstance(legislation_key, str) and legislation_key else "OTHER"


def _standard_item_type(standard: dict[str, Any]) -> StandardItemType:
    item_type = standard.get("item_type")
    if item_type in {"standard", "review"}:
        return cast(StandardItemType, item_type)
    code = str(standard.get("code", "")).lower()
    title = str(standard.get("title", "")).lower()
    return "review" if "review" in code or "review" in title else "standard"


def _directive_sort_key(standard: dict[str, Any]) -> tuple[int, str]:
    directive = _primary_directive(standard)
    return DIRECTIVE_ORDER.get(directive, 99), str(standard.get("code", ""))


def _product_hit_type(
    standard: dict[str, Any],
    product_type: str | None,
    matched_products: list[str] | None,
) -> ProductHitType | None:
    applies_if_products = set(_string_list(standard.get("applies_if_products")))
    exclude_if_products = set(_string_list(standard.get("exclude_if_products")))
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


def _is_preferred_standard(standard: dict[str, Any], preferred_standard_codes: set[str]) -> bool:
    if not preferred_standard_codes:
        return False
    code = standard.get("code")
    family = standard.get("standard_family")
    return (isinstance(code, str) and code in preferred_standard_codes) or (
        isinstance(family, str) and family in preferred_standard_codes
    )


def _trait_gate_details(
    standard: dict[str, Any],
    traits: set[str],
    confirmed_traits: set[str],
    allow_soft_any_miss: bool,
) -> TraitGate:
    applies_if_all = set(_string_list(standard.get("applies_if_all")))
    applies_if_any = set(_string_list(standard.get("applies_if_any")))
    exclude_if = set(_string_list(standard.get("exclude_if")))

    excluded_by_traits = sorted(exclude_if & traits)
    matched_traits_all = sorted(applies_if_all & traits)
    matched_traits_any = sorted(applies_if_any & traits)
    confirmed_traits_all = sorted(applies_if_all & confirmed_traits)
    confirmed_traits_any = sorted(applies_if_any & confirmed_traits)
    missing_required_traits = sorted(applies_if_all - traits)
    missing_any_group = sorted(applies_if_any) if applies_if_any and not matched_traits_any else []
    soft_missing_any = bool(missing_any_group and allow_soft_any_miss)

    soft_inferred_match = False
    if not missing_required_traits:
        inferred_only_required = bool(applies_if_all and not applies_if_all.issubset(confirmed_traits))
        inferred_only_any = bool(applies_if_any and matched_traits_any and not confirmed_traits_any)
        soft_inferred_match = inferred_only_required or inferred_only_any

    passes = not excluded_by_traits and not missing_required_traits and (not missing_any_group or soft_missing_any)

    fact_basis: FactBasis = "confirmed"
    if soft_inferred_match and (confirmed_traits_all or confirmed_traits_any):
        fact_basis = "mixed"
    elif soft_inferred_match:
        fact_basis = "inferred"

    return {
        "passes": passes,
        "soft_missing_any": soft_missing_any,
        "soft_inferred_match": soft_inferred_match,
        "matched_traits_all": matched_traits_all,
        "matched_traits_any": matched_traits_any,
        "confirmed_traits_all": confirmed_traits_all,
        "confirmed_traits_any": confirmed_traits_any,
        "missing_required_traits": missing_required_traits,
        "missing_any_group": missing_any_group,
        "excluded_by_traits": excluded_by_traits,
        "fact_basis": fact_basis,
    }


def _rejection_reason(product_hit_type: ProductHitType | None, gate: TraitGate) -> str:
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
    standard: dict[str, Any],
    product_type: str | None,
    matched_products: list[str],
    product_hit_type: ProductHitType | None,
    gate: TraitGate,
    is_preferred: bool,
) -> tuple[str, MatchBasis]:
    parts: list[str] = []
    match_basis: MatchBasis = "traits"

    if product_hit_type == "primary_product" and product_type:
        parts.append(f"exact product match: {product_type.replace('_', ' ')}")
        match_basis = "product"
    elif product_hit_type == "alternate_product":
        applies_if_products = set(_string_list(standard.get("applies_if_products")))
        alternate_products = [pid for pid in matched_products if pid in applies_if_products] or matched_products
        matched_list = ", ".join(pid.replace("_", " ") for pid in alternate_products)
        parts.append(f"matched through alternate detected product candidate: {matched_list}")
        match_basis = "alternate_product"
    elif is_preferred:
        parts.append("recommended by the matched product knowledge base")
        match_basis = "preferred_product"

    matched_all = gate["matched_traits_all"]
    matched_any = gate["matched_traits_any"]
    if matched_all:
        parts.append("required traits matched: " + ", ".join(matched_all))
    if matched_any:
        parts.append("additional traits matched: " + ", ".join(matched_any))
    if gate["soft_inferred_match"]:
        parts.append("some routing traits are inferred from product context and still need confirmation")
    if gate["soft_missing_any"]:
        parts.append("product context suggests relevance but the feature-specific trigger still needs confirmation")

    notes = standard.get("notes")
    if isinstance(notes, str) and notes:
        parts.append(notes)

    return ". ".join(parts), match_basis


def _priority_bonus(standard: dict[str, Any]) -> int:
    code = str(standard.get("code", "")).upper()
    for prefix, bonus in BASE_STANDARD_PRIORITY.items():
        if code.startswith(prefix):
            return bonus
    item_type = _standard_item_type(standard)
    return 100 if item_type == "standard" else 30


def _score_standard(
    standard: dict[str, Any],
    gate: TraitGate,
    product_hit_type: ProductHitType | None,
    is_preferred: bool,
) -> int:
    score = _priority_bonus(standard)

    if product_hit_type == "primary_product":
        score += 300
    elif product_hit_type == "alternate_product":
        score += 220

    if is_preferred:
        score += 80

    score += len(gate["confirmed_traits_all"]) * 40
    score += len(gate["confirmed_traits_any"]) * 18
    score += (len(gate["matched_traits_all"]) - len(gate["confirmed_traits_all"])) * 16
    score += (len(gate["matched_traits_any"]) - len(gate["confirmed_traits_any"])) * 8

    if gate["soft_missing_any"]:
        score -= 20
    if gate["soft_inferred_match"]:
        score -= 35

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
        score += 25
    elif harmonization_status == "state_of_the_art":
        score += 10
    elif harmonization_status == "review":
        score -= 5

    return score


def find_applicable_items(
    traits: set[str],
    directives: list[str],
    product_type: str | None = None,
    matched_products: list[str] | None = None,
    preferred_standard_codes: list[str] | None = None,
    explicit_traits: set[str] | None = None,
    confirmed_traits: set[str] | None = None,
) -> ApplicableItems:
    standards = load_standards()
    matched_products = matched_products or []
    preferred_codes = set(preferred_standard_codes or [])
    confirmed_traits = confirmed_traits or set(traits)
    explicit_traits = explicit_traits or set(confirmed_traits)

    results: list[dict[str, Any]] = []
    rejections: list[dict[str, Any]] = []
    for standard in standards:
        standard_directives = _string_list(standard.get("directives"))
        if directives and standard_directives and not any(d in directives for d in standard_directives):
            rejections.append({"code": standard.get("code"), "reason": "directive filter mismatch"})
            continue

        product_hit_type = _product_hit_type(standard, product_type, matched_products)
        preferred_hit = _is_preferred_standard(standard, preferred_codes)
        allow_soft_any_miss = preferred_hit
        gate = _trait_gate_details(standard, traits, confirmed_traits, allow_soft_any_miss=allow_soft_any_miss)
        if product_hit_type is None or not gate["passes"]:
            rejections.append({"code": standard.get("code"), "reason": _rejection_reason(product_hit_type, gate)})
            continue

        enriched = dict(standard)
        reason, match_basis = _build_reason(
            standard,
            product_type,
            matched_products,
            product_hit_type,
            gate,
            preferred_hit,
        )
        needs_review = gate["soft_missing_any"] or gate["soft_inferred_match"]
        enriched["reason"] = reason
        enriched["match_basis"] = match_basis
        enriched["fact_basis"] = gate["fact_basis"]
        enriched["item_type"] = "review" if needs_review else _standard_item_type(standard)
        enriched["score"] = _score_standard(standard, gate, product_hit_type, preferred_hit)
        enriched["matched_traits_all"] = gate["matched_traits_all"]
        enriched["matched_traits_any"] = gate["matched_traits_any"]
        enriched["missing_required_traits"] = gate["missing_required_traits"]
        enriched["excluded_by_traits"] = gate["excluded_by_traits"]
        enriched["product_match_type"] = product_hit_type
        results.append(enriched)

    deduped: dict[str, dict[str, Any]] = {}
    for row in results:
        code = str(row.get("code", ""))
        existing = deduped.get(code)
        if existing is None or cast(int, row["score"]) > cast(int, existing["score"]):
            deduped[code] = row

    final = list(deduped.values())
    final.sort(key=lambda row: (-cast(int, row["score"]), *_directive_sort_key(row)))

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
    preferred_standard_codes: list[str] | None = None,
    explicit_traits: set[str] | None = None,
    confirmed_traits: set[str] | None = None,
) -> list[dict[str, Any]]:
    return find_applicable_items(
        traits=traits,
        directives=directives,
        product_type=product_type,
        matched_products=matched_products,
        preferred_standard_codes=preferred_standard_codes,
        explicit_traits=explicit_traits,
        confirmed_traits=confirmed_traits,
    )["standards"]
