from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any, cast

from app.domain.catalog_types import StandardCatalogRow
from app.services.knowledge_base import get_knowledge_base_snapshot

from .audit import _audit_item_from_row
from .contracts import ApplicableItems, ItemsAudit, RejectionEntry, SelectionContext
from .gating import (
    FactBasis,
    _baseline_confirmed_traits,
    _build_reason,
    _directive_review_fallback_allowed,
    _directive_sort_key,
    _fact_basis_satisfies,
    _finalize_selected_rows_v2,
    _is_preferred_standard,
    _normalize_selection_group,
    _product_hit_type,
    _recover_preferred_62368_group_loser,
    _rejection_reason,
    _soften_preferred_62368_gate,
    _standard_item_type,
    _trait_gate_details,
)
from .scoring import _keyword_hits, _score_standard, _score_standard_v2
from .selection_groups import _selection_group_winners, _selection_sort_key


def _selection_row(row: StandardCatalogRow | Mapping[str, Any]) -> StandardCatalogRow:
    if isinstance(row, StandardCatalogRow):
        return row
    return StandardCatalogRow.model_validate(dict(row))


def _selection_rows(rows: Sequence[StandardCatalogRow | Mapping[str, Any]]) -> list[StandardCatalogRow]:
    return [_selection_row(row) for row in rows]


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
    preferred_codes = set(preferred_standard_codes or [])
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
    standards = list(get_knowledge_base_snapshot().standards)
    matched_products = matched_products or []
    product_genres = product_genres or []
    preferred_codes = set(preferred_standard_codes or [])
    confirmed_traits = confirmed_traits or set(traits)
    explicit_traits = explicit_traits or set(confirmed_traits)
    effective_confirmed_traits = confirmed_traits | _baseline_confirmed_traits(explicit_traits)
    context_tags = context_tags or set()

    candidates: list[StandardCatalogRow] = []
    rejections: list[RejectionEntry] = []
    rejected_rows: list[StandardCatalogRow] = []
    for standard in standards:
        standard_directives = list(standard.directives)
        product_hit_type = _product_hit_type(standard, product_type, matched_products, product_genres)
        preferred_hit = _is_preferred_standard(standard, preferred_codes)
        gate = _trait_gate_details(standard, traits, effective_confirmed_traits, allow_soft_any_miss=preferred_hit)
        gate, preferred_62368_fallback_reason = _soften_preferred_62368_gate(
            standard,
            gate,
            preferred_codes,
            product_genres,
        )
        directive_review_fallback = False
        if directives and standard_directives and not any(directive in directives for directive in standard_directives):
            if not _directive_review_fallback_allowed(standard, preferred_codes, product_hit_type):
                reason = "directive filter mismatch"
                rejected_rows.append(standard.model_copy(update={"rejection_reason": reason}))
                rejections.append(_rejection_entry(standard, reason))
                continue
            directive_review_fallback = True
        if product_hit_type is None or not gate["passes"]:
            reason = _rejection_reason(product_hit_type, gate)
            rejected_rows.append(standard.model_copy(update={"rejection_reason": reason}))
            rejections.append(_rejection_entry(standard, reason))
            continue

        keyword_hits = _keyword_hits(standard, normalized_text)
        required_fact_basis = cast(FactBasis, standard.get("required_fact_basis", "inferred"))
        sufficient_fact_basis = _fact_basis_satisfies(required_fact_basis, gate["fact_basis"])

        reason, match_basis = _build_reason(
            standard,
            product_type,
            matched_products,
            product_genres,
            product_hit_type,
            gate,
            preferred_hit,
        )
        if keyword_hits:
            reason += ". keyword evidence: " + ", ".join(keyword_hits)
        if preferred_62368_fallback_reason:
            reason += ". " + preferred_62368_fallback_reason
        if not sufficient_fact_basis:
            reason += f". requires {required_fact_basis} evidence before the route can be treated as fully selected"
        if directive_review_fallback:
            reason += ". retained as a review route because the primary directive path is not currently selected"

        needs_review = (
            gate["soft_missing_any"]
            or gate["soft_inferred_match"]
            or not sufficient_fact_basis
            or directive_review_fallback
            or preferred_62368_fallback_reason is not None
        )
        updates: dict[str, object] = {
            "reason": reason,
            "match_basis": match_basis,
            "fact_basis": gate["fact_basis"],
            "required_fact_basis": required_fact_basis,
            "item_type": "review" if needs_review else _standard_item_type(standard),
            "score": _score_standard_v2(standard, gate, product_hit_type, preferred_hit, keyword_hits, context_tags),
            "matched_traits_all": gate["matched_traits_all"],
            "matched_traits_any": gate["matched_traits_any"],
            "missing_required_traits": gate["missing_required_traits"],
            "excluded_by_traits": gate["excluded_by_traits"],
            "product_match_type": product_hit_type,
            "keyword_hits": keyword_hits,
            "selection_group": _normalize_selection_group(standard),
            "selection_priority": int(standard.get("selection_priority") or 0),
        }
        if directive_review_fallback:
            updates["directive"] = "OTHER"
            updates["legislation_key"] = "OTHER"
        candidates.append(standard.model_copy(update=updates))

    winners, group_losers = _selection_group_winners(candidates)
    recovered_group_losers: list[StandardCatalogRow] = []
    rejected_group_losers: list[StandardCatalogRow] = []
    for loser in group_losers:
        if _recover_preferred_62368_group_loser(loser, preferred_codes, product_genres):
            recovered_group_losers.append(
                loser.model_copy(
                    update={
                        "item_type": "review",
                        "reason": (
                            (str(loser.get("reason", "")) + ". " if loser.get("reason") else "")
                            + "retained as a review route because EN 62368-1 is explicitly preferred for a small smart-device "
                            + "product even though another LVD safety standard scored higher"
                        ),
                    }
                )
            )
            continue
        rejected_group_losers.append(loser)
        rejections.append(
            RejectionEntry(
                code=loser.code,
                title=str(loser.get("title", loser.code)),
                reason=str(loser.get("rejection_reason") or ""),
            )
        )

    winners.extend(recovered_group_losers)

    deduped: dict[str, StandardCatalogRow] = {}
    for row in winners:
        existing = deduped.get(row.code)
        if existing is None or _selection_sort_key(row) > _selection_sort_key(existing):
            deduped[row.code] = row

    final = list(deduped.values())
    finalized_rows, finalized_rejections = _finalize_selected_rows_v2(
        final,
        traits=traits,
        allowed_directives=allowed_directives,
        selection_context=selection_context,
        rejections=rejections,
    )
    rejected_rows.extend(rejected_group_losers)
    rejected_rows.extend(finalized_rejections)
    final = finalized_rows
    final.sort(key=lambda row: (-cast(int, row.get("score", 0)), -int(row.get("selection_priority", 0)), *_directive_sort_key(row)))

    standards_rows = [row for row in final if row.get("item_type") == "standard"]
    review_rows = [row for row in final if row.get("item_type") == "review"]
    audit = ItemsAudit(
        selected=[_audit_item_from_row(row, "selected") for row in standards_rows],
        review=[_audit_item_from_row(row, "review") for row in review_rows],
        rejected=[_audit_item_from_row(row, "rejected") for row in rejected_rows],
    )

    return _selection_payload(standards_rows, review_rows, rejections, audit)


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
