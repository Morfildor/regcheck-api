from __future__ import annotations

from models import AnalysisResult, Finding, ProductCandidate, RiskLevel, StandardItem, Status
from classifier import extract_traits
from standards_engine import find_applicable_items


def add_finding(
    findings: list[Finding],
    directive: str,
    article: str,
    status: Status,
    finding: str,
    action: str | None = None,
) -> None:
    findings.append(
        Finding(
            directive=directive,
            article=article,
            status=status,
            finding=finding,
            action=action,
        )
    )


def infer_directives(traits: set[str], requested_directives: list[str]) -> list[str]:
    directives = set(requested_directives or [])

    if "radio" in traits:
        directives.add("RED")

    if {
        "electronic", "radio", "app_control", "cloud", "internet", "ota",
        "authentication", "account", "data_storage",
    } & traits:
        directives.add("CRA")

    if {
        "personal_data_likely", "camera", "microphone", "location",
        "health_related", "child_targeted", "account",
    } & traits:
        directives.add("GDPR")

    if "ai_related" in traits:
        directives.add("AI_Act")

    if {"electrical", "electronic", "radio"} & traits:
        directives.add("EMC")

    if {"electrical", "mains_powered", "mains_power_likely", "heating"} & traits:
        directives.add("LVD")

    return sorted(directives)


def derive_overall_risk(findings: list[Finding], contradictions: list[str], missing_information: list[str]) -> RiskLevel:
    fail_count = sum(1 for f in findings if f.status == "FAIL")
    warn_count = sum(1 for f in findings if f.status == "WARN")

    if fail_count >= 3:
        return "CRITICAL"
    if fail_count >= 1 or len(contradictions) >= 2:
        return "HIGH"
    if warn_count >= 3 or len(contradictions) == 1 or len(missing_information) >= 3:
        return "MEDIUM"
    return "LOW"


def build_summary(
    product_type: str | None,
    directives: list[str],
    standards: list[StandardItem],
    review_items: list[StandardItem],
    missing_information: list[str],
    contradictions: list[str],
) -> str:
    product_text = product_type.replace("_", " ") if product_type else "product"
    parts = [
        f"Compliance screening completed for {product_text}.",
        f"{len(directives)} likely directive(s) inferred.",
        f"{len(standards)} likely standard(s) identified.",
    ]

    if review_items:
        parts.append(f"{len(review_items)} review item(s) still need manual route selection.")

    if missing_information:
        parts.append(f"{len(missing_information)} key information gap(s) still affect the result.")

    if contradictions:
        parts.append("Some contradictory signals were found and should be clarified.")

    return " ".join(parts)


