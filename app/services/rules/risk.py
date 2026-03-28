from __future__ import annotations

from typing import Literal

from app.domain.models import ConfidenceLevel, ContradictionSeverity, MissingInformationItem, RiskBucketSummary, RiskLevel, RiskReason, RiskSummary, StandardItem


def _risk_reasons(
    *,
    overall_risk: RiskLevel,
    current_risk: RiskLevel,
    future_risk: RiskLevel,
    traits: set[str],
    directives: list[str],
    product_confidence: str,
    contradictions: list[str],
    review_items: list[StandardItem],
    missing_items: list[MissingInformationItem],
) -> list[RiskReason]:
    reasons: list[RiskReason] = []
    seen: set[tuple[str, str]] = set()

    def add(key: str, scope: Literal["overall", "current", "future"], level: RiskLevel, title: str, detail: str) -> None:
        dedupe_key = (scope, key)
        if dedupe_key in seen:
            return
        seen.add(dedupe_key)
        reasons.append(RiskReason(key=key, scope=scope, level=level, title=title, detail=detail))

    if product_confidence == "low":
        add(
            "low_confidence_classification",
            "current",
            "HIGH",
            "Low classification confidence",
            "The product description does not provide enough product-specific evidence to trust the automatic category match.",
        )
        add(
            "low_confidence_classification",
            "overall",
            "HIGH",
            "Low classification confidence",
            "The route should be treated as provisional until the product type is clarified.",
        )

    if contradictions:
        detail = "Conflicting signals were detected: " + _join_readable(contradictions, 2) + "."
        add("contradictions", "current", "HIGH", "Conflicting product signals", detail)
        add("contradictions", "overall", "HIGH", "Conflicting product signals", detail)

    high_missing = [item for item in missing_items if item.importance == "high"]
    if high_missing:
        detail = "Route-critical inputs are still missing: " + _join_readable([item.message for item in high_missing], 2) + "."
        add("missing_information", "current", "HIGH", "Missing route-critical information", detail)
        add("missing_information", "overall", "HIGH", "Missing route-critical information", detail)
    elif missing_items:
        detail = "Some compliance inputs still need clarification: " + _join_readable([item.message for item in missing_items], 2) + "."
        add("missing_information", "current", "MEDIUM", "Missing supporting detail", detail)

    if review_items:
        detail = f"{len(review_items)} standards remain review-dependent rather than fully confirmed."
        add("review_items", "current", "MEDIUM", "Review-dependent standards remain", detail)
        add("review_items", "overall", "MEDIUM", "Review-dependent standards remain", detail)

    if {"radio", "wifi", "bluetooth", "cellular", "thread", "zigbee", "nfc"} & traits:
        detail = "Radio functionality introduces RED evidence, RF exposure, EMC, and cybersecurity scoping questions."
        add("radio", "overall", "MEDIUM", "Radio transmitter or receiver present", detail)
        if {"CRA", "RED_CYBER"} & set(directives):
            add("radio", "future", "HIGH" if future_risk == "HIGH" else "MEDIUM", "Connected radio security exposure", detail)

    if {"mains_powered", "mains_power_likely", "motorized", "pressure"} & traits:
        detail = "Moving parts, mains energy, or pressurized components increase the safety assessment burden."
        add("high_energy", "overall", "MEDIUM", "High-energy or moving components", detail)
        add("high_energy", "current", "MEDIUM", "High-energy or moving components", detail)

    if "food_contact" in traits:
        detail = "Food-contact surfaces can trigger additional materials and hygiene evidence expectations."
        add("food_contact", "overall", "MEDIUM", "Food-contact surfaces", detail)
        add("food_contact", "current", "MEDIUM", "Food-contact surfaces", detail)

    if {"battery_powered", "backup_battery"} & traits:
        detail = "Battery chemistry, capacity, removability, and transport classification can change the obligations profile."
        add("battery", "overall", "MEDIUM", "Battery-powered architecture", detail)
        add("battery", "current", "MEDIUM", "Battery-powered architecture", detail)

    if {"wearable", "body_worn_or_applied", "personal_care"} & traits:
        detail = "Body-contact or near-body use introduces skin-contact, RF exposure, and materials-review questions."
        add("body_contact", "overall", "MEDIUM", "Body-contact or near-body use", detail)
        add("body_contact", "current", "MEDIUM", "Body-contact or near-body use", detail)

    if {"personal_data_likely", "health_related", "biometric", "account", "camera", "microphone", "location"} & traits:
        detail = "Personal or health-related data can expand GDPR, privacy, and connected-device review scope."
        add("personal_health_data", "overall", "MEDIUM", "Personal or health-related data", detail)
        add("personal_health_data", "current", "MEDIUM", "Personal or health-related data", detail)

    if {"cloud", "app_control", "ota", "internet", "account", "authentication"} & traits:
        detail = "Connected software and account features can expand cybersecurity and data-governance obligations."
        add("connected_software", "overall", "MEDIUM", "Connected software surface", detail)
        if {"CRA", "RED_CYBER", "GDPR"} & set(directives):
            add("connected_software", "future", "HIGH" if future_risk == "HIGH" else "MEDIUM", "Connected software surface", detail)

    if {"cloud", "account", "authentication"} & traits:
        detail = "Cloud or account dependency can change cybersecurity, privacy, and service-continuity expectations."
        add("cloud_dependency", "overall", "MEDIUM", "Cloud or account dependency", detail)
        add("cloud_dependency", "current", "MEDIUM", "Cloud or account dependency", detail)

    if {"possible_medical_boundary", "medical_context", "medical_claims"} & traits:
        detail = "The stated use case may sit on the wellness-to-medical boundary and needs intended-purpose review before relying on the route."
        level: RiskLevel = "HIGH" if "medical_claims" in traits else "MEDIUM"
        add("possible_medical_boundary", "overall", level, "Possible medical / wellness boundary", detail)
        add("possible_medical_boundary", "current", level, "Possible medical / wellness boundary", detail)

    if "MACH_REG" in directives:
        add(
            "machinery_future",
            "future",
            "MEDIUM",
            "Future machinery regime",
            "The Machinery Regulation becomes relevant from 20 January 2027 for machinery-style equipment.",
        )
    if "AI_Act" in directives:
        add(
            "ai_future",
            "future",
            "MEDIUM",
            "Future AI review",
            "AI functionality can trigger additional classification and documentation obligations under the AI Act.",
        )

    return reasons


