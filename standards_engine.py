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
    audit: dict[str, Any]


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


FACT_BASIS_RANK: dict[FactBasis, int] = {"inferred": 0, "mixed": 1, "confirmed": 2}

BASE_STANDARD_PRIORITY_V2 = {
    "EN 60335-1": 155,
    "EN 60335-2": 175,
    "EN 55014-1": 145,
    "EN 55014-2": 140,
    "EN 55032": 145,
    "EN 55035": 140,
    "EN 62368-1": 155,
    "EN 62311": 130,
    "EN 62479": 125,
    "EN 62209": 150,
    "EN 50566": 145,
    "EN 18031-": 150,
    "EN 300 328": 155,
    "EN 301 489-1": 145,
    "EN 301 489-17": 140,
    "EN 301 893": 140,
    "EN 63000": 120,
}


def _fact_basis_satisfies(required: FactBasis, actual: FactBasis) -> bool:
    return FACT_BASIS_RANK[actual] >= FACT_BASIS_RANK[required]


def _keyword_hits(standard: dict[str, Any], normalized_text: str) -> list[str]:
    hits: list[str] = []
    if not normalized_text:
        return hits
    for keyword in _string_list(standard.get("keywords")):
        phrase = " ".join(str(keyword).lower().split())
        if phrase and phrase in normalized_text:
            hits.append(keyword)
    return hits


def _priority_bonus_v2(standard: dict[str, Any]) -> int:
    code = str(standard.get("code", "")).upper()
    for prefix, bonus in BASE_STANDARD_PRIORITY_V2.items():
        if code.startswith(prefix):
            return bonus
    return 95 if _standard_item_type(standard) == "standard" else 45


def _context_bonus_v2(standard: dict[str, Any], context_tags: set[str]) -> int:
    code = str(standard.get("code", ""))
    bonus = 0
    if "scope:av_ict" in context_tags and (code == "EN 62368-1" or code in {"EN 55032", "EN 55035"}):
        bonus += 80
    if "scope:appliance" in context_tags and (code.startswith("EN 60335-") or code.startswith("EN 55014-")):
        bonus += 80
    if "exposure:close_proximity" in context_tags and (
        code.startswith("EN 62209") or code in {"EN 50566", "EN 50663 / EN 62311 review", "EN 50665"}
    ):
        bonus += 70
    if "exposure:household_emf" in context_tags and code == "EN 62233":
        bonus += 45
    if "optical:laser" in context_tags and code == "EN 60825-1":
        bonus += 35
    if "optical:photobio" in context_tags and code == "EN 62471":
        bonus += 30
    if "power:external_psu" in context_tags and code == "EN 50563":
        bonus += 35
    if "power:external_psu" not in context_tags and code == "EN 50563":
        bonus -= 40
    return bonus


def _score_standard_v2(
    standard: dict[str, Any],
    gate: TraitGate,
    product_hit_type: ProductHitType | None,
    is_preferred: bool,
    keyword_hits: list[str],
    context_tags: set[str],
) -> int:
    score = _priority_bonus_v2(standard)

    if product_hit_type == "primary_product":
        score += 135
    elif product_hit_type == "alternate_product":
        score += 85
    if is_preferred:
        score += 65

    score += len(gate["confirmed_traits_all"]) * 34
    score += len(gate["confirmed_traits_any"]) * 16
    score += (len(gate["matched_traits_all"]) - len(gate["confirmed_traits_all"])) * 12
    score += (len(gate["matched_traits_any"]) - len(gate["confirmed_traits_any"])) * 6
    score += len(keyword_hits) * 16
    score += int(standard.get("selection_priority") or 0) * 2
    score += _context_bonus_v2(standard, context_tags)

    if gate["soft_missing_any"]:
        score -= 18
    if gate["soft_inferred_match"]:
        score -= 28

    confidence = standard.get("confidence", "medium")
    if confidence == "high":
        score += 18
    elif confidence == "low":
        score -= 8

    harmonization_status = standard.get("harmonization_status")
    if harmonization_status == "harmonized":
        score += 24
    elif harmonization_status == "state_of_the_art":
        score += 12
    elif harmonization_status == "review":
        score -= 10

    return score


def _selection_sort_key(row: dict[str, Any]) -> tuple[int, int, int, str]:
    return (
        int(row.get("score", 0)),
        int(row.get("selection_priority", 0)),
        FACT_BASIS_RANK[cast(FactBasis, row.get("fact_basis", "inferred"))],
        str(row.get("code", "")),
    )


