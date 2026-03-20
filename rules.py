from __future__ import annotations

from datetime import date
from typing import Any

from classifier import extract_traits
from knowledge_base import load_legislations, load_meta
from models import AnalysisResult, AnalysisStats, Finding, KnowledgeBaseMeta, LegislationItem, MissingInformationItem, StandardItem
from standards_engine import find_applicable_items

TODAY = date.today()


BUCKET_SORT = {"ce": 0, "framework": 1, "non_ce": 2, "future": 3, "informational": 4}
PRIORITY_SORT = {"core": 0, "product_specific": 1, "conditional": 2, "informational": 3}
SECTION_ORDER = ["harmonized", "state_of_the_art", "review", "unknown"]
SECTION_TITLES = {
    "harmonized": "Harmonized standards",
    "state_of_the_art": "State of the art / latest technical route",
    "review": "Review-required routes",
    "unknown": "Other standards",
}
LEG_SECTION_TITLES = {
    "ce": "CE legislations",
    "framework": "Framework regimes",
    "non_ce": "Parallel obligations",
    "future": "Future regimes",
    "informational": "Informational items",
}


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
            BUCKET_SORT.get(x.get("bucket", "non_ce"), 9),
            PRIORITY_SORT.get(x.get("priority", "conditional"), 9),
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

        harmonization_status = enriched.get("harmonization_status", "unknown")
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
            matched_traits_all=enriched.get("matched_traits_all", []),
            matched_traits_any=enriched.get("matched_traits_any", []),
            missing_required_traits=enriched.get("missing_required_traits", []),
            excluded_by_traits=enriched.get("excluded_by_traits", []),
            applies_if_products=enriched.get("applies_if_products", []),
            exclude_if_products=enriched.get("exclude_if_products", []),
            product_match_type=enriched.get("product_match_type"),
            standard_family=enriched.get("standard_family"),
            is_harmonized=enriched.get("is_harmonized"),
            harmonized_under=enriched.get("harmonized_under"),
            harmonization_status=harmonization_status,
            harmonized_reference=enriched.get("harmonized_reference"),
            version=enriched.get("version"),
            dated_version=enriched.get("dated_version"),
            supersedes=enriched.get("supersedes"),
            test_focus=enriched.get("test_focus", []),
            evidence_hint=enriched.get("evidence_hint", []),
            keywords=enriched.get("keywords", []),
        ))
    return out


def _missing_information_items(
    all_traits: set[str],
    product_type: str | None,
    contradictions: list[str],
    contradiction_severity: str,
) -> list[MissingInformationItem]:
    items: list[MissingInformationItem] = []

    if not product_type:
        items.append(MissingInformationItem(
            key="product_type",
            message="Exact product type is unclear; provide the commercial product description or product family.",
            importance="high",
            examples=["air fryer", "robot vacuum cleaner", "built-in induction hob"],
        ))
    if "electrical" in all_traits and not ({"mains_powered", "battery_powered", "usb_powered", "mains_power_likely"} & all_traits):
        items.append(MissingInformationItem(
            key="power_source",
            message="Power source is unclear; specify mains, battery, USB, or external PSU.",
            importance="high",
            examples=["230 V mains", "rechargeable Li-ion battery", "USB-C powered"],
            related_traits=["mains_powered", "battery_powered", "usb_powered"],
        ))
    if "radio" in all_traits and not ({"wifi", "bluetooth", "zigbee", "thread", "matter", "nfc", "cellular"} & all_traits):
        items.append(MissingInformationItem(
            key="radio_technology",
            message="Radio technology is unclear; specify Wi-Fi, Bluetooth, Thread, Zigbee, NFC, or cellular.",
            importance="high",
            examples=["Wi-Fi 2.4 GHz", "Bluetooth LE", "Zigbee"],
            related_traits=["radio"],
        ))
    if "food_contact" in all_traits:
        items.append(MissingInformationItem(
            key="food_contact_materials",
            message="Confirm whether food-contact parts include plastic, coating, rubber, silicone, paper, or metal materials.",
            importance="medium",
            examples=["PA plastic water tank", "silicone seal", "non-stick coating"],
            related_traits=["food_contact"],
        ))
    if "cloud" in all_traits or "internet" in all_traits or "app_control" in all_traits:
        items.append(MissingInformationItem(
            key="connectivity_architecture",
            message="Clarify whether the product requires cloud, user accounts, local LAN control, or OTA updates.",
            importance="medium",
            examples=["local LAN only", "cloud account required", "OTA security patching supported"],
            related_traits=["cloud", "internet", "app_control", "ota"],
        ))
    if contradiction_severity in {"medium", "high"} or contradictions:
        items.append(MissingInformationItem(
            key="contradictions",
            message="Resolve contradictory product signals before relying on the output for compliance decisions.",
            importance="high",
            examples=contradictions[:3],
        ))

    return items


