from __future__ import annotations

from typing import cast

from app.domain.catalog_types import StandardCatalogRow

from .gating import FACT_BASIS_RANK, FactBasis


def _selection_sort_key(row: StandardCatalogRow) -> tuple[int, int, int, int, str]:
    return (
        1 if row.get("item_type") == "standard" else 0,
        int(row.get("score", 0)),
        int(row.get("selection_priority", 0)),
        FACT_BASIS_RANK[cast(FactBasis, row.get("fact_basis", "inferred"))],
        str(row.get("code", "")),
    )


def _selection_group_winners(rows: list[StandardCatalogRow]) -> tuple[list[StandardCatalogRow], list[StandardCatalogRow]]:
    winners: list[StandardCatalogRow] = []
    losers: list[StandardCatalogRow] = []
    grouped: dict[str, list[StandardCatalogRow]] = {}
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
                loser.model_copy(
                    update={
                        "rejection_reason": f"selection group '{selection_group}' won by {winner.get('code')}",
                    }
                )
            )

    return winners, losers


__all__ = [
    "_selection_group_winners",
    "_selection_sort_key",
]
