from __future__ import annotations

from collections.abc import Mapping
from typing import Any, cast

from app.domain.catalog_types import StandardCatalogRow
from app.services.knowledge_base import get_knowledge_base_snapshot
from app.services.standard_codes import canonical_standard_code_set

from .contracts import ApplicableItems, ItemsAudit, RejectionEntry, SelectionContext
from .gating import (
    _build_reason,
    _directive_review_fallback_allowed,
    _directive_sort_key,
    _is_preferred_standard,
    _product_hit_type,
    _rejection_reason,
    _standard_item_type,
    _trait_gate_details,
)
from .scoring import _score_standard


def _selection_row(row: StandardCatalogRow | Mapping[str, Any]) -> StandardCatalogRow:
    if isinstance(row, StandardCatalogRow):
        return row
    return StandardCatalogRow.model_validate(dict(row))
def _rejection_entry(row: StandardCatalogRow, reason: str) -> RejectionEntry:
    return RejectionEntry(
        code=row.code,
        title=str(row.get("title", row.code)),
        reason=reason,
    )


def _selection_payload(
    standards_rows: list[StandardCatalogRow],
    review_rows: list[StandardCatalogRow],
    rejections: list[RejectionEntry],
    audit: ItemsAudit,
) -> ApplicableItems:
    return {
        "standards": standards_rows,
        "review_items": review_rows,
        "rejections": [entry.as_dict() for entry in rejections],
        "audit": audit.as_dict(),
    }


def find_applicable_items_v1(
    traits: set[str],
    directives: list[str],
    product_type: str | None = None,
    matched_products: list[str] | None = None,
    product_genres: list[str] | None = None,
    preferred_standard_codes: list[str] | None = None,
    explicit_traits: set[str] | None = None,
    confirmed_traits: set[str] | None = None,
) -> ApplicableItems:
    standards = list(get_knowledge_base_snapshot().standards)
    matched_products = matched_products or []
    product_genres = product_genres or []
    preferred_codes = canonical_standard_code_set(preferred_standard_codes)
    confirmed_traits = confirmed_traits or set(traits)
    explicit_traits = explicit_traits or set(confirmed_traits)

    results: list[StandardCatalogRow] = []
    rejections: list[RejectionEntry] = []
    for standard in standards:
        standard_directives = list(standard.directives)
        product_hit_type = _product_hit_type(standard, product_type, matched_products, product_genres)
        preferred_hit = _is_preferred_standard(standard, preferred_codes)
        gate = _trait_gate_details(standard, traits, confirmed_traits, allow_soft_any_miss=preferred_hit)
        directive_review_fallback = False
        if directives and standard_directives and not any(directive in directives for directive in standard_directives):
            if not _directive_review_fallback_allowed(standard, preferred_codes, product_hit_type):
                rejections.append(_rejection_entry(standard, "directive filter mismatch"))
                continue
            directive_review_fallback = True
        if product_hit_type is None or not gate["passes"]:
            rejections.append(_rejection_entry(standard, _rejection_reason(product_hit_type, gate)))
            continue

        reason, match_basis = _build_reason(
            standard,
            product_type,
            matched_products,
            product_genres,
            product_hit_type,
            gate,
            preferred_hit,
        )
        if directive_review_fallback:
            reason += ". retained as a review route because the primary directive path is not currently selected"
        needs_review = gate["soft_missing_any"] or gate["soft_inferred_match"]
        updates: dict[str, object] = {
            "reason": reason,
            "match_basis": match_basis,
            "fact_basis": gate["fact_basis"],
            "item_type": "review" if needs_review or directive_review_fallback else _standard_item_type(standard),
            "score": _score_standard(standard, gate, product_hit_type, preferred_hit),
            "matched_traits_all": gate["matched_traits_all"],
            "matched_traits_any": gate["matched_traits_any"],
            "missing_required_traits": gate["missing_required_traits"],
            "excluded_by_traits": gate["excluded_by_traits"],
            "product_match_type": product_hit_type,
        }
        if directive_review_fallback:
            updates["directive"] = "OTHER"
            updates["legislation_key"] = "OTHER"
        results.append(standard.model_copy(update=updates))

    deduped: dict[str, StandardCatalogRow] = {}
    for row in results:
        existing = deduped.get(row.code)
        if existing is None or int(row.get("score", 0)) > int(existing.get("score", 0)):
            deduped[row.code] = row

    final = list(deduped.values())
    final.sort(key=lambda row: (-cast(int, row.get("score", 0)), *_directive_sort_key(row)))

    standards_rows = [row for row in final if row.get("item_type") == "standard"]
    review_rows = [row for row in final if row.get("item_type") == "review"]
    return _selection_payload(
        standards_rows,
        review_rows,
        rejections,
        ItemsAudit(),
    )


