from __future__ import annotations

from knowledge_base import load_standards


def _has_product_gate(standard: dict) -> bool:
    return bool(standard.get("applies_if_products") or standard.get("exclude_if_products"))


def standard_applies(
    standard: dict,
    traits: set[str],
    product_type: str | None = None,
    matched_products: set[str] | None = None,
) -> bool:
    matched_products = matched_products or set()
    applies_if_all = set(standard.get("applies_if_all", []))
    applies_if_any = set(standard.get("applies_if_any", []))
    exclude_if = set(standard.get("exclude_if", []))
    applies_if_products = set(standard.get("applies_if_products", []))
    exclude_if_products = set(standard.get("exclude_if_products", []))

    if exclude_if & traits:
        return False

    if product_type and product_type in exclude_if_products:
        return False
    if matched_products & exclude_if_products:
        return False

    if applies_if_products:
        if not product_type:
            return False
        if product_type not in applies_if_products:
            return False

    if applies_if_all and not applies_if_all.issubset(traits):
        return False

    if applies_if_any and not (applies_if_any & traits):
        return False

    return True


def build_reason(
    standard: dict,
    traits: set[str],
    product_type: str | None = None,
    matched_products: set[str] | None = None,
) -> str:
    matched_products = matched_products or set()
    all_hits = [t for t in standard.get("applies_if_all", []) if t in traits]
    any_hits = [t for t in standard.get("applies_if_any", []) if t in traits]
    product_hits = []

    applies_if_products = set(standard.get("applies_if_products", []))
    if product_type and product_type in applies_if_products:
        product_hits.append(product_type)

    parts = []
    if product_hits:
        pretty = ", ".join(x.replace("_", " ") for x in product_hits)
        parts.append("product match: " + pretty)
    if all_hits:
        parts.append("required traits matched: " + ", ".join(all_hits))
    if any_hits:
        parts.append("additional traits matched: " + ", ".join(any_hits))

    notes = standard.get("notes")
    if notes:
        parts.append(notes)

    return ". ".join(parts) if parts else (notes or "")


def find_applicable_standards(
    traits: set[str],
    directives: list[str],
    product_type: str | None = None,
    matched_products: list[str] | None = None,
) -> list[dict]:
    standards = load_standards()
    results: list[dict] = []
    matched_products_set = set(matched_products or [])

    for standard in standards:
        standard_directives = standard.get("directives", [])
        if directives and not any(d in directives for d in standard_directives):
            continue

        if standard_applies(
            standard,
            traits,
            product_type=product_type,
            matched_products=matched_products_set,
        ):
            enriched = dict(standard)
            enriched["reason"] = build_reason(
                standard,
                traits,
                product_type=product_type,
                matched_products=matched_products_set,
            )
            enriched["_priority"] = 0 if _has_product_gate(standard) else 1
            results.append(enriched)

    deduped: dict[str, dict] = {}
    for row in results:
        code = row.get("code", "")
        existing = deduped.get(code)
        if existing is None or row.get("_priority", 1) < existing.get("_priority", 1):
            deduped[code] = row

    final = list(deduped.values())
    final.sort(key=lambda x: (x.get("_priority", 1), x.get("category", ""), x.get("code", "")))
    for row in final:
        row.pop("_priority", None)
    return final
