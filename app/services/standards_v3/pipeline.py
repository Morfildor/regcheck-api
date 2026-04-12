from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, cast

from app.domain.catalog_types import StandardCatalogRow
from app.services.knowledge_base import get_knowledge_base_snapshot
from app.services.standards_engine.audit import _audit_item_from_row
from app.services.standards_engine.contracts import ApplicableItems, ItemsAudit, RejectionEntry, SelectionContext
from app.services.standards_engine.gating import (
    FactBasis,
    ProductHitType,
    TraitGate,
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
from app.services.standards_engine.scoring import _keyword_hits, _score_standard_v2
from app.services.standards_engine.selection_groups import _selection_group_winners, _selection_sort_key
from app.services.standard_codes import canonical_standard_code_set


@dataclass(frozen=True, slots=True)
class EligibilityDecision:
    row: StandardCatalogRow
    gate: TraitGate
    product_hit_type: ProductHitType
    preferred_hit: bool
    directive_review_fallback: bool
    preferred_62368_fallback_reason: str | None
    keyword_hits: list[str]


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


def _run_eligibility_stage(
    *,
    directives: list[str],
    traits: set[str],
    effective_confirmed_traits: set[str],
    product_type: str | None,
    matched_products: list[str],
    product_genres: list[str],
    preferred_codes: set[str],
    normalized_text: str,
) -> tuple[list[EligibilityDecision], list[RejectionEntry], list[StandardCatalogRow]]:
    decisions: list[EligibilityDecision] = []
    rejections: list[RejectionEntry] = []
    rejected_rows: list[StandardCatalogRow] = []

    for standard in get_knowledge_base_snapshot().standards:
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

        decisions.append(
            EligibilityDecision(
                row=standard,
                gate=gate,
                product_hit_type=product_hit_type,
                preferred_hit=preferred_hit,
                directive_review_fallback=directive_review_fallback,
                preferred_62368_fallback_reason=preferred_62368_fallback_reason,
                keyword_hits=_keyword_hits(standard, normalized_text),
            )
        )

    return decisions, rejections, rejected_rows


def _apply_fact_basis_stage(
    *,
    decisions: list[EligibilityDecision],
    product_type: str | None,
    matched_products: list[str],
    product_genres: list[str],
    context_tags: set[str],
) -> tuple[list[StandardCatalogRow], list[str], list[str], list[str]]:
    candidates: list[StandardCatalogRow] = []
    eligibility_codes: list[str] = []
    fact_basis_review_codes: list[str] = []
    route_family_review_codes: list[str] = []

    for decision in decisions:
        row = decision.row
        required_fact_basis = cast(FactBasis, row.get("required_fact_basis", "inferred"))
        sufficient_fact_basis = _fact_basis_satisfies(required_fact_basis, decision.gate["fact_basis"])
        reason, match_basis = _build_reason(
            row,
            product_type,
            matched_products,
            product_genres,
            decision.product_hit_type,
            decision.gate,
            decision.preferred_hit,
        )
        if decision.keyword_hits:
            reason += ". keyword evidence: " + ", ".join(decision.keyword_hits)
        if decision.preferred_62368_fallback_reason:
            reason += ". " + decision.preferred_62368_fallback_reason
        if not sufficient_fact_basis:
            reason += f". requires {required_fact_basis} evidence before the route can be treated as fully selected"
        if decision.directive_review_fallback:
            reason += ". retained as a review route because the primary directive path is not currently selected"

        needs_review = (
            decision.gate["soft_missing_any"]
            or decision.gate["soft_inferred_match"]
            or not sufficient_fact_basis
            or decision.directive_review_fallback
            or decision.preferred_62368_fallback_reason is not None
        )
        updates: dict[str, object] = {
            "reason": reason,
            "match_basis": match_basis,
            "fact_basis": decision.gate["fact_basis"],
            "required_fact_basis": required_fact_basis,
            "item_type": "review" if needs_review else _standard_item_type(row),
            "score": _score_standard_v2(
                row,
                decision.gate,
                decision.product_hit_type,
                decision.preferred_hit,
                decision.keyword_hits,
                context_tags,
            ),
            "matched_traits_all": decision.gate["matched_traits_all"],
            "matched_traits_any": decision.gate["matched_traits_any"],
            "missing_required_traits": decision.gate["missing_required_traits"],
            "excluded_by_traits": decision.gate["excluded_by_traits"],
            "product_match_type": decision.product_hit_type,
            "keyword_hits": decision.keyword_hits,
            "selection_group": _normalize_selection_group(row),
            "selection_priority": int(row.get("selection_priority") or 0),
        }
        if decision.directive_review_fallback:
            updates["directive"] = "OTHER"
            updates["legislation_key"] = "OTHER"

        selected = row.model_copy(update=updates)
        candidates.append(selected)
        eligibility_codes.append(selected.code)
        if selected.get("item_type") == "review" and selected.get("fact_basis") != "confirmed":
            fact_basis_review_codes.append(selected.code)
        if selected.get("item_type") == "review" and "scope" in str(selected.get("reason") or "").lower():
            route_family_review_codes.append(selected.code)

    return candidates, eligibility_codes, fact_basis_review_codes, route_family_review_codes


def _apply_selection_group_stage(
    *,
    candidates: list[StandardCatalogRow],
    preferred_codes: set[str],
    product_genres: list[str],
    rejections: list[RejectionEntry],
    rejected_rows: list[StandardCatalogRow],
) -> tuple[list[StandardCatalogRow], list[str]]:
    winners, group_losers = _selection_group_winners(candidates)
    recovered_group_losers: list[StandardCatalogRow] = []
    selection_group_review_codes: list[str] = []
    for loser in group_losers:
        if _recover_preferred_62368_group_loser(loser, preferred_codes, product_genres):
            recovered = loser.model_copy(
                update={
                    "item_type": "review",
                    "reason": (
                        (str(loser.get("reason", "")) + ". " if loser.get("reason") else "")
                        + "retained as a review route because EN 62368-1 is explicitly preferred for a small smart-device "
                        + "product even though another LVD safety standard scored higher"
                    ),
                }
            )
            recovered_group_losers.append(recovered)
            selection_group_review_codes.append(recovered.code)
            continue
        rejected_rows.append(loser)
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

    return list(deduped.values()), selection_group_review_codes


def _apply_route_family_stage(
    *,
    rows: list[StandardCatalogRow],
    traits: set[str],
    allowed_directives: set[str] | None,
    selection_context: SelectionContext | Mapping[str, Any] | None,
    rejections: list[RejectionEntry],
    rejected_rows: list[StandardCatalogRow],
) -> tuple[list[StandardCatalogRow], list[str]]:
    finalized_rows, finalized_rejections = _finalize_selected_rows_v2(
        rows,
        traits=traits,
        allowed_directives=allowed_directives,
        selection_context=selection_context,
        rejections=rejections,
    )
    rejected_rows.extend(finalized_rejections)

    route_family_review_codes = [
        row.code
        for row in finalized_rows
        if row.get("item_type") == "review" and "scope" in str(row.get("reason") or "").lower()
    ]
    return finalized_rows, route_family_review_codes


def select_applicable_items_v3(
    *,
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
    matched_products = matched_products or []
    product_genres = product_genres or []
    preferred_codes = canonical_standard_code_set(preferred_standard_codes)
    confirmed_traits = confirmed_traits or set(traits)
    explicit_traits = explicit_traits or set(confirmed_traits)
    effective_confirmed_traits = confirmed_traits | _baseline_confirmed_traits(explicit_traits)
    context_tags = context_tags or set()

    decisions, rejections, rejected_rows = _run_eligibility_stage(
        directives=directives,
        traits=traits,
        effective_confirmed_traits=effective_confirmed_traits,
        product_type=product_type,
        matched_products=matched_products,
        product_genres=product_genres,
        preferred_codes=preferred_codes,
        normalized_text=normalized_text,
    )
    candidates, eligibility_codes, fact_basis_review_codes, route_family_review_codes = _apply_fact_basis_stage(
        decisions=decisions,
        product_type=product_type,
        matched_products=matched_products,
        product_genres=product_genres,
        context_tags=context_tags,
    )
    grouped_rows, selection_group_review_codes = _apply_selection_group_stage(
        candidates=candidates,
        preferred_codes=preferred_codes,
        product_genres=product_genres,
        rejections=rejections,
        rejected_rows=rejected_rows,
    )
    final_rows, post_route_family_review_codes = _apply_route_family_stage(
        rows=grouped_rows,
        traits=traits,
        allowed_directives=allowed_directives,
        selection_context=selection_context,
        rejections=rejections,
        rejected_rows=rejected_rows,
    )
    route_family_review_codes = sorted({*route_family_review_codes, *post_route_family_review_codes})

    final_rows.sort(key=lambda row: (-cast(int, row.get("score", 0)), -int(row.get("selection_priority", 0)), *_directive_sort_key(row)))

    standards_rows = [row for row in final_rows if row.get("item_type") == "standard"]
    review_rows = [row for row in final_rows if row.get("item_type") == "review"]
    audit = ItemsAudit(
        selected=[_audit_item_from_row(row, "selected") for row in standards_rows],
        review=[_audit_item_from_row(row, "review") for row in review_rows],
        rejected=[_audit_item_from_row(row, "rejected") for row in rejected_rows],
    )

    # Keep the stage outputs directly derivable from the rows so policy ownership stays in v3.
    selection_group_review_codes = sorted(
        {
            *selection_group_review_codes,
            *[
                row.code
                for row in review_rows
                if isinstance(row.get("selection_group"), str) and row.get("selection_group")
            ],
        }
    )
    _ = (eligibility_codes, fact_basis_review_codes, route_family_review_codes, selection_group_review_codes)
    return _selection_payload(standards_rows, review_rows, rejections, audit)


__all__ = ["EligibilityDecision", "select_applicable_items_v3"]
