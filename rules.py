from __future__ import annotations

from datetime import date
from typing import Any

from classifier import extract_traits
from knowledge_base import load_legislations, load_meta
from models import (
    AnalysisResult,
    AnalysisStats,
    Finding,
    KnowledgeBaseMeta,
    LegislationItem,
    MissingInformationItem,
    StandardItem,
)
from standards_engine import find_applicable_items

BUCKET_SORT = {"ce": 0, "framework": 1, "non_ce": 2, "future": 3, "informational": 4}
PRIORITY_SORT = {"core": 0, "product_specific": 1, "conditional": 2, "informational": 3}
EVIDENCE_SORT = {"confirmed": 0, "mixed": 1, "inferred": 2}
DIR_ROUTE_ORDER = {
    "LVD": 0,
    "EMC": 1,
    "RED": 2,
    "RED_CYBER": 3,
    "ROHS": 4,
    "REACH": 5,
    "GDPR": 6,
    "FCM": 7,
    "FCM_PLASTIC": 8,
    "BATTERY": 9,
    "ECO": 10,
    "ESPR": 11,
    "CRA": 12,
    "AI_Act": 13,
    "MD": 14,
    "MACH_REG": 15,
    "OTHER": 99,
}
LEG_SECTION_TITLES = {
    "ce": "Current CE legislation path",
    "framework": "Framework and delegated regime checks",
    "non_ce": "Parallel obligations outside CE marking",
    "future": "Future watchlist",
    "informational": "Informational items",
}
DIR_SECTION_TITLES = {
    "LVD": "LVD safety route",
    "EMC": "EMC route",
    "RED": "RED radio route",
    "RED_CYBER": "RED delegated-act cybersecurity route",
    "ROHS": "RoHS route",
    "REACH": "REACH route",
    "GDPR": "Data protection route",
    "FCM": "Food contact route",
    "FCM_PLASTIC": "Plastic food-contact route",
    "BATTERY": "Battery route",
    "ECO": "Ecodesign route",
    "ESPR": "ESPR framework route",
    "CRA": "CRA future route",
    "AI_Act": "AI Act future route",
    "MD": "Machinery route",
    "MACH_REG": "Future machinery route",
    "OTHER": "Other standards",
}
RISK_ORDER = {"LOW": 0, "MEDIUM": 1, "HIGH": 2, "CRITICAL": 3}
FORCED_DIRECTIVE_FALLBACKS = {
    "LVD": ("User-forced LVD route", "Electrical safety", "ce"),
    "EMC": ("User-forced EMC route", "Electromagnetic compatibility", "ce"),
    "RED": ("User-forced RED route", "Radio", "ce"),
    "RED_CYBER": ("User-forced RED cybersecurity route", "Cybersecurity for radio equipment", "ce"),
    "ROHS": ("User-forced RoHS route", "Substances", "ce"),
    "REACH": ("User-forced REACH route", "Substances", "non_ce"),
    "BATTERY": ("User-forced Battery route", "Batteries", "non_ce"),
    "GDPR": ("User-forced GDPR route", "Data protection", "non_ce"),
    "FCM": ("User-forced food contact route", "Food contact", "non_ce"),
    "CRA": ("User-forced CRA watchlist", "Cybersecurity for products with digital elements", "future"),
    "AI_Act": ("User-forced AI Act watchlist", "AI regulation", "future"),
}


def _current_date() -> date:
    return date.today()


