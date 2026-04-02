from __future__ import annotations

from typing import Literal

from app.domain.catalog_types import StandardCatalogRow
from app.domain.models import StandardAuditItem

from .contracts import RejectionEntry

StandardAuditOutcome = Literal["selected", "review", "rejected"]


def _audit_item_from_row(row: StandardCatalogRow, outcome: StandardAuditOutcome) -> StandardAuditItem:
    return StandardAuditItem(
        code=row.code,
        title=str(row.get("title", row.code)),
        outcome=outcome,
        score=int(row.get("score", 0)),
        confidence=row.get("confidence", "medium"),
        fact_basis=row.get("fact_basis", "inferred" if outcome == "rejected" else "confirmed"),
        selection_group=row.get("selection_group"),
        selection_priority=int(row.get("selection_priority", 0)),
        keyword_hits=list(row.get("keyword_hits", [])),
        reason=row.get("reason") or row.get("rejection_reason"),
    )


def _reject_selected_row(
    row: StandardCatalogRow,
    reason: str,
    rejected_rows: list[StandardCatalogRow],
    rejections: list[RejectionEntry],
) -> None:
    rejected_row = row.model_copy(update={"rejection_reason": reason})
    rejected_rows.append(rejected_row)
    rejections.append(
        RejectionEntry(
            code=row.code,
            title=str(row.get("title", row.code)),
            reason=reason,
        )
    )


__all__ = [
    "_audit_item_from_row",
    "_reject_selected_row",
]