def _join_readable(values: list[str], limit: int = 3) -> str:
    filtered = [value for value in values if value]
    if not filtered:
        return ""
    if len(filtered) <= limit:
        return ", ".join(filtered)
    return ", ".join(filtered[:limit]) + f", +{len(filtered) - limit} more"

def _current_risk(
    product_confidence: ConfidenceLevel,
    contradiction_severity: ContradictionSeverity,
    review_items: list[StandardItem],
    missing_items: list[MissingInformationItem],
) -> RiskLevel:
    if contradiction_severity in {"medium", "high"}:
        return "HIGH"
    if product_confidence == "low":
        return "HIGH"
    if len(review_items) >= 2 or any(item.importance == "high" for item in missing_items):
        return "HIGH"
    if review_items or missing_items:
        return "MEDIUM"
    return "LOW"


def _future_risk(directives: list[str], traits: set[str]) -> RiskLevel:
    if "CRA" in directives and ({"cloud", "internet", "ota", "app_control"} & traits):
        return "HIGH"
    if "AI_Act" in directives or "MACH_REG" in directives:
        return "MEDIUM"
    if "CRA" in directives:
        return "MEDIUM"
    return "LOW"

def _make_risk_summary(
    *,
    overall_risk: RiskLevel,
    current_risk: RiskLevel,
    future_risk: RiskLevel,
    risk_reasons: list[RiskReason],
) -> RiskSummary:
    return RiskSummary(
        overall=RiskBucketSummary(level=overall_risk, reasons=[item for item in risk_reasons if item.scope == "overall"]),
        current=RiskBucketSummary(level=current_risk, reasons=[item for item in risk_reasons if item.scope == "current"]),
        future=RiskBucketSummary(level=future_risk, reasons=[item for item in risk_reasons if item.scope == "future"]),
    )


__all__ = [
    "_current_risk",
    "_future_risk",
    "_join_readable",
    "_make_risk_summary",
    "_risk_reasons",
]
