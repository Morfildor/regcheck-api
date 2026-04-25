from __future__ import annotations

from datetime import date
import re
from typing import Any

from app.domain.models import ConfidenceLevel, ContradictionSeverity, ProductMatchStage

from .routing_models import AnalysisDepth


def _has_any(text: str, patterns: list[str]) -> bool:
    return any(re.search(pattern, text) for pattern in patterns)


def _directive_rank(directive_order: list[str], key: str) -> int:
    try:
        return directive_order.index(key)
    except ValueError:
        return 999


def _route_title(key: str) -> str:
    return {
        "LVD": "LVD safety route",
        "EMC": "EMC compatibility route",
        "RED": "RED wireless route",
        "RED_CYBER": "RED cybersecurity route",
        "ROHS": "RoHS materials route",
        "REACH": "REACH chemicals route",
        "BATTERY": "Battery route",
        "ECO": "Ecodesign route",
        "CRA": "CRA review route",
        "GDPR": "GDPR data route",
    }.get(key, "Additional route")


def _analysis_depth(depth: str) -> AnalysisDepth:
    return depth if depth in {"quick", "deep", "standard"} else "standard"  # type: ignore[return-value]


def _confidence_level(value: Any, default: ConfidenceLevel = "medium") -> ConfidenceLevel:
    return value if value in {"low", "medium", "high"} else default  # type: ignore[return-value]


def _contradiction_severity(value: Any) -> ContradictionSeverity:
    return value if value in {"low", "medium", "high"} else "none"  # type: ignore[return-value]


def _product_match_stage(value: Any) -> ProductMatchStage:
    return value if value in {"family", "subtype"} else "ambiguous"  # type: ignore[return-value]


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, str) and item]


def _parse_date(value: Any) -> date | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


def _confidence_from_score(score: int) -> ConfidenceLevel:
    if score >= 95:
        return "high"
    if score >= 55:
        return "medium"
    return "low"


__all__ = [
    "_analysis_depth",
    "_confidence_from_score",
    "_confidence_level",
    "_contradiction_severity",
    "_directive_rank",
    "_has_any",
    "_parse_date",
    "_product_match_stage",
    "_route_title",
    "_string_list",
]