def _selection_group_winners(rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    winners: list[dict[str, Any]] = []
    losers: list[dict[str, Any]] = []
    grouped: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        selection_group = row.get("selection_group")
        if not isinstance(selection_group, str) or not selection_group:
            winners.append(row)
            continue
        grouped.setdefault(selection_group, []).append(row)

    for selection_group, group_rows in grouped.items():
        ordered = sorted(group_rows, key=_selection_sort_key, reverse=True)
        winner = ordered[0]
        winners.append(winner)
        for loser in ordered[1:]:
            losers.append(
                {
                    **loser,
                    "rejection_reason": f"selection group '{selection_group}' won by {winner.get('code')}",
                }
            )

    return winners, losers


def find_applicable_items_v1(
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
        "audit": {"selected": [], "review": [], "rejected": []},
    }


def find_applicable_standards_v1(
    traits: set[str],
    directives: list[str],
    product_type: str | None = None,
    matched_products: list[str] | None = None,
    preferred_standard_codes: list[str] | None = None,
    explicit_traits: set[str] | None = None,
    confirmed_traits: set[str] | None = None,
) -> list[dict[str, Any]]:
    return find_applicable_items_v1(
        traits=traits,
        directives=directives,
        product_type=product_type,
        matched_products=matched_products,
        preferred_standard_codes=preferred_standard_codes,
        explicit_traits=explicit_traits,
        confirmed_traits=confirmed_traits,
    )["standards"]


def find_applicable_items_v2(
    traits: set[str],
    directives: list[str],
    product_type: str | None = None,
    matched_products: list[str] | None = None,
    preferred_standard_codes: list[str] | None = None,
    explicit_traits: set[str] | None = None,
    confirmed_traits: set[str] | None = None,
    normalized_text: str = "",
    context_tags: set[str] | None = None,
) -> ApplicableItems:
    standards = load_standards()
    matched_products = matched_products or []
    preferred_codes = set(preferred_standard_codes or [])
    confirmed_traits = confirmed_traits or set(traits)
    explicit_traits = explicit_traits or set(confirmed_traits)
    context_tags = context_tags or set()

    candidates: list[dict[str, Any]] = []
    rejections: list[dict[str, Any]] = []
    for standard in standards:
        standard_directives = _string_list(standard.get("directives"))
        if directives and standard_directives and not any(d in directives for d in standard_directives):
            rejections.append({"code": standard.get("code"), "reason": "directive filter mismatch"})
            continue

        product_hit_type = _product_hit_type(standard, product_type, matched_products)
        preferred_hit = _is_preferred_standard(standard, preferred_codes)
        gate = _trait_gate_details(standard, traits, confirmed_traits, allow_soft_any_miss=preferred_hit)
        if product_hit_type is None or not gate["passes"]:
            rejections.append({"code": standard.get("code"), "reason": _rejection_reason(product_hit_type, gate)})
            continue

        keyword_hits = _keyword_hits(standard, normalized_text)
        required_fact_basis = cast(FactBasis, standard.get("required_fact_basis", "inferred"))
        sufficient_fact_basis = _fact_basis_satisfies(required_fact_basis, gate["fact_basis"])

        enriched = dict(standard)
        reason, match_basis = _build_reason(
            standard,
            product_type,
            matched_products,
            product_hit_type,
            gate,
            preferred_hit,
        )
        if keyword_hits:
            reason += ". keyword evidence: " + ", ".join(keyword_hits)
        if not sufficient_fact_basis:
            reason += f". requires {required_fact_basis} evidence before the route can be treated as fully selected"

        needs_review = gate["soft_missing_any"] or gate["soft_inferred_match"] or not sufficient_fact_basis
        enriched["reason"] = reason
        enriched["match_basis"] = match_basis
        enriched["fact_basis"] = gate["fact_basis"]
        enriched["required_fact_basis"] = required_fact_basis
        enriched["item_type"] = "review" if needs_review else _standard_item_type(standard)
        enriched["score"] = _score_standard_v2(standard, gate, product_hit_type, preferred_hit, keyword_hits, context_tags)
        enriched["matched_traits_all"] = gate["matched_traits_all"]
        enriched["matched_traits_any"] = gate["matched_traits_any"]
        enriched["missing_required_traits"] = gate["missing_required_traits"]
        enriched["excluded_by_traits"] = gate["excluded_by_traits"]
        enriched["product_match_type"] = product_hit_type
        enriched["keyword_hits"] = keyword_hits
        enriched["selection_group"] = standard.get("selection_group")
        enriched["selection_priority"] = int(standard.get("selection_priority") or 0)
        candidates.append(enriched)

    winners, group_losers = _selection_group_winners(candidates)
    for loser in group_losers:
        rejections.append({"code": loser.get("code"), "reason": loser.get("rejection_reason")})

    deduped: dict[str, dict[str, Any]] = {}
    for row in winners:
        code = str(row.get("code", ""))
        existing = deduped.get(code)
        if existing is None or _selection_sort_key(row) > _selection_sort_key(existing):
            deduped[code] = row

    final = list(deduped.values())
    final.sort(key=lambda row: (-cast(int, row["score"]), -int(row.get("selection_priority", 0)), *_directive_sort_key(row)))

    standards_rows = [row for row in final if row["item_type"] == "standard"]
    review_rows = [row for row in final if row["item_type"] == "review"]
    audit = {
        "selected": [
            {
                "code": row.get("code"),
                "title": row.get("title"),
                "outcome": "selected",
                "score": int(row.get("score", 0)),
                "confidence": row.get("confidence", "medium"),
                "fact_basis": row.get("fact_basis", "confirmed"),
                "selection_group": row.get("selection_group"),
                "selection_priority": int(row.get("selection_priority", 0)),
                "keyword_hits": row.get("keyword_hits", []),
                "reason": row.get("reason"),
            }
            for row in standards_rows
        ],
        "review": [
            {
                "code": row.get("code"),
                "title": row.get("title"),
                "outcome": "review",
                "score": int(row.get("score", 0)),
                "confidence": row.get("confidence", "medium"),
                "fact_basis": row.get("fact_basis", "confirmed"),
                "selection_group": row.get("selection_group"),
                "selection_priority": int(row.get("selection_priority", 0)),
                "keyword_hits": row.get("keyword_hits", []),
                "reason": row.get("reason"),
            }
            for row in review_rows
        ],
        "rejected": [
            {
                "code": row.get("code"),
                "title": row.get("title", row.get("code")),
                "outcome": "rejected",
                "score": int(row.get("score", 0)),
                "confidence": row.get("confidence", "medium"),
                "fact_basis": row.get("fact_basis", "inferred"),
                "selection_group": row.get("selection_group"),
                "selection_priority": int(row.get("selection_priority", 0)),
                "keyword_hits": row.get("keyword_hits", []),
                "reason": row.get("reason") or row.get("rejection_reason"),
            }
            for row in group_losers
        ],
    }

    return {
        "standards": standards_rows,
        "review_items": review_rows,
        "rejections": rejections,
        "audit": audit,
    }


def find_applicable_standards_v2(
    traits: set[str],
    directives: list[str],
    product_type: str | None = None,
    matched_products: list[str] | None = None,
    preferred_standard_codes: list[str] | None = None,
    explicit_traits: set[str] | None = None,
    confirmed_traits: set[str] | None = None,
    normalized_text: str = "",
    context_tags: set[str] | None = None,
) -> list[dict[str, Any]]:
    return find_applicable_items_v2(
        traits=traits,
        directives=directives,
        product_type=product_type,
        matched_products=matched_products,
        preferred_standard_codes=preferred_standard_codes,
        explicit_traits=explicit_traits,
        confirmed_traits=confirmed_traits,
        normalized_text=normalized_text,
        context_tags=context_tags,
    )["standards"]


def find_applicable_items(
    traits: set[str],
    directives: list[str],
    product_type: str | None = None,
    matched_products: list[str] | None = None,
    preferred_standard_codes: list[str] | None = None,
    explicit_traits: set[str] | None = None,
    confirmed_traits: set[str] | None = None,
    normalized_text: str = "",
    context_tags: set[str] | None = None,
) -> ApplicableItems:
    return find_applicable_items_v2(
        traits=traits,
        directives=directives,
        product_type=product_type,
        matched_products=matched_products,
        preferred_standard_codes=preferred_standard_codes,
        explicit_traits=explicit_traits,
        confirmed_traits=confirmed_traits,
        normalized_text=normalized_text,
        context_tags=context_tags,
    )


def find_applicable_standards(
    traits: set[str],
    directives: list[str],
    product_type: str | None = None,
    matched_products: list[str] | None = None,
    preferred_standard_codes: list[str] | None = None,
    explicit_traits: set[str] | None = None,
    confirmed_traits: set[str] | None = None,
    normalized_text: str = "",
    context_tags: set[str] | None = None,
) -> list[dict[str, Any]]:
    return find_applicable_items(
        traits=traits,
        directives=directives,
        product_type=product_type,
        matched_products=matched_products,
        preferred_standard_codes=preferred_standard_codes,
        explicit_traits=explicit_traits,
        confirmed_traits=confirmed_traits,
        normalized_text=normalized_text,
        context_tags=context_tags,
    )["standards"]
