from __future__ import annotations

from typing import Any

from classifier import extract_traits
from knowledge_base import load_legislations
from models import (
    AnalysisResult,
    Finding,
    LegislationItem,
    ProductCandidate,
    RiskLevel,
    StandardItem,
)
from standards_engine import find_applicable_items

APP_VERSION = "3.1.1"


def _matches_legislation(row: dict[str, Any], traits_info: dict[str, Any]) -> bool:
    traits = set(traits_info.get("all_traits", []))
    functional_classes = set(traits_info.get("functional_classes", []))
    product_type = traits_info.get("product_type")

    all_of_traits = set(row.get("all_of_traits", []))
    any_of_traits = set(row.get("any_of_traits", []))
    none_of_traits = set(row.get("none_of_traits", []))

    all_of_fc = set(row.get("all_of_functional_classes", []))
    any_of_fc = set(row.get("any_of_functional_classes", []))
    none_of_fc = set(row.get("none_of_functional_classes", []))

    any_of_product_types = set(row.get("any_of_product_types", []))
    exclude_product_types = set(row.get("exclude_product_types", []))

    if all_of_traits and not all_of_traits.issubset(traits):
        return False
    if any_of_traits and not (any_of_traits & traits):
        return False
    if none_of_traits and (none_of_traits & traits):
        return False

    if all_of_fc and not all_of_fc.issubset(functional_classes):
        return False
    if any_of_fc and not (any_of_fc & functional_classes):
        return False
    if none_of_fc and (none_of_fc & functional_classes):
        return False

    if any_of_product_types and product_type not in any_of_product_types:
        return False
    if exclude_product_types and product_type in exclude_product_types:
        return False

    return True


def _build_legislation_items(traits_info: dict[str, Any]) -> list[LegislationItem]:
    items: list[LegislationItem] = []
    for row in load_legislations():
        if not _matches_legislation(row, traits_info):
            continue
        items.append(
            LegislationItem(
                code=row["code"],
                title=row["title"],
                family=row["family"],
                legal_form=row.get("legal_form", "Other"),
                priority=row.get("priority", "conditional"),
                applicability=row.get("applicability", "conditional"),
                directive_key=row.get("directive_key", "OTHER"),
                reason=row.get("reason"),
                triggers=row.get("triggers", []),
                doc_impacts=row.get("doc_impacts", []),
                notes=row.get("notes"),
            )
        )

    priority_order = {"core": 0, "product_specific": 1, "conditional": 2, "informational": 3}
    items.sort(key=lambda x: (priority_order.get(x.priority, 9), x.family, x.code))
    return items


def _derive_directives(legislations: list[LegislationItem], standards: list[dict[str, Any]]) -> list[str]:
    found: set[str] = set()
    for item in legislations:
        if item.directive_key:
            found.add(item.directive_key)
    for row in standards:
        if row.get("legislation_key"):
            found.add(row["legislation_key"])
        for directive in row.get("directives", []):
            found.add(directive)
    return sorted(found)


def _convert_standard(row: dict[str, Any]) -> StandardItem:
    directive = row.get("legislation_key") or (row.get("directives", ["OTHER"])[0] if row.get("directives") else "OTHER")
    return StandardItem(
        code=row["code"],
        title=row["title"],
        directive=directive,
        legislation_key=row.get("legislation_key"),
        category=row.get("category", "other"),
        confidence=row.get("confidence", "medium"),
        item_type=row.get("item_type", "standard"),
        match_basis=row.get("match_basis", "traits"),
        score=row.get("score", 0),
        reason=row.get("reason"),
        notes=row.get("notes"),
    )


def _build_missing_information(traits_info: dict[str, Any], legislations: list[LegislationItem]) -> list[str]:
    traits = set(traits_info.get("all_traits", []))
    directive_keys = {x.directive_key for x in legislations}
    missing: list[str] = []

    if not traits_info.get("product_type"):
        missing.append("Exact product type is unclear; identify the closest product family before relying on specific standards.")
    if "electrical" in traits and not ({"mains_powered", "mains_power_likely", "battery_powered", "usb_powered"} & traits):
        missing.append("Power architecture is unclear: mains, battery, USB, detachable PSU, or charger-dependent.")
    if "RED" in directive_keys and not ({"wifi", "bluetooth", "zigbee", "thread", "matter", "nfc", "cellular"} & traits):
        missing.append("Radio technology is unclear; specify Wi-Fi, Bluetooth, Thread, Zigbee, NFC, cellular, or other radio path.")
    if "RED_CYBER" in directive_keys:
        missing.append("Cybersecurity scope needs confirmation: authentication, update path, local/cloud architecture, interfaces, and handled personal data.")
    if "FCM" in directive_keys:
        missing.append("Food-contact materials are not fully described; confirm food path materials, plastics, coatings, elastomers, and supplier declarations.")
    if "ECO" in directive_keys:
        missing.append("Ecodesign scope needs confirmation: off mode, standby, networked standby, display/network functionality, and relevant implementing measure.")
    if "MD" in directive_keys:
        missing.append("Machinery boundary needs confirmation: moving parts, actuation, guards, intended use, and whether the product is machinery or outside scope.")

    seen: set[str] = set()
    deduped: list[str] = []
    for item in missing:
        if item not in seen:
            deduped.append(item)
            seen.add(item)
    return deduped


