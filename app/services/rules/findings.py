from __future__ import annotations

from typing import Literal

from app.domain.models import ContradictionSeverity, Finding, LegislationItem, MissingInformationItem, StandardItem

from .risk import _join_readable
from .routing import _analysis_depth
from .summary import _directive_label


AnalysisDepth = Literal["quick", "standard", "deep"]


def _finding_action_from_legislation(item: LegislationItem) -> str | None:
    actions: list[str] = []
    if item.doc_impacts:
        actions.append("Prepare: " + _join_readable(item.doc_impacts, 3))
    if item.evidence_strength != "confirmed" and item.triggers:
        actions.append("Confirm: " + _join_readable(item.triggers, 2))
    return " ".join(actions) or None


def _finding_action_from_standard(item: StandardItem) -> str | None:
    actions: list[str] = []
    if item.evidence_hint:
        actions.append("Collect: " + _join_readable(item.evidence_hint, 3))
    if item.test_focus:
        actions.append("Check: " + _join_readable(item.test_focus, 2))
    return " ".join(actions) or None


def _build_findings(
    *,
    depth: AnalysisDepth,
    legislation_items: list[LegislationItem],
    standards: list[StandardItem],
    review_items: list[StandardItem],
    missing_items: list[MissingInformationItem],
    contradictions: list[str],
    contradiction_severity: ContradictionSeverity,
) -> list[Finding]:
    depth = _analysis_depth(depth)
    limits = {
        "quick": {"max": 6, "missing": 2, "review": 2, "legislation": 3, "standards": 0, "future": 0, "info": 0},
        "standard": {"max": 14, "missing": 4, "review": 4, "legislation": 6, "standards": 4, "future": 2, "info": 0},
        "deep": {"max": 24, "missing": 8, "review": 8, "legislation": 12, "standards": 10, "future": 6, "info": 2},
    }[depth]

    current_legislation = [item for item in legislation_items if item.timing_status == "current" and item.bucket != "informational"]
    future_legislation = [item for item in legislation_items if item.timing_status == "future"]
    informational_legislation = [item for item in legislation_items if item.bucket == "informational"]
    current_review_items = [item for item in review_items if item.timing_status == "current"]
    future_review_items = [item for item in review_items if item.timing_status == "future"]

    candidates: list[tuple[int, Finding]] = []
    seen: set[tuple[str, str, str]] = set()

    def add(priority: int, finding: Finding) -> None:
        key = (finding.directive, finding.article, finding.finding)
        if key in seen:
            return
        seen.add(key)
        candidates.append((priority, finding))

    if contradictions:
        status = "FAIL" if contradiction_severity in {"medium", "high"} else "WARN"
        add(
            0,
            Finding(
                directive="INPUT",
                article="Contradiction",
                status=status,
                finding="Conflicting product signals need resolution: " + _join_readable(contradictions, 3),
                action="Clarify the actual product architecture and power/connectivity claims before relying on the route output.",
            ),
        )

    for item in missing_items[: limits["missing"]]:
        impacted_routes = [_directive_label(route) for route in item.route_impact]
        finding_text = item.message
        if impacted_routes:
            finding_text += " Affects: " + _join_readable(impacted_routes, 3) + "."
        action = None
        action_parts: list[str] = []
        if item.next_actions:
            action_parts.append("Next: " + _join_readable(item.next_actions, 2))
        if item.examples:
            action_parts.append("Clarify with: " + _join_readable(item.examples, 2))
        if action_parts:
            action = " ".join(action_parts)
        status = "FAIL" if item.importance == "high" else ("WARN" if item.importance == "medium" else "INFO")
        add(
            10 if item.importance == "high" else 40,
            Finding(
                directive="INPUT",
                article="Missing information",
                status=status,
                finding=finding_text,
                action=action,
            ),
        )

    for item in current_review_items[: limits["review"]]:
        finding_text = f"{item.code} stays review-dependent before it can be relied on."
        if item.reason:
            finding_text += " " + item.reason
        action = _finding_action_from_standard(item)
        add(
            20,
            Finding(
                directive=item.directive,
                article="Standard review",
                status="WARN",
                finding=finding_text,
                action=action,
            ),
        )

    for item in current_legislation[: limits["legislation"]]:
        finding_text = f"{item.title} is part of the current compliance route."
        if item.reason:
            finding_text += " " + item.reason
        if item.is_forced:
            finding_text += " Included because the route was explicitly forced."
        status = "WARN" if item.applicability == "applicable" and item.bucket in {"ce", "non_ce"} else "INFO"
        add(
            30,
            Finding(
                directive=item.directive_key,
                article="Legislation route",
                status=status,
                finding=finding_text,
                action=_finding_action_from_legislation(item),
            ),
        )

    for item in standards[: limits["standards"]]:
        finding_text = f"{item.code} selected as a {item.harmonization_status.replace('_', ' ')} standard route."
        if item.reason:
            finding_text += " " + item.reason
        status = "PASS" if item.harmonization_status == "harmonized" else "INFO"
        add(
            50,
            Finding(
                directive=item.directive,
                article="Standard route",
                status=status,
                finding=finding_text,
                action=_finding_action_from_standard(item),
            ),
        )

    if depth in {"standard", "deep"}:
        prioritized_future = sorted(
            future_legislation,
            key=lambda item: (0 if item.directive_key == "AI_Act" else 1, item.directive_key, item.title),
        )
        for item in prioritized_future[: limits["future"]]:
            finding_text = f"{item.title} is a future watchlist regime."
            if item.applicable_from:
                finding_text += f" Applies from {item.applicable_from}."
            if item.reason:
                finding_text += " " + item.reason
            add(
                45 if item.directive_key == "AI_Act" else 70,
                Finding(
                    directive=item.directive_key,
                    article="Future regime",
                    status="INFO",
                    finding=finding_text,
                    action=_finding_action_from_legislation(item),
                ),
            )

    if depth == "deep":
        for item in future_review_items[: limits["review"]]:
            finding_text = f"{item.code} is not yet a current route and remains future review-dependent."
            if item.reason:
                finding_text += " " + item.reason
            add(
                60,
                Finding(
                    directive=item.directive,
                    article="Future standard review",
                    status="INFO",
                    finding=finding_text,
                    action=_finding_action_from_standard(item),
                ),
            )

        for item in informational_legislation[: limits["info"]]:
            add(
                80,
                Finding(
                    directive=item.directive_key,
                    article="Informational notice",
                    status="INFO",
                    finding=f"{item.title} is informational context rather than a primary conformity route.",
                    action=_finding_action_from_legislation(item),
                ),
            )

    candidates.sort(key=lambda row: (row[0], row[1].directive, row[1].article, row[1].finding))
    return [finding for _, finding in candidates[: limits["max"]]]


__all__ = [
    "AnalysisDepth",
    "_build_findings",
]