def analyze(description: str, category: str, directives: list[str], depth: str) -> dict:
    findings: list[Finding] = []
    diagnostics: list[str] = []

    classification = extract_traits(description, category)
    product_type = classification["product_type"]
    product_candidates_raw = classification.get("product_candidates", [])
    matched_products = classification.get("matched_products", [])
    product_match_confidence = classification.get("product_match_confidence", "low")
    functional_classes = classification["functional_classes"]
    explicit_traits = classification["explicit_traits"]
    inferred_traits = classification["inferred_traits"]
    all_traits = classification["all_traits"]
    contradictions = classification["contradictions"]

    traits_set = set(all_traits)
    inferred_directives = infer_directives(traits_set, directives)

    add_finding(
        findings,
        "SYSTEM",
        "Product interpretation",
        "INFO",
        f"Detected product type: {product_type.replace('_', ' ') if product_type else 'not confidently identified'}.",
        f"Match confidence: {product_match_confidence}. Add more concrete product detail if the classification looks wrong.",
    )

    if product_candidates_raw:
        top = product_candidates_raw[0]
        diagnostics.append(
            f"Top product candidate '{top['id']}' matched alias '{top.get('matched_alias')}' with score {top['score']}."
        )

    if len(product_candidates_raw) > 1:
        alt_text = ", ".join(
            f"{x['id'].replace('_', ' ')} ({x['confidence']})" for x in product_candidates_raw[1:4]
        )
        add_finding(
            findings,
            "SYSTEM",
            "Alternative product candidates",
            "INFO",
            f"Other possible product matches: {alt_text}.",
            "Tighten the description if the top product match looks wrong.",
        )

    if explicit_traits:
        add_finding(
            findings,
            "SYSTEM",
            "Explicit signals",
            "INFO",
            f"Explicitly detected traits: {', '.join(explicit_traits)}.",
            None,
        )

    if inferred_traits:
        add_finding(
            findings,
            "SYSTEM",
            "Inferred signals",
            "INFO",
            f"Inferred traits from product type or context: {', '.join(inferred_traits)}.",
            "Confirm inferred assumptions if they affect compliance scope.",
        )

    for contradiction in contradictions:
        add_finding(
            findings,
            "SYSTEM",
            "Contradiction check",
            "WARN",
            contradiction,
            "Clarify the product description to improve standards matching.",
        )

    matched = find_applicable_items(
        traits=traits_set,
        directives=inferred_directives,
        product_type=product_type,
        matched_products=matched_products,
    )

    standards: list[StandardItem] = []
    review_items: list[StandardItem] = []

    for bucket_name, rows in (("standard", matched["standards"]), ("review", matched["review_items"])):
        for row in rows:
            primary_directive = row.get("directives", ["SYSTEM"])[0] if row.get("directives") else "SYSTEM"
            item = StandardItem(
                code=row.get("code", "Unknown item"),
                title=row.get("title", ""),
                directive=primary_directive,
                category=row.get("category", "general"),
                confidence=row.get("confidence", "medium"),
                item_type=row.get("item_type", bucket_name),
                match_basis=row.get("match_basis", "traits"),
                score=row.get("score", 0),
                reason=row.get("reason"),
                notes=row.get("notes"),
            )
            if bucket_name == "standard":
                standards.append(item)
            else:
                review_items.append(item)

            add_finding(
                findings,
                ", ".join(row.get("directives", [])) or "SYSTEM",
                row.get("code", "Item"),
                "INFO",
                f"{row.get('code')}: {row.get('title')}",
                row.get("reason") or row.get("notes"),
            )

    missing_information: list[str] = []

    if product_match_confidence == "low":
        missing_information.append("Product family is not confidently identified from the current description.")

    if not product_type:
        missing_information.append("Product type is not clear enough to apply product-specific standards reliably.")

    if "mains_power_likely" in traits_set and "mains_powered" not in traits_set and "battery_powered" not in traits_set:
        missing_information.append("Power architecture was not explicitly stated.")
        add_finding(
            findings,
            "LVD",
            "Missing power architecture detail",
            "WARN",
            "Power architecture looks relevant, but mains/battery supply was not explicitly stated.",
            "Confirm rated voltage, supply method, and charger/adapter architecture.",
        )

    if "radio" in traits_set and not any(x in traits_set for x in ["wifi", "bluetooth", "cellular", "zigbee", "thread", "nfc"]):
        missing_information.append("Radio technology was not clearly identified.")
        add_finding(
            findings,
            "RED",
            "Missing radio detail",
            "WARN",
            "Radio functionality appears relevant, but the radio technology was not clearly identified.",
            "Specify whether the product uses Wi-Fi, Bluetooth, Zigbee, Thread, NFC, cellular, or another radio technology.",
        )

    if (
        "personal_data_likely" in traits_set
        and "account" not in traits_set
        and "cloud" not in traits_set
        and "local_only" not in traits_set
    ):
        missing_information.append("Data storage, transfer, and access architecture are not clear.")
        add_finding(
            findings,
            "GDPR",
            "Missing privacy architecture detail",
            "WARN",
            "Personal-data relevance is likely, but storage, transfer, and access architecture are not clear from the description.",
            "Clarify what personal data is collected, where it is stored, who can access it, and whether cloud services are involved.",
        )

    if not standards and review_items:
        diagnostics.append("Only review items matched; no concrete standard route was strong enough.")
    if not standards and not review_items:
        add_finding(
            findings,
            "SYSTEM",
            "No items matched",
            "WARN",
            "No likely standards or review items were matched from the current traits, product match, and directives.",
            "Expand the product description or tighten the YAML catalogue and standards coverage.",
        )

    overall_risk = derive_overall_risk(findings, contradictions, missing_information)
    summary = build_summary(
        product_type=product_type,
        directives=inferred_directives,
        standards=standards,
        review_items=review_items,
        missing_information=missing_information,
        contradictions=contradictions,
    )

    result = AnalysisResult(
        product_summary=description[:90] + "..." if len(description) > 90 else description,
        overall_risk=overall_risk,
        summary=summary,
        product_type=product_type,
        product_match_confidence=product_match_confidence,
        product_candidates=[ProductCandidate(**row) for row in product_candidates_raw],
        functional_classes=functional_classes,
        explicit_traits=explicit_traits,
        inferred_traits=inferred_traits,
        all_traits=all_traits,
        directives=inferred_directives,
        standards=standards,
        review_items=review_items,
        missing_information=missing_information,
        contradictions=contradictions,
        diagnostics=diagnostics,
        findings=findings,
    )

    return result.model_dump()
