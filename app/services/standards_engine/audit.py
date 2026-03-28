from __future__ import annotations

from typing import Any, Literal

StandardAuditOutcome = Literal["selected", "review", "rejected"]


def _audit_item_from_row(row: dict[str, Any], outcome: StandardAuditOutcome) -> dict[str, Any]:
    return {
        "code": row.get("code"),
        "title": row.get("title", row.get("code")),
        "outcome": outcome,
        "score": int(row.get("score", 0)),
        "confidence": row.get("confidence", "medium"),
        "fact_basis": row.get("fact_basis", "inferred" if outcome == "rejected" else "confirmed"),
        "selection_group": row.get("selection_group"),
        "selection_priority": int(row.get("selection_priority", 0)),
        "keyword_hits": list(row.get("keyword_hits", [])),
        "reason": row.get("reason") or row.get("rejection_reason"),
    }


def _reject_selected_row(
    row: dict[str, Any],
    reason: str,
    rejected_rows: list[dict[str, Any]],
    rejections: list[dict[str, Any]],
) -> None:
    rejected_row = dict(row)
    rejected_row["rejection_reason"] = reason
    rejected_rows.append(rejected_row)
    rejections.append({"code": row.get("code"), "title": row.get("title", row.get("code")), "reason": reason})


__all__ = [
    "_audit_item_from_row",
    "_reject_selected_row",
]