def _priority_risk(
    traits_info: dict[str, Any],
    review_items: list[StandardItem],
    contradictions: list[str],
    missing_information: list[str],
) -> RiskLevel:
    risk = 0
    if contradictions:
        risk += 2
    if len(missing_information) >= 4:
        risk += 2
    elif missing_information:
        risk += 1
    if any(x.legislation_key == "RED_CYBER" or x.directive == "RED_CYBER" for x in review_items):
        risk += 2
    if traits_info.get("product_match_confidence") == "low":
        risk += 1

    if risk >= 5:
        return "CRITICAL"
    if risk >= 3:
        return "HIGH"
    if risk >= 2:
        return "MEDIUM"
    return "LOW"


def _build_findings(
    legislations: list[LegislationItem],
    standards: list[StandardItem],
    review_items: list[StandardItem],
    missing_information: list[str],
    contradictions: list[str],
) -> list[Finding]:
    findings: list[Finding] = []

    for leg in legislations:
        findings.append(
            Finding(
                directive=leg.directive_key or "OTHER",
                article=leg.code,
                status="PASS" if leg.applicability == "applicable" else "INFO",
                finding=leg.title if not leg.reason else f"{leg.title}. {leg.reason}",
                action="; ".join(leg.doc_impacts[:3]) if leg.doc_impacts else None,
            )
        )

    for item in standards:
        findings.append(
            Finding(
                directive=item.legislation_key or item.directive or "OTHER",
                article=item.code,
                status="PASS",
                finding=item.reason or item.title,
                action=item.notes,
            )
        )

    for item in review_items:
        findings.append(
            Finding(
                directive=item.legislation_key or item.directive or "OTHER",
                article=item.code,
                status="WARN",
                finding=item.reason or item.title,
                action=item.notes,
            )
        )

    for text in missing_information:
        findings.append(Finding(directive="SYSTEM", article="Missing information", status="WARN", finding=text))
    for text in contradictions:
        findings.append(Finding(directive="SYSTEM", article="Contradiction", status="FAIL", finding=text))

    return findings


def _apply_depth_limit(standards: list[StandardItem], review_items: list[StandardItem], depth: str) -> tuple[list[StandardItem], list[StandardItem]]:
    # Standard mode should not silently drop common EMC/RED/RED_CYBER items such as
    # EN IEC 61000-3-2, EN 61000-3-3 or EN 18031-1/-2/-3.
    # Deep mode returns everything.
    if depth == "quick":
        return standards[:24], review_items[:10]
    if depth == "standard":
        return standards[:120], review_items[:40]
    return standards, review_items


def analyze(description: str, category: str = "", directives: list[str] | None = None, depth: str = "standard") -> AnalysisResult:
    directives = directives or []
    traits_info = extract_traits(description=description, category=category)
    legislations = _build_legislation_items(traits_info)

    legislation_keys = [x.directive_key for x in legislations if x.directive_key]
    directive_scope = directives or legislation_keys

    item_rows = find_applicable_items(
        traits=set(traits_info.get("all_traits", [])),
        directives=directive_scope,
        product_type=traits_info.get("product_type"),
        matched_products=traits_info.get("matched_products", []),
    )

    standards = [_convert_standard(x) for x in item_rows["standards"]]
    review_items = [_convert_standard(x) for x in item_rows["review_items"]]
    standards, review_items = _apply_depth_limit(standards, review_items, depth)

    derived_directives = _derive_directives(legislations, item_rows["standards"] + item_rows["review_items"])
    missing_information = _build_missing_information(traits_info, legislations)
    contradictions = traits_info.get("contradictions", [])
    overall_risk = _priority_risk(traits_info, review_items, contradictions, missing_information)
    findings = _build_findings(legislations, standards, review_items, missing_information, contradictions)

    summary_parts: list[str] = []
    if traits_info.get("product_type"):
        summary_parts.append(f"Detected product type: {traits_info['product_type'].replace('_', ' ')}")
    if legislations:
        summary_parts.append("Applicable legislation: " + ", ".join(x.code for x in legislations[:8]))
    if standards or review_items:
        summary_parts.append(f"Matched {len(standards)} standards and {len(review_items)} review items")
    if not summary_parts:
        summary_parts.append("Compliance scoping completed.")

    diagnostics = [
        f"engine_version={APP_VERSION}",
        f"depth={depth}",
        f"product_match_confidence={traits_info.get('product_match_confidence', 'low')}",
        f"returned_standards={len(standards)}",
        f"returned_review_items={len(review_items)}",
    ]

    return AnalysisResult(
        product_summary=description.strip(),
        overall_risk=overall_risk,
        summary=". ".join(summary_parts),
        product_type=traits_info.get("product_type"),
        product_match_confidence=traits_info.get("product_match_confidence", "low"),
        product_candidates=[ProductCandidate(**row) for row in traits_info.get("product_candidates", [])],
        functional_classes=traits_info.get("functional_classes", []),
        explicit_traits=traits_info.get("explicit_traits", []),
        inferred_traits=traits_info.get("inferred_traits", []),
        all_traits=traits_info.get("all_traits", []),
        directives=derived_directives,
        legislations=legislations,
        standards=standards,
        review_items=review_items,
        missing_information=missing_information,
        contradictions=contradictions,
        diagnostics=diagnostics,
        findings=findings,
    )
