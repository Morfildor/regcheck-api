from __future__ import annotations

from collections.abc import Mapping, Sequence

from app.domain.catalog_types import StandardCatalogRow
from app.domain.engine_models import MissingInformationItem, StandardAuditItem, StandardItem, StandardSection
from app.services.classifier import normalize
from app.services.standards_engine.contracts import ItemsAudit, RejectionEntry, SelectionContext

from .contracts import StandardsPolicyDecision, StandardsSelectionResult
from .pipeline import select_applicable_items_v3


def _selection_row(row: StandardCatalogRow | Mapping[str, object]) -> StandardCatalogRow:
    if isinstance(row, StandardCatalogRow):
        return row
    return StandardCatalogRow.model_validate(dict(row))


def _items_audit_from_payload(payload: Mapping[str, object] | None) -> ItemsAudit:
    if payload is None:
        return ItemsAudit()

    def _rows(key: str) -> list[StandardAuditItem]:
        raw_rows = payload.get(key, [])
        if not isinstance(raw_rows, list):
            return []
        rows: list[StandardAuditItem] = []
        for raw_row in raw_rows:
            if not isinstance(raw_row, Mapping):
                continue
            rows.append(StandardAuditItem.model_validate(dict(raw_row)))
        return rows

    return ItemsAudit(
        selected=_rows("selected"),
        review=_rows("review"),
        rejected=_rows("rejected"),
    )


def _rejection_entries_from_payload(payload: list[dict[str, object]] | None) -> list[RejectionEntry]:
    entries: list[RejectionEntry] = []
    for raw_row in payload or []:
        code = raw_row.get("code")
        title = raw_row.get("title")
        reason = raw_row.get("reason") or raw_row.get("rejection_reason") or ""
        entries.append(
            RejectionEntry(
                code=str(code) if isinstance(code, str) and code else None,
                title=str(title) if isinstance(title, str) and title else None,
                reason=str(reason),
            )
        )
    return entries


def _policy_from_items(
    selected_rows: Sequence[StandardCatalogRow | Mapping[str, object]],
    review_rows: Sequence[StandardCatalogRow | Mapping[str, object]],
    rejections: list[RejectionEntry],
) -> StandardsPolicyDecision:
    normalized_selected = [_selection_row(row) for row in selected_rows]
    normalized_review = [_selection_row(row) for row in review_rows]
    return StandardsPolicyDecision(
        eligibility_codes=[row.code for row in normalized_selected] + [row.code for row in normalized_review],
        fact_basis_review_codes=[row.code for row in normalized_review if str(row.get("fact_basis") or "confirmed") != "confirmed"],
        route_family_review_codes=[row.code for row in normalized_review if "scope" in str(row.get("reason") or "").lower()],
        selection_group_review_codes=[row.code for row in normalized_review if row.get("selection_group")],
        rejection_reasons=[entry.reason for entry in rejections],
    )


def run_standards_policy(
    *,
    prepared,
    routes,
    description: str,
    context: SelectionContext,
    missing_items: list[MissingInformationItem],
    standard_sections: list[StandardSection],
    standard_item_from_row,
    sort_standard_items,
    standards_selector=None,
) -> StandardsSelectionResult:
    selector = standards_selector or select_applicable_items_v3
    items = selector(
        traits=prepared.route_traits,
        directives=list(routes.allowed_directives),
        product_type=prepared.routing_product_type,
        matched_products=sorted(prepared.routing_matched_products),
        product_genres=sorted(prepared.product_genres),
        preferred_standard_codes=sorted(prepared.likely_standards),
        explicit_traits=set(prepared.traits_data.explicit_traits),
        confirmed_traits=prepared.confirmed_traits,
        normalized_text=normalize(description),
        context_tags=context.context_tags,
        allowed_directives=routes.allowed_directives,
        selection_context=context,
    )

    selected_rows = [_selection_row(row) for row in items["standards"]]
    review_rows = [_selection_row(row) for row in items["review_items"]]
    all_rows = selected_rows + review_rows
    dedup: dict[str, StandardCatalogRow] = {}
    for row in all_rows:
        key = str(row.get("code") or "")
        if key not in dedup or int(row.get("score", 0)) > int(dedup[key].get("score", 0)):
            dedup[key] = row

    standard_items: list[StandardItem] = []
    review_items: list[StandardItem] = []
    for row in dedup.values():
        item = standard_item_from_row(row, routes.legislation_by_directive, prepared.route_traits)
        if item.item_type == "review":
            review_items.append(item)
        else:
            standard_items.append(item)

    standard_items = sort_standard_items(
        standard_items,
        primary_standard_code=prepared.route_plan.primary_standard_code,
        supporting_standard_codes=prepared.route_plan.supporting_standard_codes,
    )
    review_items = sort_standard_items(
        review_items,
        primary_standard_code=prepared.route_plan.primary_standard_code,
        supporting_standard_codes=prepared.route_plan.supporting_standard_codes,
    )
    rejections = _rejection_entries_from_payload(items["rejections"] if "rejections" in items else None)

    return StandardsSelectionResult(
        context=context,
        standard_items=standard_items,
        review_items=review_items,
        current_review_items=[item for item in review_items if item.timing_status == "current"],
        missing_items=missing_items,
        standard_sections=standard_sections,
        items_audit=_items_audit_from_payload(items["audit"] if "audit" in items else None),
        rejections=rejections,
        policy=_policy_from_items(selected_rows, review_rows, rejections),
    )