def _build_standard_sections(standards: list[StandardItem], review_items: list[StandardItem]) -> list[dict[str, Any]]:
    grouped: dict[str, dict[str, Any]] = {}
    for item in [*standards, *review_items]:
        status = item.harmonization_status or ("review" if item.item_type == "review" else "unknown")
        if status not in SECTION_TITLES:
            status = "unknown"
        section = grouped.setdefault(status, {
            "key": status,
            "title": SECTION_TITLES[status],
            "count": 0,
            "items": [],
        })
        section["items"].append({
            "code": item.code,
            "title": item.title,
            "directive": item.directive,
            "legislation_key": item.legislation_key,
            "category": item.category,
            "item_type": item.item_type,
            "confidence": item.confidence,
            "reason": item.reason,
            "notes": item.notes,
            "standard_family": item.standard_family,
            "is_harmonized": item.is_harmonized,
            "harmonized_under": item.harmonized_under,
            "harmonized_reference": item.harmonized_reference,
            "harmonization_status": item.harmonization_status,
            "version": item.version,
            "dated_version": item.dated_version,
            "supersedes": item.supersedes,
            "applies_if_products": item.applies_if_products,
            "match_basis": item.match_basis,
            "product_match_type": item.product_match_type,
            "test_focus": item.test_focus,
            "evidence_hint": item.evidence_hint,
            "keywords": item.keywords,
        })
    for section in grouped.values():
        section["items"].sort(key=lambda x: (x["directive"], x["code"]))
        section["count"] = len(section["items"])
    return [grouped[key] for key in SECTION_ORDER if key in grouped]


def _build_legislation_sections(legislations: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, dict[str, Any]] = {}
    for row in legislations:
        bucket = row.get("bucket", "non_ce")
        section = grouped.setdefault(bucket, {
            "key": bucket,
            "title": LEG_SECTION_TITLES.get(bucket, bucket.title()),
            "count": 0,
            "items": [],
        })
        section["items"].append({
            "code": row.get("code"),
            "title": row.get("title"),
            "family": row.get("family"),
            "directive_key": row.get("directive_key"),
            "priority": row.get("priority"),
            "applicability": row.get("applicability"),
            "timing_status": row.get("timing_status"),
            "reason": row.get("reason"),
            "notes": row.get("notes"),
            "applicable_from": row.get("applicable_from"),
            "applicable_until": row.get("applicable_until"),
        })
    for section in grouped.values():
        section["items"].sort(key=lambda x: (x["directive_key"], x["code"]))
        section["count"] = len(section["items"])
    return [grouped[key] for key in ["ce", "framework", "non_ce", "future", "informational"] if key in grouped]


def _findings(
    legislations: list[dict[str, Any]],
    standards: list[StandardItem],
    review_items: list[StandardItem],
    missing_information_items: list[MissingInformationItem],
    contradictions: list[str],
) -> list[Finding]:
    findings: list[Finding] = []

    for row in legislations:
        status = "INFO"
        if row["bucket"] == "future":
            status = "WARN"
        elif row["bucket"] in {"ce", "non_ce", "framework"}:
            status = "PASS" if row["timing_status"] == "current" else "WARN"

        findings.append(
            Finding(
                directive=row.get("directive_key", "OTHER"),
                article=row["code"],
                status=status,
                finding=row["title"],
                action=row.get("reason"),
            )
        )

    for item in standards:
        findings.append(
            Finding(
                directive=item.directive or item.legislation_key or "OTHER",
                article=item.code,
                status="PASS" if item.harmonization_status == "harmonized" else "INFO",
                finding=item.title,
                action=item.reason or item.notes,
            )
        )

    for item in review_items:
        findings.append(
            Finding(
                directive=item.directive or item.legislation_key or "OTHER",
                article=item.code,
                status="WARN",
                finding=item.title,
                action=item.reason or item.notes,
            )
        )

    for item in missing_information_items:
        findings.append(
            Finding(
                directive="INPUT",
                article=f"Missing: {item.key}",
                status="WARN",
                finding=item.message,
                action=("Examples: " + "; ".join(item.examples)) if item.examples else None,
            )
        )

    for contradiction in contradictions:
        findings.append(
            Finding(
                directive="INPUT",
                article="Contradiction",
                status="WARN",
                finding=contradiction,
            )
        )

    return findings