def _parse_date(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


def _matches_conditions(
    row: dict[str, Any],
    traits: set[str],
    functional_classes: set[str],
    product_types: list[str] | None,
) -> bool:
    product_types = product_types or []

    def _all(values: list[str], haystack: set[str]) -> bool:
        return not values or set(values).issubset(haystack)

    def _any(values: list[str], haystack: set[str]) -> bool:
        return not values or bool(set(values) & haystack)

    def _none(values: list[str], haystack: set[str]) -> bool:
        return not bool(set(values) & haystack)

    if not _all(row.get("all_of_traits", []), traits):
        return False
    if not _any(row.get("any_of_traits", []), traits):
        return False
    if not _none(row.get("none_of_traits", []), traits):
        return False
    if not _all(row.get("all_of_functional_classes", []), functional_classes):
        return False
    if not _any(row.get("any_of_functional_classes", []), functional_classes):
        return False
    if not _none(row.get("none_of_functional_classes", []), functional_classes):
        return False

    any_products = set(row.get("any_of_product_types", []))
    if any_products and not (set(product_types) & any_products):
        return False
    if set(product_types) & set(row.get("exclude_product_types", [])):
        return False

    return True


def _legislation_evidence_strength(
    row: dict[str, Any],
    confirmed_traits: set[str],
    all_traits: set[str],
    confirmed_functional_classes: set[str],
    functional_classes: set[str],
    confirmed_products: list[str],
    matched_products: list[str],
) -> str | None:
    if _matches_conditions(row, confirmed_traits, confirmed_functional_classes or functional_classes, confirmed_products):
        return "confirmed"
    if _matches_conditions(row, all_traits, functional_classes, matched_products):
        return "inferred"
    return None


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


def _build_legislation_reason(row: dict[str, Any], timing_status: str, evidence_strength: str, forced: bool = False) -> str:
    base = row.get("reason") or "Potentially relevant based on detected traits and product class."
    if forced:
        base = "Added because this route was explicitly selected by the user. " + base
    elif evidence_strength == "inferred":
        base += " Triggered mainly by inferred product context; confirm the scoping facts before relying on this route."

    if timing_status == "future" and row.get("applicable_from"):
        base += f" Applies from {row['applicable_from']}."
    if timing_status == "legacy" and row.get("applicable_until"):
        base += f" Legacy route only up to {row['applicable_until']}."
    if row.get("replaced_by"):
        base += f" Superseded or complemented by {row['replaced_by']}."
    return base



def _pick_legislations(
    confirmed_traits: set[str],
    all_traits: set[str] | None = None,
    confirmed_functional_classes: set[str] | None = None,
    functional_classes: set[str] | None = None,
    product_type: str | None = None,
    confirmed_products: list[str] | None = None,
    matched_products: list[str] | None = None,
    forced_directives: list[str] | None = None,
) -> list[dict[str, Any]]:
    picked: list[dict[str, Any]] = []
    today = _current_date()
    all_traits = all_traits or set(confirmed_traits)
    confirmed_functional_classes = confirmed_functional_classes or set()
    functional_classes = functional_classes or set(confirmed_functional_classes)
    confirmed_products = confirmed_products or ([product_type] if product_type else [])
    matched_products = matched_products or confirmed_products or ([product_type] if product_type else [])

    for row in load_legislations():
        evidence_strength = _legislation_evidence_strength(
            row,
            confirmed_traits=confirmed_traits,
            all_traits=all_traits,
            confirmed_functional_classes=confirmed_functional_classes,
            functional_classes=functional_classes,
            confirmed_products=confirmed_products,
            matched_products=matched_products or ([product_type] if product_type else []),
        )
        if not evidence_strength:
            continue

        enriched = dict(row)
        enriched["timing_status"] = _timing_status(row, today)
        enriched["evidence_strength"] = evidence_strength
        if evidence_strength == "inferred" and enriched.get("applicability") == "applicable":
            enriched["applicability"] = "conditional"
        enriched["reason"] = _build_legislation_reason(
            row,
            enriched["timing_status"],
            evidence_strength=evidence_strength,
            forced=False,
        )
        picked.append(enriched)

    by_key = {row["directive_key"]: row for row in picked}
    forced_directives = [item for item in dict.fromkeys(forced_directives or []) if item]
    if forced_directives:
        catalog_index = {row["directive_key"]: row for row in load_legislations()}
        for directive in forced_directives:
            if directive in by_key:
                by_key[directive]["is_forced"] = True
                by_key[directive]["reason"] = _build_legislation_reason(
                    by_key[directive],
                    by_key[directive]["timing_status"],
                    by_key[directive].get("evidence_strength", "confirmed"),
                    forced=True,
                )
                continue

            source = catalog_index.get(directive)
            if source:
                forced_row = dict(source)
                forced_row["timing_status"] = _timing_status(source, today)
            else:
                title, family, bucket = FORCED_DIRECTIVE_FALLBACKS.get(directive, (f"User-forced {directive} route", "Other", "informational"))
                forced_row = {
                    "code": f"FORCED::{directive}",
                    "title": title,
                    "family": family,
                    "directive_key": directive,
                    "legal_form": "User selection",
                    "priority": "conditional",
                    "bucket": bucket,
                    "applicability": "conditional",
                    "triggers": [],
                    "doc_impacts": [],
                    "timing_status": "current" if bucket != "future" else "future",
                }
            forced_row["evidence_strength"] = "confirmed"
            forced_row["is_forced"] = True
            forced_row["reason"] = _build_legislation_reason(forced_row, forced_row["timing_status"], "confirmed", forced=True)
            by_key[directive] = forced_row

    picked = list(by_key.values())
    picked.sort(
        key=lambda x: (
            BUCKET_SORT.get(x.get("bucket", "non_ce"), 9),
            PRIORITY_SORT.get(x.get("priority", "conditional"), 9),
            EVIDENCE_SORT.get(x.get("evidence_strength", "confirmed"), 9),
            DIR_ROUTE_ORDER.get(x.get("directive_key", "OTHER"), 99),
            x.get("code", ""),
        )
    )
    return picked


def _directive_keys_for_matching(legislations: list[dict[str, Any]], forced: list[str]) -> list[str]:
    keys = {row["directive_key"] for row in legislations if row.get("directive_key")}
    keys.update(item for item in (forced or []) if item)
    return sorted(keys)


def _row_directives(row: dict[str, Any]) -> list[str]:
    directives = row.get("directives")
    if isinstance(directives, list):
        values = [item for item in directives if isinstance(item, str) and item]
        if values:
            return values

    for key in ("directive", "legislation_key"):
        value = row.get(key)
        if isinstance(value, str) and value:
            return [value]

    return ["OTHER"]


def _item_directives(item: StandardItem) -> list[str]:
    directives = item.directives or [item.directive]
    if item.legislation_key:
        directives = [*directives, item.legislation_key]
    unique = [value for value in dict.fromkeys(directives) if value]
    return unique or ["OTHER"]


def _has_directive(item: StandardItem, directive: str) -> bool:
    return directive in _item_directives(item)


def _directive_label(item: StandardItem) -> str:
    return " / ".join(_item_directives(item))


def _annotate_standard_items(rows: list[dict[str, Any]], legislation_index: dict[str, dict[str, Any]]) -> list[StandardItem]:
    out: list[StandardItem] = []
    for row in rows:
        lookup_key = row.get("legislation_key") or row.get("directive")
        leg = legislation_index.get(lookup_key) if isinstance(lookup_key, str) and lookup_key else None
        enriched = dict(row)
        if leg:
            enriched["regime_bucket"] = leg.get("bucket")
            enriched["timing_status"] = leg.get("timing_status", "current")

        directives = _row_directives(enriched)

        out.append(
            StandardItem(
                code=enriched["code"],
                title=enriched["title"],
                directive=directives[0],
                directives=directives,
                legislation_key=enriched.get("legislation_key"),
                category=enriched["category"],
                confidence=enriched.get("confidence", "medium"),
                item_type=enriched.get("item_type", "standard"),
                match_basis=enriched.get("match_basis", "traits"),
                fact_basis=enriched.get("fact_basis", "confirmed"),
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
                harmonization_status=enriched.get("harmonization_status", "unknown"),
                harmonized_reference=enriched.get("harmonized_reference"),
                version=enriched.get("version"),
                dated_version=enriched.get("dated_version"),
                supersedes=enriched.get("supersedes"),
                test_focus=enriched.get("test_focus", []),
                evidence_hint=enriched.get("evidence_hint", []),
                keywords=enriched.get("keywords", []),
            )
        )
    return out


def _add_gap(
    items: list[MissingInformationItem],
    *,
    key: str,
    message: str,
    importance: str = "medium",
    examples: list[str] | None = None,
    related_traits: list[str] | None = None,
    route_impact: list[str] | None = None,
) -> None:
    items.append(
        MissingInformationItem(
            key=key,
            message=message,
            importance=importance,
            examples=examples or [],
            related_traits=related_traits or [],
            route_impact=route_impact or [],
        )
    )


def _missing_information_items(
    explicit_traits: set[str],
    confirmed_traits: set[str],
    all_traits: set[str],
    product_type: str | None,
    product_confidence: str,
    contradictions: list[str],
    contradiction_severity: str,
    ce_legislations: list[LegislationItem],
    review_items: list[StandardItem],
) -> list[MissingInformationItem]:
    items: list[MissingInformationItem] = []

    connected_traits = {"cloud", "internet", "ota"}
    radio_traits = {"wifi", "bluetooth", "zigbee", "thread", "matter", "nfc", "cellular"}
    future_keys = {row.directive_key for row in ce_legislations}
    review_codes = {item.code for item in review_items}

    if not product_type or product_confidence == "low":
        _add_gap(
            items,
            key="product_type",
            message="Exact product type is unclear; provide the commercial product description or product family.",
            importance="high",
            examples=["air fryer", "robot vacuum cleaner", "built-in induction hob"],
            route_impact=["LVD", "EMC", "RED"],
        )

    if "electrical" in all_traits and not ({"mains_powered", "battery_powered", "usb_powered", "external_psu", "mains_power_likely"} & confirmed_traits):
        _add_gap(
            items,
            key="power_source",
            message="Power source is unclear; specify mains, battery, USB, or external PSU.",
            importance="high",
            examples=["230 V mains", "rechargeable Li-ion battery", "USB-C powered", "12 V DC via external adapter"],
            related_traits=["mains_powered", "battery_powered", "usb_powered", "external_psu"],
            route_impact=["LVD", "BATTERY", "ECO"],
        )

    if "electrical" in all_traits and not ({"portable", "fixed_installation", "built_in"} & confirmed_traits):
        _add_gap(
            items,
            key="installation_mode",
            message="Installation mode is unclear; confirm whether the product is portable, fixed-installed, or built-in.",
            importance="medium",
            examples=["portable countertop appliance", "built-in appliance", "wall-mounted fixed installation"],
            related_traits=["portable", "fixed_installation", "built_in"],
            route_impact=["LVD", "EMC"],
        )

    if ({"app_control", "cloud", "ota"} & all_traits) and "radio" not in confirmed_traits:
        _add_gap(
            items,
            key="radio_scope_confirmation",
            message="Connected features are described but no radio technology is explicit; confirm whether the product has Wi‑Fi, Bluetooth, Thread, Zigbee, NFC, or cellular.",
            importance="high",
            examples=["Wi-Fi radio", "Bluetooth LE radio", "No radio, local-only wired control"],
            related_traits=["radio", "wifi", "bluetooth", "thread", "zigbee", "nfc", "cellular"],
            route_impact=["RED", "RED_CYBER"],
        )

    if "radio" in all_traits and not (radio_traits & confirmed_traits):
        _add_gap(
            items,
            key="radio_technology",
            message="Radio technology is unclear; specify Wi‑Fi, Bluetooth, Thread, Zigbee, NFC, or cellular.",
            importance="high",
            examples=["Wi-Fi 2.4 GHz", "Bluetooth LE", "Thread radio"],
            related_traits=["radio"],
            route_impact=["RED"],
        )

    if "wifi" in all_traits and "wifi_5ghz" not in confirmed_traits:
        _add_gap(
            items,
            key="wifi_band",
            message="Confirm whether Wi‑Fi is 2.4 GHz only or also includes 5 GHz. This changes whether EN 301 893 should be shown.",
            importance="medium",
            examples=["2.4 GHz only", "dual-band 2.4/5 GHz", "5 GHz Wi-Fi"],
            related_traits=["wifi", "wifi_5ghz"],
            route_impact=["RED"],
        )

    if ({"radio", "cellular", "bluetooth"} & all_traits) and not ({"portable", "handheld", "body_worn_or_applied", "wearable"} & confirmed_traits):
        _add_gap(
            items,
            key="rf_exposure_form_factor",
            message="Form factor for RF exposure is unclear; confirm whether the radio product is handheld, body-worn, wearable, or only used with separation distance.",
            importance="medium",
            examples=["handheld", "body-worn wearable", "desktop use with separation distance"],
            related_traits=["handheld", "body_worn_or_applied", "wearable"],
            route_impact=["RED"],
        )

    if "food_contact" in all_traits:
        _add_gap(
            items,
            key="food_contact_materials",
            message="Confirm whether food-contact parts include plastic, coating, rubber, silicone, paper, or metal materials.",
            importance="medium",
            examples=["PA plastic water tank", "silicone seal", "non-stick coating"],
            related_traits=["food_contact"],
            route_impact=["FCM", "FCM_PLASTIC"],
        )

    if ({"water_contact", "wet_environment", "outdoor_use"} & all_traits) and not ({"wet_environment", "outdoor_use"} & confirmed_traits):
        _add_gap(
            items,
            key="environment_of_use",
            message="Environmental use conditions are unclear; confirm indoor, wet-location, bathroom, splash, or outdoor use.",
            importance="medium",
            examples=["indoor dry use", "bathroom / wet-location use", "outdoor garden use"],
            related_traits=["wet_environment", "outdoor_use"],
            route_impact=["LVD", "MD"],
        )

    if ({"radio"} & all_traits) and ((connected_traits & all_traits) or ("wifi" in all_traits) or ("account" in all_traits) or ("authentication" in all_traits)):
        _add_gap(
            items,
            key="connectivity_architecture",
            message="Clarify whether the connected radio product requires cloud, has local-only LAN control, and supports OTA updates.",
            importance="medium",
            examples=["local LAN only", "cloud account required", "OTA security patching supported"],
            related_traits=["cloud", "internet", "ota", "local_only"],
            route_impact=["RED_CYBER", "CRA"],
        )

    if ({"radio"} & all_traits) and ((connected_traits & all_traits) or ("wifi" in all_traits)) and not ({"account", "authentication"} & confirmed_traits):
        _add_gap(
            items,
            key="redcyber_auth_scope",
            message="Confirm whether the product or companion app uses account, login, password, PIN, pairing code, or similar authentication. This changes EN 18031‑2 applicability.",
            importance="medium",
            examples=["user account required", "password or PIN entry", "no login or authentication"],
            related_traits=["account", "authentication"],
            route_impact=["RED_CYBER"],
        )

    if ({"radio"} & all_traits) and ((connected_traits & all_traits) or ("wifi" in all_traits)) and "monetary_transaction" not in confirmed_traits:
        _add_gap(
            items,
            key="redcyber_transaction_scope",
            message="Confirm whether the product or companion app supports purchases, subscriptions, payments, wallet functions, or any transfer of monetary value. This changes EN 18031‑3 applicability.",
            importance="medium",
            examples=["subscription purchase through app", "payment or wallet function", "no payment or monetary transfer"],
            related_traits=["monetary_transaction"],
            route_impact=["RED_CYBER"],
        )

    if ({"account", "authentication", "camera", "microphone", "location", "personal_data_likely"} & all_traits) and not ({"cloud", "local_only", "internet"} & confirmed_traits):
        _add_gap(
            items,
            key="personal_data_architecture",
            message="Personal-data architecture is unclear; confirm whether user data stays local, syncs to cloud, or is shared with a companion service.",
            importance="medium",
            examples=["local-only storage", "cloud account storage", "companion app forwards telemetry"],
            related_traits=["personal_data_likely", "cloud", "local_only", "internet"],
            route_impact=["GDPR", "RED_CYBER", "CRA"],
        )

    if ("child_targeted" not in confirmed_traits) and ({"camera", "microphone", "location"} & all_traits) and product_type in {"smart_watch", "smart_display", "wearable_tracker", "toy"}:
        _add_gap(
            items,
            key="child_targeting",
            message="Target user group is unclear; confirm whether the product is intended for children or vulnerable users.",
            importance="low",
            examples=["general consumer product", "intended for children"],
            related_traits=["child_targeted"],
            route_impact=["GDPR", "AI_Act"],
        )

    if ({"CRA", "AI_Act"} & future_keys) and ({"cloud", "internet", "ota", "app_control", "radio", "ai_related"} & all_traits):
        _add_gap(
            items,
            key="future_regime_planning",
            message="Future digital-regime planning is incomplete; confirm software update policy, vulnerability handling, and product support period.",
            importance="low",
            examples=["security support period", "vulnerability disclosure process", "software bill of materials"],
            related_traits=["ota", "cloud", "radio", "ai_related"],
            route_impact=["CRA", "AI_Act"],
        )

    if contradiction_severity in {"medium", "high"} or contradictions:
        _add_gap(
            items,
            key="contradictions",
            message="Resolve contradictory product signals before relying on the output for compliance decisions.",
            importance="high",
            examples=contradictions[:3],
            route_impact=["LVD", "EMC", "RED", "RED_CYBER"],
        )

    deduped: list[MissingInformationItem] = []
    seen: set[str] = set()
    for item in items:
        if item.key in seen:
            continue
        seen.add(item.key)
        deduped.append(item)
    return deduped


def _display_tags(item: StandardItem) -> list[str]:
    tags: list[str] = []
    code_upper = item.code.upper()
    if item.harmonization_status == "harmonized":
        tags.append("Harmonized")
    elif item.harmonization_status == "state_of_the_art":
        tags.append("State of the art")
    elif item.item_type == "review":
        tags.append("Review required")

    if item.fact_basis != "confirmed":
        tags.append("Needs confirmation")
    if item.timing_status == "future":
        tags.append("Future route")
    if _has_directive(item, "LVD") and code_upper.startswith("EN 60335-2-"):
        tags.append("Part 2")
    if _has_directive(item, "LVD") and code_upper.startswith("EN 60335-1"):
        tags.append("Base safety")
    if item.category == "emc" or code_upper.startswith("EN 55014") or code_upper.startswith("EN 61000"):
        tags.append("EMC")
    if _has_directive(item, "RED"):
        tags.append("Radio")
    if _has_directive(item, "RED_CYBER"):
        tags.append("Cybersecurity")
    if code_upper.startswith("EN 18031-1"):
        tags.extend(["Art. 3(3)(d)", "Network security"])
    if code_upper.startswith("EN 18031-2"):
        tags.append("Auth / login")
    if code_upper.startswith("EN 18031-3"):
        tags.append("Payments / fraud")
    if item.category == "emf":
        tags.append("EMF")
    if item.category == "energy":
        tags.append("Energy")
    if "privacy" in item.test_focus:
        tags.append("Privacy")
    if "software" in item.test_focus:
        tags.append("Software")
    return list(dict.fromkeys(tags))[:6]


def _standard_summary(item: StandardItem) -> str:
    code = item.code.upper()
    if code.startswith("EN 60335-1"):
        return "General electrical safety baseline for household appliances."
    if code.startswith("EN 60335-2-"):
        return "Product-specific Part 2 route for the detected appliance family."
    if code.startswith("EN 55014-1"):
        return "Emission-side EMC route for household appliances and similar apparatus."
    if code.startswith("EN 55014-2"):
        return "Immunity-side EMC route for household appliances and similar apparatus."
    if code.startswith("EN 61000-3-2"):
        return "Harmonic current emissions route for mains-connected equipment."
    if code.startswith("EN 61000-3-3") or code.startswith("EN 61000-3-11"):
        return "Voltage change and flicker route for mains-connected equipment."
    if code.startswith("EN 18031-1"):
        return "RED delegated-act route for internet-connected or network-enabled radio equipment."
    if code.startswith("EN 18031-2"):
        return "RED delegated-act route for account, login, password, PIN, or other authentication controls."
    if code.startswith("EN 18031-3"):
        return "RED delegated-act route for payments, subscriptions, orders, wallet functions, or other monetary-value transfer."
    if code.startswith("EN 301 893"):
        return "5 GHz Wi‑Fi spectrum route; confirm only when 5 GHz or dual-band Wi‑Fi is present."
    if code.startswith("EN 300") or code.startswith("EN 301"):
        return "Radio spectrum or radio EMC route for the detected wireless technology."
    if code.startswith("EN 62209-1528"):
        return "SAR route for handheld, body-near, or cellular radio equipment."
    if code.startswith("EN 62311") or code.startswith("EN 62479") or code.startswith("EN 50364"):
        return "EMF or RF exposure assessment route."
    if code.startswith("EN 63000"):
        return "RoHS technical documentation route."
    return item.title


def _standard_route_keys(item: StandardItem) -> list[str]:
    code_upper = item.code.upper()
    if code_upper.startswith("EN 18031-"):
        return ["RED_CYBER"]
    return _item_directives(item)


def _standard_sort_rank_from_code(code: str) -> tuple[int, int, str]:
    code_upper = code.upper()
    if code_upper.startswith("EN 60335-1"):
        return (0, 0, code_upper)
    if code_upper.startswith("EN 60335-2-"):
        return (0, 1, code_upper)
    if code_upper.startswith("EN 55014-1"):
        return (1, 0, code_upper)
    if code_upper.startswith("EN 55014-2"):
        return (1, 1, code_upper)
    if code_upper.startswith("EN 61000-3-2"):
        return (1, 2, code_upper)
    if code_upper.startswith("EN 61000-3-3") or code_upper.startswith("EN 61000-3-11"):
        return (1, 3, code_upper)
    if code_upper.startswith("EN 300 328"):
        return (2, 0, code_upper)
    if code_upper.startswith("EN 301 489-1"):
        return (2, 1, code_upper)
    if code_upper.startswith("EN 301 489-17"):
        return (2, 2, code_upper)
    if code_upper.startswith("EN 62479") or code_upper.startswith("EN 62311") or code_upper.startswith("EN 50364"):
        return (2, 3, code_upper)
    if code_upper.startswith("EN 18031-1"):
        return (3, 0, code_upper)
    if code_upper.startswith("EN 18031-2"):
        return (3, 1, code_upper)
    if code_upper.startswith("EN 18031-3"):
        return (3, 2, code_upper)
    if code_upper.startswith("EN 63000"):
        return (4, 0, code_upper)
    return (9, 9, code_upper)


def _build_standard_sections(standards: list[StandardItem], review_items: list[StandardItem]) -> list[dict[str, Any]]:
    grouped: dict[str, dict[str, Any]] = {}

    for item in [*standards, *review_items]:
        for route_key in _standard_route_keys(item):
            section = grouped.setdefault(
                route_key,
                {"key": route_key, "title": DIR_SECTION_TITLES.get(route_key, route_key), "count": 0, "items": []},
            )
            section["items"].append(
                {
                    "code": item.code,
                    "title": item.title,
                    "directive": route_key,
                    "directives": _item_directives(item),
                    "legislation_key": item.legislation_key,
                    "category": item.category,
                    "item_type": item.item_type,
                    "confidence": item.confidence,
                    "fact_basis": item.fact_basis,
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
                    "timing_status": item.timing_status,
                    "test_focus": item.test_focus,
                    "evidence_hint": item.evidence_hint,
                    "keywords": item.keywords,
                    "display_tags": _display_tags(item),
                    "standard_summary": _standard_summary(item),
                }
            )

    for section in grouped.values():
        section["items"].sort(key=lambda row: _standard_sort_rank_from_code(row["code"]))
        section["count"] = len(section["items"])

    return [grouped[key] for key in sorted(grouped, key=lambda x: DIR_ROUTE_ORDER.get(x, 99))]


def _build_legislation_sections(legislations: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, dict[str, Any]] = {}
    for row in legislations:
        bucket = row.get("bucket", "non_ce")
        section = grouped.setdefault(
            bucket,
            {"key": bucket, "title": LEG_SECTION_TITLES.get(bucket, bucket.title()), "count": 0, "items": []},
        )
        section["items"].append(
            {
                "code": row.get("code"),
                "title": row.get("title"),
                "family": row.get("family"),
                "directive_key": row.get("directive_key"),
                "priority": row.get("priority"),
                "applicability": row.get("applicability"),
                "timing_status": row.get("timing_status"),
                "reason": row.get("reason"),
                "notes": row.get("notes"),
                "evidence_strength": row.get("evidence_strength", "confirmed"),
                "is_forced": row.get("is_forced", False),
                "applicable_from": row.get("applicable_from"),
                "applicable_until": row.get("applicable_until"),
                "doc_impacts": row.get("doc_impacts", []),
            }
        )
    for section in grouped.values():
        section["items"].sort(
            key=lambda x: (
                DIR_ROUTE_ORDER.get(x["directive_key"] or "OTHER", 99),
                EVIDENCE_SORT.get(x.get("evidence_strength", "confirmed"), 9),
                x["code"] or "",
            )
        )
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
            status = "PASS" if row["timing_status"] == "current" and row.get("evidence_strength") == "confirmed" else "WARN"
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
                directive=_directive_label(item),
                article=item.code,
                status="PASS" if item.harmonization_status == "harmonized" and item.fact_basis == "confirmed" else "INFO",
                finding=item.title,
                action=item.reason or item.notes,
            )
        )

    for item in review_items:
        findings.append(
            Finding(
                directive=_directive_label(item),
                article=item.code,
                status="WARN" if item.timing_status == "current" else "INFO",
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
        findings.append(Finding(directive="INPUT", article="Contradiction", status="WARN", finding=contradiction))

    return findings


def _diagnostics(
    depth: str,
    classification: dict[str, Any],
    picked_legislations: list[dict[str, Any]],
    applicable_items: dict[str, Any],
    current_risk: str,
    future_risk: str,
) -> list[str]:
    diagnostics = [f"analysis_date={_current_date().isoformat()}", f"depth={depth}"]
    diagnostics.extend(classification.get("diagnostics", []))
    diagnostics.append("legislation_keys=" + ",".join(sorted({row["directive_key"] for row in picked_legislations if row.get("directive_key")})))
    diagnostics.append(f"standard_hits={len(applicable_items.get('standards', []))}")
    diagnostics.append(f"review_hits={len(applicable_items.get('review_items', []))}")
    diagnostics.append(f"rejections={len(applicable_items.get('rejections', []))}")
    diagnostics.append(f"current_compliance_risk={current_risk}")
    diagnostics.append(f"future_watchlist_risk={future_risk}")
    for rejection in applicable_items.get("rejections", [])[:12]:
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
        current_review_items_count=sum(1 for row in review_items if row.timing_status == "current"),
        future_review_items_count=sum(1 for row in review_items if row.timing_status == "future"),
        harmonized_standards_count=sum(1 for row in standards if row.harmonization_status == "harmonized"),
        state_of_the_art_standards_count=sum(1 for row in standards if row.harmonization_status == "state_of_the_art"),
        product_gated_standards_count=sum(1 for row in standards if row.applies_if_products),
        ambiguity_flag_count=len(contradictions),
        missing_information_count=len(missing_information_items),
    )


def _nice_product(product_type: str | None) -> str:
    return product_type.replace("_", " ") if product_type else "unclear product"


def _hero_summary(
    product_type: str | None,
    product_confidence: str,
    current_risk: str,
    future_risk: str,
    ce_legislations: list[LegislationItem],
    standards: list[StandardItem],
    review_items: list[StandardItem],
    missing_information_items: list[MissingInformationItem],
) -> dict[str, Any]:
    primary_regimes = [row.directive_key for row in sorted(ce_legislations, key=lambda x: DIR_ROUTE_ORDER.get(x.directive_key, 99))[:5]]
    return {
        "title": _nice_product(product_type).title() if product_type else "Product not confidently identified",
        "subtitle": "Current compliance path is separated from future monitoring and parallel obligations.",
        "confidence": product_confidence,
        "current_compliance_risk": current_risk,
        "future_watchlist_risk": future_risk,
        "primary_regimes": primary_regimes,
        "stats": [
            {"label": "Current CE", "value": len(ce_legislations)},
            {"label": "Standards", "value": len(standards)},
            {"label": "Review items", "value": len(review_items)},
            {"label": "Input gaps", "value": len(missing_information_items)},
        ],
    }


def _confidence_panel(classification: dict[str, Any]) -> dict[str, Any]:
    candidates = classification.get("product_candidates", [])
    return {
        "level": classification.get("product_match_confidence", "low"),
        "product_type": classification.get("product_type"),
        "alternatives": candidates[1:4],
        "reasons": candidates[0].get("reasons", []) if candidates else [],
        "confirmed_traits": classification.get("confirmed_traits", []),
        "contradictions": classification.get("contradictions", []),
        "contradiction_severity": classification.get("contradiction_severity", "none"),
    }


def _input_gaps_panel(items: list[MissingInformationItem]) -> dict[str, Any]:
    return {
        "title": "What to clarify next",
        "count": len(items),
        "items": [
            {
                "key": item.key,
                "message": item.message,
                "importance": item.importance,
                "examples": item.examples,
                "related_traits": item.related_traits,
                "route_impact": item.route_impact,
            }
            for item in items
        ],
    }


def _top_actions(
    product_type: str | None,
    ce_legislations: list[LegislationItem],
    standards: list[StandardItem],
    review_items: list[StandardItem],
    missing_information_items: list[MissingInformationItem],
) -> list[str]:
    actions: list[str] = []
    if product_type:
        actions.append(f"Confirm that the detected product family '{_nice_product(product_type)}' is correct.")
    if any(item.key == "radio_scope_confirmation" for item in missing_information_items):
        actions.append("Confirm the radio stack explicitly before fixing RED and EN 18031 scope.")
    if any(item.key == "wifi_band" for item in missing_information_items):
        actions.append("Clarify whether Wi‑Fi is 2.4 GHz only or also 5 GHz before finalizing RED radio standards.")
    if any(item.key == "redcyber_auth_scope" for item in missing_information_items):
        actions.append("Confirm account, login, password, PIN, or pairing flows to decide EN 18031‑2.")
    if any(item.key == "redcyber_transaction_scope" for item in missing_information_items):
        actions.append("Confirm payment, subscription, ordering, or other money-transfer features to decide EN 18031‑3.")
    if any(row.directive_key == "RED_CYBER" for row in ce_legislations):
        actions.append("Map connected radio functions to EN 18031‑1, ‑2, and ‑3, and keep CRA separate as a future regime.")
    if any(_has_directive(item, "LVD") and item.code.startswith("EN 60335-2-") for item in standards):
        actions.append("Use EN 60335‑1 as the base route and the applicable EN 60335‑2 Part 2 route for product-specific safety.")
    if any(_has_directive(item, "EMC") for item in standards):
        actions.append("Plan EMC evidence separately for emission, immunity, harmonics, and flicker where applicable.")
    if any(item.timing_status == "current" for item in review_items):
        actions.append("Resolve current review-required routes before treating the output as final for declaration work.")
    if missing_information_items:
        actions.append("Close the missing-input gaps before freezing the compliance route.")
    return actions[:8]


def _current_path(ce_legislations: list[LegislationItem], standards: list[StandardItem]) -> list[str]:
    directives = [row.directive_key for row in sorted(ce_legislations, key=lambda x: DIR_ROUTE_ORDER.get(x.directive_key, 99))]
    path: list[str] = []

    if "LVD" in directives:
        path.append("Keep EN 60335‑1 as the base safety route and apply the correct EN 60335‑2 Part 2 product standard.")
    if "EMC" in directives:
        path.append("Confirm EMC routes for emission, immunity, and mains disturbance standards as applicable.")
    if "RED" in directives:
        path.append("Keep radio spectrum, radio EMC, and RF exposure under the RED route.")
    if any(item.code.upper().startswith("EN 18031-1") for item in standards):
        path.append("Use EN 18031‑1 for internet-connected or network-enabled radio functionality.")
    if any(item.code.upper().startswith("EN 18031-2") for item in standards):
        path.append("Use EN 18031‑2 where account, login, password, PIN, or similar authentication is present.")
    if any(item.code.upper().startswith("EN 18031-3") for item in standards):
        path.append("Use EN 18031‑3 where the product or companion flow supports payment or other monetary-value transfer.")
    if any(_has_directive(item, "ROHS") for item in standards) or any(row.directive_key == "ROHS" for row in ce_legislations):
        path.append("Maintain RoHS technical documentation and supplier-material evidence alongside the CE file.")
    return path[:6]


def _future_watchlist(future_regimes: list[LegislationItem], framework_regimes: list[LegislationItem]) -> list[str]:
    watchlist: list[str] = []
    for row in future_regimes[:4]:
        line = row.title
        if row.applicable_from:
            line += f" from {row.applicable_from}"
        watchlist.append(line)
    for row in framework_regimes[:2]:
        watchlist.append(f"Monitor delegated or product-family measures under {row.title}.")
    return watchlist[:6]


def _suggested_questions(
    product_type: str | None,
    all_traits: set[str],
    missing_information_items: list[MissingInformationItem],
    contradictions: list[str],
) -> list[str]:
    questions: list[str] = []
    keys = {item.key for item in missing_information_items}
    if not product_type:
        questions.append("What exact product family is it, in commercial terms?")
    if "power_source" in keys:
        questions.append("Is it mains powered, battery powered, USB powered, or supplied via external PSU?")
    if "installation_mode" in keys:
        questions.append("Is it portable, fixed-installed, or built in?")
    if keys & {"radio_scope_confirmation", "radio_technology"} or "radio" in all_traits:
        questions.append("Which radio technologies are present: Wi‑Fi, Bluetooth, Thread, Zigbee, NFC, or cellular?")
    if "wifi_band" in keys:
        questions.append("Is the Wi‑Fi 2.4 GHz only, or dual-band with 5 GHz as well?")
    if "rf_exposure_form_factor" in keys:
        questions.append("Is the radio product handheld, body-worn, wearable, or used only with separation distance?")
    if "food_contact_materials" in keys:
        questions.append("Which materials are in the food-contact path?")
    if "connectivity_architecture" in keys:
        questions.append("Does the connected product need cloud, internet access, local-only LAN control, OTA updates, or some combination?")
    if "redcyber_auth_scope" in keys:
        questions.append("Does the product or companion app use login, password, PIN, pairing, or any other authentication control?")
    if "redcyber_transaction_scope" in keys:
        questions.append("Can the product or companion flow place orders, take payments, run subscriptions, or transfer monetary value?")
    if "personal_data_architecture" in keys:
        questions.append("What personal data is processed, and does it stay local or move to a cloud / companion service?")
    if contradictions:
        questions.append("Which of the contradictory signals is actually correct in the product specification?")
    return questions[:10]


def _suggested_quick_adds(product_type: str | None, all_traits: set[str], missing_information_items: list[MissingInformationItem]) -> list[dict[str, str]]:
    chips: list[dict[str, str]] = []
    keys = {item.key for item in missing_information_items}

    def add(label: str, text: str) -> None:
        if len(chips) < 16 and not any(existing["text"] == text for existing in chips):
            chips.append({"label": label, "text": text})

    if product_type == "coffee_machine":
        add("Water tank", "water tank and brew path")
        add("Milk system", "milk system and food-contact elastomers")
        add("Grinder", "integrated grinder and motor")
        add("Wi‑Fi", "Wi‑Fi radio")
        add("Cloud", "cloud account and brew-profile storage")
        add("Login", "user account and password login")
        add("Payments", "capsule or subscription purchase through app")
    elif product_type == "electric_kettle":
        add("2.4 GHz", "Wi‑Fi 2.4 GHz radio")
        add("Heating liquids", "liquid heating and steam generation")
        add("Food-contact", "plastic and silicone food-contact parts")
    elif product_type in {"robot_vacuum_cleaner", "robot_vacuum"}:
        add("LiDAR", "LiDAR navigation and laser emitter")
        add("Camera", "camera for mapping and remote monitoring")
        add("Battery", "rechargeable lithium battery")
        add("Login", "user account and password login")
        add("Payments", "subscription or accessory purchase through app")
    elif product_type in {"air_purifier", "air_cleaner"}:
        add("PM sensor", "air-quality sensing and fan control")
        add("Wi‑Fi", "Wi‑Fi radio and app control")
        add("Standby", "networked standby and off-mode behaviour")

    if keys & {"radio_scope_confirmation", "radio_technology"}:
        add("Wi‑Fi", "Wi‑Fi radio")
        add("Bluetooth", "Bluetooth LE radio")
        add("No radio", "No radio, local-only wired control")
    if "wifi_band" in keys:
        add("2.4 GHz", "Wi‑Fi 2.4 GHz radio")
        add("5 GHz", "dual-band 2.4/5 GHz Wi‑Fi")
    if "power_source" in keys:
        add("230 V mains", "230 V mains powered")
        add("Battery", "rechargeable lithium battery")
        add("USB‑C", "USB‑C powered")
        add("External PSU", "supplied via external power adapter")
    if "installation_mode" in keys:
        add("Portable", "portable countertop product")
        add("Built-in", "built-in fixed installation")
    if "connectivity_architecture" in keys:
        add("Local LAN", "local LAN control without cloud dependency")
        add("Cloud account", "cloud account required")
        add("Security patching", "security and firmware patching over the air")
    if "redcyber_auth_scope" in keys:
        add("Login", "user account and password login")
        add("PIN", "PIN or passcode entry")
        add("No login", "no login or authentication")
    if "redcyber_transaction_scope" in keys:
        add("Payments", "payment or wallet function")
        add("Subscriptions", "subscription purchase through app")
        add("No payments", "no payment or monetary transfer")
    if "food_contact_materials" in keys:
        add("Plastic path", "food-contact plastics and silicone")
    if "rf_exposure_form_factor" in keys:
        add("Handheld", "handheld use close to the body")
        add("Wearable", "body-worn wearable use")

    fallback = [
        ("Heating", "heating element"),
        ("Motor", "motor and moving parts"),
        ("Display", "display and touch UI"),
        ("Camera", "camera and image capture"),
        ("Personal data", "personal data and account-related processing"),
    ]
    for label, text in fallback:
        add(label, text)

    return chips[:16]


def _max_risk(*levels: str) -> str:
    if not levels:
        return "LOW"
    return max(levels, key=lambda level: RISK_ORDER.get(level, 0))


def _current_compliance_risk(
    product_type: str | None,
    product_match_confidence: str,
    contradiction_severity: str,
    missing_information_items: list[MissingInformationItem],
    standards: list[StandardItem],
    review_items: list[StandardItem],
    ce_legislations: list[LegislationItem],
) -> str:
    risk = "LOW"
    if contradiction_severity == "high":
        return "CRITICAL"
    if contradiction_severity == "medium":
        risk = _max_risk(risk, "HIGH")
    if product_match_confidence == "low" or not product_type:
        risk = _max_risk(risk, "MEDIUM")

    high_gaps = any(item.importance == "high" for item in missing_information_items)
    medium_gaps = any(item.importance == "medium" for item in missing_information_items)
    current_review_items = [item for item in review_items if item.timing_status == "current"]

    if high_gaps:
        risk = _max_risk(risk, "HIGH")
    elif medium_gaps:
        risk = _max_risk(risk, "MEDIUM")

    if current_review_items:
        risk = _max_risk(risk, "HIGH")
    if ce_legislations and not standards and not current_review_items:
        risk = _max_risk(risk, "HIGH")
    return risk


def _future_watchlist_risk(
    all_traits: set[str],
    future_regimes: list[LegislationItem],
    framework_regimes: list[LegislationItem],
    review_items: list[StandardItem],
) -> str:
    risk = "LOW"
    future_review_items = [item for item in review_items if item.timing_status == "future"]
    if future_regimes or framework_regimes or future_review_items:
        risk = "MEDIUM"

    future_keys = {row.directive_key for row in future_regimes}
    if ("CRA" in future_keys and ({"cloud", "internet", "ota", "app_control", "radio", "data_storage"} & all_traits)) or (
        "AI_Act" in future_keys and "ai_related" in all_traits
    ):
        risk = _max_risk(risk, "HIGH")
    return risk


def analyze(description: str, category: str = "", directives: list[str] | None = None, depth: str = "standard") -> AnalysisResult:
    classification = extract_traits(description=description, category=category)
    product_type = classification.get("product_type")
    explicit_traits = set(classification.get("explicit_traits", []))
    confirmed_traits = set(classification.get("confirmed_traits", []))
    all_traits = set(classification.get("all_traits", []))
    functional_classes = set(classification.get("functional_classes", []))
    confirmed_functional_classes = set(classification.get("confirmed_functional_classes", []))
    forced_directives = [item for item in dict.fromkeys(directives or []) if item]

    picked_legislations = _pick_legislations(
        confirmed_traits=confirmed_traits,
        all_traits=all_traits,
        confirmed_functional_classes=confirmed_functional_classes,
        functional_classes=functional_classes,
        product_type=product_type,
        confirmed_products=classification.get("confirmed_products", []),
        matched_products=classification.get("matched_products", []),
        forced_directives=forced_directives,
    )
    directive_keys = _directive_keys_for_matching(picked_legislations, forced_directives)
    applicable_items = find_applicable_items(
        traits=all_traits,
        directives=directive_keys,
        product_type=product_type,
        matched_products=classification.get("matched_products", []),
        preferred_standard_codes=classification.get("preferred_standard_codes", []),
        explicit_traits=explicit_traits,
        confirmed_traits=confirmed_traits,
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
        explicit_traits=explicit_traits,
        confirmed_traits=confirmed_traits,
        all_traits=all_traits,
        product_type=product_type,
        product_confidence=classification["product_match_confidence"],
        contradictions=classification["contradictions"],
        contradiction_severity=contradiction_severity,
        ce_legislations=ce_legislations,
        review_items=review_items,
    )
    missing_information = [item.message for item in missing_information_items]

    current_risk = _current_compliance_risk(
        product_type=product_type,
        product_match_confidence=classification["product_match_confidence"],
        contradiction_severity=contradiction_severity,
        missing_information_items=missing_information_items,
        standards=standards,
        review_items=review_items,
        ce_legislations=ce_legislations,
    )
    future_risk = _future_watchlist_risk(
        all_traits=all_traits,
        future_regimes=future_regimes,
        framework_regimes=framework_regimes,
        review_items=review_items,
    )
    overall_risk = _max_risk(current_risk, future_risk)

    summary_parts: list[str] = []
    if product_type:
        summary_parts.append(f"Detected product type: {_nice_product(product_type)}.")
    else:
        summary_parts.append("Product type could not be identified with confidence.")
    if any(item.key == "radio_scope_confirmation" for item in missing_information_items):
        summary_parts.append("Connected features were detected but the radio stack is not explicit, so RED and EN 18031 scoping may still be incomplete.")
    if ce_legislations:
        summary_parts.append("Current CE legislation is separated from future and parallel obligations.")
    if standards:
        summary_parts.append("Standards are grouped by route so the main path is easier to review.")
    if classification["contradictions"]:
        summary_parts.append("Contradictions reduce confidence and should be resolved before declaration work.")
    summary_parts.append(f"Current compliance risk is {current_risk}; future watchlist risk is {future_risk}.")

    kb_meta = KnowledgeBaseMeta(**load_meta())
    standard_sections = _build_standard_sections(standards, review_items)
    legislation_sections = _build_legislation_sections(picked_legislations)
    hero_summary = _hero_summary(
        product_type,
        classification["product_match_confidence"],
        current_risk,
        future_risk,
        ce_legislations,
        standards,
        review_items,
        missing_information_items,
    )
    confidence_panel = _confidence_panel(classification)
    input_gaps_panel = _input_gaps_panel(missing_information_items)
    current_path = _current_path(ce_legislations, standards)
    future_watchlist = _future_watchlist(future_regimes, framework_regimes)
    top_actions = _top_actions(product_type, ce_legislations, standards, review_items, missing_information_items)
    suggested_questions = _suggested_questions(product_type, all_traits, missing_information_items, classification["contradictions"])
    suggested_quick_adds = _suggested_quick_adds(product_type, all_traits, missing_information_items)
    analysis_audit = {
        "analysis_date": _current_date().isoformat(),
        "knowledge_base_version": kb_meta.version,
        "forced_directives": forced_directives,
        "matched_products": classification.get("matched_products", []),
        "confirmed_products": classification.get("confirmed_products", []),
        "product_match_confidence": classification.get("product_match_confidence", "low"),
    }

    return AnalysisResult(
        product_summary=description.strip() or category.strip() or "Product analysis",
        overall_risk=overall_risk,
        current_compliance_risk=current_risk,
        future_watchlist_risk=future_risk,
        summary=" ".join(summary_parts) or "Regulatory scoping completed.",
        product_type=product_type,
        product_match_confidence=classification["product_match_confidence"],
        product_candidates=classification["product_candidates"],
        functional_classes=classification["functional_classes"],
        confirmed_functional_classes=classification.get("confirmed_functional_classes", []),
        explicit_traits=classification["explicit_traits"],
        confirmed_traits=classification.get("confirmed_traits", []),
        inferred_traits=classification["inferred_traits"],
        all_traits=classification["all_traits"],
        directives=directive_keys,
        forced_directives=forced_directives,
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
        diagnostics=_diagnostics(depth, classification, picked_legislations, applicable_items, current_risk, future_risk),
        stats=_stats(picked_legislations, standards, review_items, missing_information_items, classification["contradictions"]),
        knowledge_base_meta=kb_meta,
        analysis_audit=analysis_audit,
        standard_sections=standard_sections,
        legislation_sections=legislation_sections,
        hero_summary=hero_summary,
        confidence_panel=confidence_panel,
        input_gaps_panel=input_gaps_panel,
        top_actions=top_actions,
        current_path=current_path,
        future_watchlist=future_watchlist,
        suggested_questions=suggested_questions,
        suggested_quick_adds=suggested_quick_adds,
        findings=_findings(picked_legislations, standards, review_items, missing_information_items, classification["contradictions"]),
    )
