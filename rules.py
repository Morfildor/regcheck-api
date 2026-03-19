from __future__ import annotations

from datetime import date
from typing import Any

from classifier import extract_traits
from knowledge_base import load_legislations
from models import AnalysisResult, Finding, LegislationItem, StandardItem
from standards_engine import find_applicable_items

TODAY = date.today()


def _parse_date(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


def _matches_conditions(row: dict[str, Any], all_traits: set[str], functional_classes: set[str], product_type: str | None) -> bool:
    def _all(values: list[str], haystack: set[str]) -> bool:
        return not values or set(values).issubset(haystack)

    def _any(values: list[str], haystack: set[str]) -> bool:
        return not values or bool(set(values) & haystack)

    def _none(values: list[str], haystack: set[str]) -> bool:
        return not bool(set(values) & haystack)

    if not _all(row.get("all_of_traits", []), all_traits):
        return False
    if not _any(row.get("any_of_traits", []), all_traits):
        return False
    if not _none(row.get("none_of_traits", []), all_traits):
        return False

    if not _all(row.get("all_of_functional_classes", []), functional_classes):
        return False
    if not _any(row.get("any_of_functional_classes", []), functional_classes):
        return False
    if not _none(row.get("none_of_functional_classes", []), functional_classes):
        return False

    any_products = row.get("any_of_product_types", [])
    if any_products and product_type not in any_products:
        return False
    if product_type and product_type in set(row.get("exclude_product_types", [])):
        return False

    return True


def _timing_status(row: dict[str, Any], today: date) -> str:
    applicable_from = _parse_date(row.get("applicable_from"))
    applicable_until = _parse_date(row.get("applicable_until"))
    bucket = row.get("bucket", "non_ce")

    if bucket == "informational":
        return "informational"
    if applicable_from and today < applicable_from:
        return "future"
    if applicable_until and today > applicable_until:
        return "legacy"
    return "current"


def _build_legislation_reason(row: dict[str, Any], timing_status: str) -> str:
    base = row.get("reason") or "Potentially relevant based on detected traits and product class."
    if timing_status == "future" and row.get("applicable_from"):
        base += f" Applies from {row['applicable_from']}."
    if timing_status == "legacy" and row.get("applicable_until"):
        base += f" Legacy route only up to {row['applicable_until']}."
    if row.get("replaced_by"):
        base += f" Superseded or complemented by {row['replaced_by']}."
    return base


def _pick_legislations(all_traits: set[str], functional_classes: set[str], product_type: str | None) -> list[dict[str, Any]]:
    picked: list[dict[str, Any]] = []
    for row in load_legislations():
        if not _matches_conditions(row, all_traits, functional_classes, product_type):
            continue
        enriched = dict(row)
        enriched["timing_status"] = _timing_status(row, TODAY)
        enriched["reason"] = _build_legislation_reason(row, enriched["timing_status"])
        picked.append(enriched)

    picked.sort(
        key=lambda x: (
            {"ce": 0, "framework": 1, "non_ce": 2, "future": 3, "informational": 4}.get(x.get("bucket", "non_ce"), 9),
            {"core": 0, "product_specific": 1, "conditional": 2, "informational": 3}.get(x.get("priority", "conditional"), 9),
            x.get("code", ""),
        )
    )
    return picked


def _directive_keys_for_matching(legislations: list[dict[str, Any]], forced: list[str]) -> list[str]:
    keys = {row["directive_key"] for row in legislations if row.get("directive_key")}
    keys.update(forced or [])
    return sorted(keys)


def _annotate_standard_items(rows: list[dict[str, Any]], legislation_index: dict[str, dict[str, Any]]) -> list[StandardItem]:
    out: list[StandardItem] = []
    for row in rows:
        lookup_key = row.get("legislation_key") or row.get("directive")
        leg = legislation_index.get(lookup_key) if isinstance(lookup_key, str) and lookup_key else None
        enriched = dict(row)
        if leg:
            enriched["regime_bucket"] = leg.get("bucket")
            enriched["timing_status"] = leg.get("timing_status", "current")
        out.append(StandardItem(
            code=enriched["code"],
            title=enriched["title"],
            directive=(enriched.get("directives") or [enriched.get("legislation_key") or "OTHER"])[0],
            legislation_key=enriched.get("legislation_key"),
            category=enriched["category"],
            confidence=enriched.get("confidence", "medium"),
            item_type=enriched.get("item_type", "standard"),
            match_basis=enriched.get("match_basis", "traits"),
            score=enriched.get("score", 0),
            reason=enriched.get("reason"),
            notes=enriched.get("notes"),
            regime_bucket=enriched.get("regime_bucket"),
            timing_status=enriched.get("timing_status", "current"),
        ))
    return out


def _missing_information(all_traits: set[str], product_type: str | None, contradictions: list[str]) -> list[str]:
    missing: list[str] = []
    if not product_type:
        missing.append("Exact product type is unclear; provide the commercial product description or product family.")
    if "electrical" in all_traits and not ({"mains_powered", "battery_powered", "usb_powered", "mains_power_likely"} & all_traits):
        missing.append("Power source is unclear; specify mains, battery, USB, or external PSU.")
    if "radio" in all_traits and not ({"wifi", "bluetooth", "zigbee", "thread", "matter", "nfc", "cellular"} & all_traits):
        missing.append("Radio technology is unclear; specify Wi-Fi, Bluetooth, Thread, Zigbee, NFC, or cellular.")
    if "food_contact" in all_traits:
        missing.append("Confirm whether food-contact parts include plastic, coating, rubber, silicone, paper, or metal materials.")
    if contradictions:
        missing.append("Resolve contradictory product signals before relying on the output for compliance decisions.")
    return missing


def _findings(legislations: list[dict[str, Any]], review_items: list[StandardItem], missing_information: list[str]) -> list[Finding]:
    findings: list[Finding] = []

    for row in legislations:
        status = "INFO"
        if row["bucket"] == "future":
            status = "WARN"
        elif row["bucket"] in {"ce", "non_ce", "framework"}:
            status = "PASS" if row["timing_status"] == "current" else "WARN"

        findings.append(
            Finding(
                directive=row["directive_key"],
                article="Scope",
                status=status,
                finding=row["title"],
                action=row.get("reason"),
            )
        )

    for item in review_items[:8]:
        findings.append(
            Finding(
                directive=item.directive,
                article="Review",
                status="WARN",
                finding=item.title,
                action=item.reason or item.notes,
            )
        )

    for note in missing_information:
        findings.append(
            Finding(
                directive="INPUT",
                article="Missing information",
                status="WARN",
                finding=note,
            )
        )

    return findings


def analyze(description: str, category: str = "", directives: list[str] | None = None, depth: str = "standard") -> AnalysisResult:
    classification = extract_traits(description=description, category=category)
    all_traits = set(classification["all_traits"])
    functional_classes = set(classification["functional_classes"])
    product_type = classification["product_type"]

    picked_legislations = _pick_legislations(
        all_traits=all_traits,
        functional_classes=functional_classes,
        product_type=product_type,
    )

    directive_keys = _directive_keys_for_matching(picked_legislations, directives or [])
    applicable_items = find_applicable_items(
        traits=all_traits,
        directives=directive_keys,
        product_type=product_type,
        matched_products=classification.get("matched_products", []),
    )

    legislation_index = {row["directive_key"]: row for row in picked_legislations}
    standards = _annotate_standard_items(applicable_items["standards"], legislation_index)
    review_items = _annotate_standard_items(applicable_items["review_items"], legislation_index)

    ce_legislations = [LegislationItem(**row) for row in picked_legislations if row["bucket"] == "ce"]
    non_ce_obligations = [LegislationItem(**row) for row in picked_legislations if row["bucket"] == "non_ce"]
    framework_regimes = [LegislationItem(**row) for row in picked_legislations if row["bucket"] == "framework"]
    future_regimes = [LegislationItem(**row) for row in picked_legislations if row["bucket"] == "future"]
    informational_items = [LegislationItem(**row) for row in picked_legislations if row["bucket"] == "informational"]

    missing_information = _missing_information(all_traits, product_type, classification["contradictions"])

    overall_risk = "LOW"
    if classification["contradictions"] or missing_information:
        overall_risk = "MEDIUM"
    if future_regimes or any(item.item_type == "review" for item in review_items):
        overall_risk = "HIGH" if missing_information else "MEDIUM"

    summary_parts = []
    if product_type:
        summary_parts.append(f"Detected product type: {product_type.replace('_', ' ')}.")
    if ce_legislations:
        summary_parts.append("Current CE harmonisation acts are separated from non-CE obligations.")
    if non_ce_obligations:
        summary_parts.append("Parallel non-CE obligations were identified separately.")
    if framework_regimes:
        summary_parts.append("Framework or product-family regimes need a separate product-specific check.")
    if future_regimes:
        summary_parts.append("Future regimes are flagged separately and not merged into current obligations.")

    return AnalysisResult(
        product_summary=description.strip() or category.strip() or "Product analysis",
        overall_risk=overall_risk,
        summary=" ".join(summary_parts) or "Regulatory scoping completed.",
        product_type=product_type,
        product_match_confidence=classification["product_match_confidence"],
        product_candidates=classification["product_candidates"],
        functional_classes=classification["functional_classes"],
        explicit_traits=classification["explicit_traits"],
        inferred_traits=classification["inferred_traits"],
        all_traits=classification["all_traits"],
        directives=directive_keys,
        legislations=[LegislationItem(**row) for row in picked_legislations],
        ce_legislations=ce_legislations,
        non_ce_obligations=non_ce_obligations,
        framework_regimes=framework_regimes,
        future_regimes=future_regimes,
        informational_items=informational_items,
        standards=standards,
        review_items=review_items,
        missing_information=missing_information,
        contradictions=classification["contradictions"],
        diagnostics=[f"analysis_date={TODAY.isoformat()}", f"depth={depth}"],
        findings=_findings(picked_legislations, review_items, missing_information),
    )