def _diagnostics(
    depth: str,
    classification: dict[str, Any],
    picked_legislations: list[dict[str, Any]],
    applicable_items: dict[str, Any],
) -> list[str]:
    diagnostics = [f"analysis_date={TODAY.isoformat()}", f"depth={depth}"]
    diagnostics.extend(classification.get("diagnostics", []))
    diagnostics.append("legislation_keys=" + ",".join(sorted({row["directive_key"] for row in picked_legislations if row.get("directive_key")})))
    diagnostics.append(f"standard_hits={len(applicable_items.get('standards', []))}")
    diagnostics.append(f"review_hits={len(applicable_items.get('review_items', []))}")
    diagnostics.append(f"rejections={len(applicable_items.get('rejections', []))}")
    for rejection in applicable_items.get("rejections", [])[:10]:
        code = rejection.get("code") or "unknown"
        reason = rejection.get("reason") or "rejected"
        diagnostics.append(f"rejected:{code}:{reason}")
    return diagnostics


def _stats(
    picked_legislations: list[dict[str, Any]],
    standards: list[StandardItem],
    review_items: list[StandardItem],
    missing_information_items: list[MissingInformationItem],
    contradictions: list[str],
) -> AnalysisStats:
    return AnalysisStats(
        legislation_count=len(picked_legislations),
        current_legislation_count=sum(1 for row in picked_legislations if row.get("timing_status") == "current"),
        future_legislation_count=sum(1 for row in picked_legislations if row.get("timing_status") == "future"),
        standards_count=len(standards),
        review_items_count=len(review_items),
        harmonized_standards_count=sum(1 for row in standards if row.harmonization_status == "harmonized"),
        state_of_the_art_standards_count=sum(1 for row in standards if row.harmonization_status == "state_of_the_art"),
        product_gated_standards_count=sum(1 for row in standards if row.applies_if_products),
        ambiguity_flag_count=len(contradictions),
        missing_information_count=len(missing_information_items),
    )


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

    contradiction_severity = classification.get("contradiction_severity", "none")
    missing_information_items = _missing_information_items(
        all_traits,
        product_type,
        classification["contradictions"],
        contradiction_severity,
    )
    missing_information = [item.message for item in missing_information_items]

    overall_risk = "LOW"
    if contradiction_severity == "high":
        overall_risk = "CRITICAL"
    elif contradiction_severity == "medium" or missing_information:
        overall_risk = "MEDIUM"
    if future_regimes or review_items:
        overall_risk = "HIGH" if overall_risk in {"MEDIUM", "CRITICAL"} or missing_information else "MEDIUM"
    if contradiction_severity == "high":
        overall_risk = "CRITICAL"

    summary_parts = []
    if product_type:
        summary_parts.append(f"Detected product type: {product_type.replace('_', ' ')}.")
    else:
        summary_parts.append("Product type could not be identified with confidence.")
    if ce_legislations:
        summary_parts.append("Current CE harmonisation acts are separated from non-CE obligations.")
    if non_ce_obligations:
        summary_parts.append("Parallel non-CE obligations were identified separately.")
    if framework_regimes:
        summary_parts.append("Framework or product-family regimes need a separate product-specific check.")
    if future_regimes:
        summary_parts.append("Future regimes are flagged separately and not merged into current obligations.")
    if any(item.harmonization_status == "harmonized" for item in standards):
        summary_parts.append("Harmonized standards are tagged separately from state-of-the-art routes.")
    if contradiction_severity in {"medium", "high"}:
        summary_parts.append("Input contradictions reduce confidence and need resolution.")

    kb_meta = KnowledgeBaseMeta(**load_meta())
    standard_sections = _build_standard_sections(standards, review_items)
    legislation_sections = _build_legislation_sections(picked_legislations)

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
        missing_information_items=missing_information_items,
        contradictions=classification["contradictions"],
        contradiction_severity=contradiction_severity,
        diagnostics=_diagnostics(depth, classification, picked_legislations, applicable_items),
        stats=_stats(picked_legislations, standards, review_items, missing_information_items, classification["contradictions"]),
        knowledge_base_meta=kb_meta,
        standard_sections=standard_sections,
        legislation_sections=legislation_sections,
        findings=_findings(picked_legislations, standards, review_items, missing_information_items, classification["contradictions"]),
    )