def find_applicable_standards_v1(
    traits: set[str],
    directives: list[str],
    product_type: str | None = None,
    matched_products: list[str] | None = None,
    product_genres: list[str] | None = None,
    preferred_standard_codes: list[str] | None = None,
    explicit_traits: set[str] | None = None,
    confirmed_traits: set[str] | None = None,
) -> list[StandardCatalogRow]:
    return find_applicable_items_v1(
        traits=traits,
        directives=directives,
        product_type=product_type,
        matched_products=matched_products,
        product_genres=product_genres,
        preferred_standard_codes=preferred_standard_codes,
        explicit_traits=explicit_traits,
        confirmed_traits=confirmed_traits,
    )["standards"]


def find_applicable_items_v2(
    traits: set[str],
    directives: list[str],
    product_type: str | None = None,
    matched_products: list[str] | None = None,
    product_genres: list[str] | None = None,
    preferred_standard_codes: list[str] | None = None,
    explicit_traits: set[str] | None = None,
    confirmed_traits: set[str] | None = None,
    normalized_text: str = "",
    context_tags: set[str] | None = None,
    allowed_directives: set[str] | None = None,
    selection_context: SelectionContext | Mapping[str, Any] | None = None,
) -> ApplicableItems:
    from app.services.standards_v3.pipeline import select_applicable_items_v3

    return select_applicable_items_v3(
        traits=traits,
        directives=directives,
        product_type=product_type,
        matched_products=matched_products,
        product_genres=product_genres,
        preferred_standard_codes=preferred_standard_codes,
        explicit_traits=explicit_traits,
        confirmed_traits=confirmed_traits,
        normalized_text=normalized_text,
        context_tags=context_tags,
        allowed_directives=allowed_directives,
        selection_context=selection_context,
    )


def find_applicable_standards_v2(
    traits: set[str],
    directives: list[str],
    product_type: str | None = None,
    matched_products: list[str] | None = None,
    product_genres: list[str] | None = None,
    preferred_standard_codes: list[str] | None = None,
    explicit_traits: set[str] | None = None,
    confirmed_traits: set[str] | None = None,
    normalized_text: str = "",
    context_tags: set[str] | None = None,
    allowed_directives: set[str] | None = None,
    selection_context: SelectionContext | Mapping[str, Any] | None = None,
) -> list[StandardCatalogRow]:
    return find_applicable_items_v2(
        traits=traits,
        directives=directives,
        product_type=product_type,
        matched_products=matched_products,
        product_genres=product_genres,
        preferred_standard_codes=preferred_standard_codes,
        explicit_traits=explicit_traits,
        confirmed_traits=confirmed_traits,
        normalized_text=normalized_text,
        context_tags=context_tags,
        allowed_directives=allowed_directives,
        selection_context=selection_context,
    )["standards"]


def find_applicable_items(
    traits: set[str],
    directives: list[str],
    product_type: str | None = None,
    matched_products: list[str] | None = None,
    product_genres: list[str] | None = None,
    preferred_standard_codes: list[str] | None = None,
    explicit_traits: set[str] | None = None,
    confirmed_traits: set[str] | None = None,
    normalized_text: str = "",
    context_tags: set[str] | None = None,
    allowed_directives: set[str] | None = None,
    selection_context: SelectionContext | Mapping[str, Any] | None = None,
) -> ApplicableItems:
    return find_applicable_items_v2(
        traits=traits,
        directives=directives,
        product_type=product_type,
        matched_products=matched_products,
        product_genres=product_genres,
        preferred_standard_codes=preferred_standard_codes,
        explicit_traits=explicit_traits,
        confirmed_traits=confirmed_traits,
        normalized_text=normalized_text,
        context_tags=context_tags,
        allowed_directives=allowed_directives,
        selection_context=selection_context,
    )


def find_applicable_standards(
    traits: set[str],
    directives: list[str],
    product_type: str | None = None,
    matched_products: list[str] | None = None,
    product_genres: list[str] | None = None,
    preferred_standard_codes: list[str] | None = None,
    explicit_traits: set[str] | None = None,
    confirmed_traits: set[str] | None = None,
    normalized_text: str = "",
    context_tags: set[str] | None = None,
    allowed_directives: set[str] | None = None,
    selection_context: SelectionContext | Mapping[str, Any] | None = None,
) -> list[StandardCatalogRow]:
    return find_applicable_items(
        traits=traits,
        directives=directives,
        product_type=product_type,
        matched_products=matched_products,
        product_genres=product_genres,
        preferred_standard_codes=preferred_standard_codes,
        explicit_traits=explicit_traits,
        confirmed_traits=confirmed_traits,
        normalized_text=normalized_text,
        context_tags=context_tags,
        allowed_directives=allowed_directives,
        selection_context=selection_context,
    )["standards"]
