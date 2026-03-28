from __future__ import annotations

from typing import Any
from typing import cast

from .gating import FACT_BASIS_RANK, FactBasis


def _selection_sort_key(row: dict[str, Any]) -> tuple[int, int, int, int, str]:
    return (
        1 if row.get("item_type") == "standard" else 0,
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


__all__ = [
    "_selection_group_winners",
    "_selection_sort_key",
]
