from models import AnalysisResult, Finding, RiskLevel, StandardItem, Status
from classifier import extract_traits
from standards_engine import find_applicable_standards


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

    if (
        "electronic" in traits
        or "radio" in traits
        or "app_control" in traits
        or "cloud" in traits
        or "internet" in traits
        or "ota" in traits
        or "authentication" in traits
        or "account" in traits
        or "data_storage" in traits
    ):
        directives.add("CRA")

    if (
        "personal_data_likely" in traits
        or "camera" in traits
        or "microphone" in traits
        or "location" in traits
        or "health_related" in traits
        or "child_targeted" in traits
        or "account" in traits
    ):
        directives.add("GDPR")

    if "ai_related" in traits:
        directives.add("AI_Act")

    if "electrical" in traits or "electronic" in traits or "radio" in traits:
        directives.add("EMC")

    if "electrical" in traits or "mains_powered" in traits or "mains_power_likely" in traits or "heating" in traits:
        directives.add("LVD")

    return sorted(directives)


def derive_overall_risk(findings: list[Finding], contradictions: list[str]) -> RiskLevel:
    fail_count = sum(1 for f in findings if f.status == "FAIL")
    warn_count = sum(1 for f in findings if f.status == "WARN")

    if fail_count >= 3:
        return "CRITICAL"
    if fail_count >= 1 or len(contradictions) >= 2:
        return "HIGH"
    if warn_count >= 3 or len(contradictions) == 1:
        return "MEDIUM"
    return "LOW"


def build_summary(
    product_type: str | None,
    directives: list[str],
    standards: list[StandardItem],
    missing_information: list[str],
    contradictions: list[str],
) -> str:
    product_text = product_type.replace("_", " ") if product_type else "product"
    parts = [
        f"Likely compliance screening completed for {product_text}.",
        f"{len(directives)} likely directive(s) inferred.",
        f"{len(standards)} likely standard or review item(s) identified.",
    ]

    if missing_information:
        parts.append(f"{len(missing_information)} key information gap(s) still affect the result.")

    if contradictions:
        parts.append("Some contradictory signals were found in the description, so assumptions should be confirmed.")

    return " ".join(parts)


def analyze(description: str, category: str, directives: list[str], depth: str) -> dict:
    findings: list[Finding] = []

    classification = extract_traits(description, category)
    product_type = classification["product_type"]
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
        f"Match confidence: {product_match_confidence}. Add more product detail if the classification looks wrong.",
    )

    if len(matched_products) > 1:
        add_finding(
            findings,
            "SYSTEM",
            "Alternative product candidates",
            "INFO",
            "Other possible product matches: " + ", ".join(x.replace("_", " ") for x in matched_products[1:4]) + ".",
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

    standards: list[StandardItem] = []
    matched_standard_rows = find_applicable_standards(
        traits_set,
        inferred_directives,
        product_type=product_type,
        matched_products=matched_products,
    )

    for std in matched_standard_rows:
        primary_directive = std.get("directives", ["SYSTEM"])[0] if std.get("directives") else "SYSTEM"

        standards.append(
            StandardItem(
                code=std.get("code", "Unknown standard"),
                title=std.get("title", ""),
                directive=primary_directive,
                category=std.get("category", "general"),
                confidence=std.get("confidence", "medium"),
                reason=std.get("reason"),
                notes=std.get("notes"),
            )
        )

        add_finding(
            findings,
            ", ".join(std.get("directives", [])) or "SYSTEM",
            std.get("code", "Standard"),
            "INFO",
            f"{std.get('code')}: {std.get('title')}",
            std.get("reason") or std.get("notes"),
        )

    missing_information: list[str] = []

    if product_type == "electric_kettle" and "mains_powered" not in traits_set and "mains_power_likely" in traits_set:
        missing_information.append("Rated voltage or power architecture was not explicitly stated.")
        add_finding(
            findings,
            "LVD",
            "Missing power architecture detail",
            "WARN",
            "Product looks like a mains-powered household heating appliance, but rated voltage or power architecture was not explicitly stated.",
            "Confirm rated voltage, supply method, and power characteristics.",
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

    if not standards:
        add_finding(
            findings,
            "SYSTEM",
            "No standards matched",
            "WARN",
            "No likely standards were matched from the current traits, product match, and directives.",
            "Expand the product description or add more archetypes and standards to the YAML database.",
        )

    overall_risk = derive_overall_risk(findings, contradictions)
    summary = build_summary(
        product_type=product_type,
        directives=inferred_directives,
        standards=standards,
        missing_information=missing_information,
        contradictions=contradictions,
    )

    result = AnalysisResult(
        product_summary=description[:90] + "..." if len(description) > 90 else description,
        overall_risk=overall_risk,
        summary=summary,
        product_type=product_type,
        functional_classes=functional_classes,
        explicit_traits=explicit_traits,
        inferred_traits=inferred_traits,
        all_traits=all_traits,
        directives=inferred_directives,
        standards=standards,
        missing_information=missing_information,
        contradictions=contradictions,
        findings=findings,
    )

    return result.model_dump()
