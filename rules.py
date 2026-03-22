from __future__ import annotations

import re
from collections import defaultdict
from datetime import date
import os
from typing import Any, Literal

from env_config import init_env

init_env()

from classifier import ENGINE_VERSION as CLASSIFIER_ENGINE_VERSION, extract_traits, extract_traits_v1, normalize
from knowledge_base import load_legislations, load_meta
from models import (
    AnalysisResult,
    AnalysisStats,
    ConfidenceLevel,
    FactBasis,
    Finding,
    KnowledgeBaseMeta,
    LegislationItem,
    MissingInformationItem,
    ProductMatchAudit,
    RiskLevel,
    StandardAuditItem,
    StandardMatchAudit,
    StandardItem,
    TraitEvidenceItem,
    TraitEvidenceState,
)
from standards_engine import find_applicable_items, find_applicable_items_v1

LegislationBucket = Literal["ce", "non_ce", "framework", "future", "informational"]
MissingImportance = Literal["high", "medium", "low"]

DIRECTIVE_TITLES: dict[str, tuple[str, str]] = {
    "LVD": ("LVD", "Low Voltage Directive 2014/35/EU"),
    "EMC": ("EMC", "EMC Directive 2014/30/EU"),
    "RED": ("RED", "Radio Equipment Directive 2014/53/EU"),
    "RED_CYBER": ("RED-DA", "RED delegated cybersecurity requirements"),
    "ROHS": ("RoHS", "RoHS Directive 2011/65/EU"),
    "REACH": ("REACH", "REACH Regulation (EC) No 1907/2006"),
    "BATTERY": ("Battery", "Battery Regulation (EU) 2023/1542"),
    "GPSR": ("GPSR", "General Product Safety Regulation (EU) 2023/988"),
    "WEEE": ("WEEE", "WEEE Directive 2012/19/EU"),
    "TOY": ("Toy", "Toy Safety Directive 2009/48/EC"),
    "UAS": ("Drone/UAS", "EU drone / UAS framework review"),
    "ECO": ("Ecodesign", "Ecodesign / energy efficiency review"),
    "CRA": ("CRA", "Cyber Resilience Act review"),
    "GDPR": ("GDPR", "GDPR review"),
    "MDR": ("MDR", "Medical Device Regulation borderline review"),
    "OTHER": ("Other", "Additional compliance route"),
}

DIRECTIVE_ORDER = [
    "LVD",
    "EMC",
    "RED",
    "RED_CYBER",
    "ROHS",
    "REACH",
    "BATTERY",
    "GPSR",
    "TOY",
    "UAS",
    "WEEE",
    "ECO",
    "CRA",
    "GDPR",
    "MDR",
    "OTHER",
]

ENGINE_VERSION = CLASSIFIER_ENGINE_VERSION
ENABLE_ENGINE_V2_SHADOW = os.getenv("REGCHECK_ENGINE_V2_SHADOW", "false").strip().lower() in {"1", "true", "yes", "on"}

POWER_EXTERNAL_PATTERNS = [
    r"\bexternal power supply\b",
    r"\bexternal psu\b",
    r"\bpower adapter\b",
    r"\bac adapter\b",
    r"\bdc adapter\b",
    r"\bpower brick\b",
    r"\bwall adapter\b",
    r"\bplug ?pack\b",
    r"\bcharging dock\b",
    r"\bcharging cradle\b",
    r"\bcharger supplied\b",
    r"\bcomes with (an? )?(adapter|charger)\b",
    r"\bsupplied via external adapter\b",
    r"\bvia external adapter\b",
]

POWER_EXTERNAL_NEGATION_PATTERNS = [
    r"\bno external power supply\b",
    r"\bwithout external power supply\b",
    r"\bexternal power supply not included\b",
    r"\badapter not included\b",
    r"\bcharger not included\b",
    r"\bno charger supplied\b",
    r"\bwithout charger\b",
    r"\binternal power supply only\b",
    r"\bdirect mains\b",
]

POWER_INTERNAL_PATTERNS = [
    r"\binternal power supply\b",
    r"\bintegrated power supply\b",
    r"\bdirect mains\b",
    r"\b230 ?v\b",
    r"\b230v\b",
    r"\bhardwired\b",
    r"\bbuilt in transformer\b",
]

WEARABLE_PATTERNS = [
    r"\bwearable\b",
    r"\bwrist\b",
    r"\bwatch\b",
    r"\bring\b",
    r"\bheadset\b",
    r"\bearbud",
    r"\bear ?worn\b",
    r"\bbody ?worn\b",
    r"\bbody mounted\b",
    r"\bon body\b",
    r"\bon the body\b",
    r"\bon skin\b",
    r"\bskin contact\b",
    r"\bclip on\b",
]

HANDHELD_PATTERNS = [
    r"\bhandheld\b",
    r"\bhand held\b",
    r"\bportable\b",
    r"\bheld in hand\b",
    r"\bshaver\b",
    r"\btrimmer\b",
    r"\btoothbrush\b",
    r"\bwater flosser\b",
]

CLOSE_PROXIMITY_PATTERNS = [
    r"\bclose to the body\b",
    r"\bused near the body\b",
    r"\bused on the body\b",
    r"\bbody worn\b",
    r"\bbody mounted\b",
    r"\bhead\b",
    r"\bear\b",
    r"\bface\b",
]

LASER_SOURCE_PATTERNS = [
    r"\blaser\b",
    r"\blidar\b",
    r"\blaser scanner\b",
    r"\brangefinder\b",
    r"\blaser projector\b",
    r"\blaser module\b",
]

PHOTOBIOLOGICAL_SOURCE_PATTERNS = [
    r"\bprojector\b",
    r"\blamp\b",
    r"\blighting\b",
    r"\bluminaire\b",
    r"\bspotlight\b",
    r"\bfloodlight\b",
    r"\bflashlight\b",
    r"\btorch\b",
    r"\buv\b",
    r"\bultraviolet\b",
    r"\binfrared\b",
    r"\bir emitter\b",
    r"\bir lamp\b",
    r"\bgrow light\b",
    r"\bstage light\b",
    r"\bdisinfection lamp\b",
    r"\bdisinfection light\b",
    r"\bphototherapy\b",
]

PHOTOBIO_PRODUCT_HINTS = {
    "projector",
    "heating_lamp",
}

PERSONAL_CARE_PRODUCT_HINTS = {
    "shaver",
    "hair_clipper",
    "battery_powered_oral_hygiene",
    "skin_hair_care_appliance",
    "beauty_treatment_appliance",
}

AV_ICT_PRODUCT_HINTS = {
    "smart_speaker",
    "smart_display",
    "router",
    "modem",
    "iot_gateway",
    "network_switch",
    "wireless_access_point",
    "laptop",
    "desktop_pc",
    "server",
    "nas",
    "monitor",
    "smart_tv",
    "streaming_device",
    "set_top_box",
    "projector",
}

APPLIANCE_PRIMARY_TRAITS = {
    "air_cleaning",
    "air_treatment",
    "beverage_preparation",
    "cleaning",
    "coffee_brewing",
    "cooking",
    "cooling",
    "dehumidification",
    "drying",
    "extraction",
    "food_contact",
    "food_preparation",
    "garden_use",
    "hair_care",
    "heating",
    "heating_personal_environment",
    "humidification",
    "motorized",
    "oral_care",
    "personal_care",
    "surface_cleaning",
    "steam",
    "textile_care",
    "water_contact",
    "water_heating",
    "washing",
}

AV_ICT_SUPPORTING_TRAITS = {
    "av_ict",
    "camera",
    "data_storage",
    "display",
    "microphone",
    "speaker",
}


def _scope_route(
    traits: set[str],
    matched_products: set[str],
    product_type: str | None,
    confirmed_traits: set[str] | None = None,
) -> tuple[str, list[str]]:
    confirmed_traits = confirmed_traits or set()
    reasons: list[str] = []

    appliance_signals = set(APPLIANCE_PRIMARY_TRAITS) & traits
    av_ict_signals = {"av_ict"} & traits

    if matched_products & AV_ICT_PRODUCT_HINTS:
        reasons.append("matched_av_ict_product")
        av_ict_signals.add("av_ict")
    if product_type in AV_ICT_PRODUCT_HINTS:
        reasons.append(f"primary_product={product_type}")
        av_ict_signals.add("av_ict")

    if not av_ict_signals and (AV_ICT_SUPPORTING_TRAITS & confirmed_traits) and not appliance_signals:
        reasons.append("confirmed_av_ict_signals")
        av_ict_signals.add("av_ict")

    if appliance_signals and not av_ict_signals:
        reasons.append("appliance_primary_traits=" + ",".join(sorted(appliance_signals)))
        return "appliance", reasons
    if av_ict_signals and not appliance_signals:
        reasons.append("av_ict_primary")
        return "av_ict", reasons
    if av_ict_signals and appliance_signals:
        reasons.append("convergent_product_boundary")
        if product_type in AV_ICT_PRODUCT_HINTS:
            reasons.append("resolved_by_primary_product=av_ict")
            return "av_ict", reasons
        if product_type and product_type not in AV_ICT_PRODUCT_HINTS:
            reasons.append("resolved_by_primary_product=appliance")
            return "appliance", reasons
        return "convergent", reasons
    return "generic", reasons


def _has_any(text: str, patterns: list[str]) -> bool:
    return any(re.search(pattern, text) for pattern in patterns)


def _directive_rank(key: str) -> int:
    try:
        return DIRECTIVE_ORDER.index(key)
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


def _analysis_depth(depth: str) -> str:
    return depth if depth in {"quick", "standard", "deep"} else "standard"


def _current_date() -> date:
    return date.today()


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


def _timing_status(row: dict[str, Any], today: date) -> str:
    if row.get("bucket") == "informational":
        return "informational"

    applicable_from = _parse_date(row.get("applicable_from"))
    applicable_until = _parse_date(row.get("applicable_until"))

    if applicable_from and today < applicable_from:
        return "future"
    if applicable_until and today > applicable_until:
        return "legacy"
    return "current"


def _fact_basis_for_legislation(
    row: dict[str, Any],
    traits: set[str],
    confirmed_traits: set[str],
) -> str:
    relevant = (
        set(_string_list(row.get("all_of_traits")))
        | (set(_string_list(row.get("any_of_traits"))) & traits)
        | (set(_string_list(row.get("none_of_traits"))) & traits)
    )
    if not relevant:
        return "confirmed"
    if relevant.issubset(confirmed_traits):
        return "confirmed"
    if relevant & confirmed_traits:
        return "mixed"
    return "inferred"


def _legislation_matches(
    row: dict[str, Any],
    traits: set[str],
    functional_classes: set[str],
    product_type: str | None,
    matched_products: set[str],
    product_genres: set[str],
) -> bool:
    all_of_traits = set(_string_list(row.get("all_of_traits")))
    any_of_traits = set(_string_list(row.get("any_of_traits")))
    none_of_traits = set(_string_list(row.get("none_of_traits")))
    all_of_classes = set(_string_list(row.get("all_of_functional_classes")))
    any_of_classes = set(_string_list(row.get("any_of_functional_classes")))
    none_of_classes = set(_string_list(row.get("none_of_functional_classes")))
    any_of_products = set(_string_list(row.get("any_of_product_types")))
    exclude_products = set(_string_list(row.get("exclude_product_types")))
    any_of_genres = set(_string_list(row.get("any_of_genres")))
    exclude_genres = set(_string_list(row.get("exclude_genres")))

    if all_of_traits and not all_of_traits.issubset(traits):
        return False
    if any_of_traits and not (any_of_traits & traits):
        return False
    if none_of_traits & traits:
        return False

    if all_of_classes and not all_of_classes.issubset(functional_classes):
        return False
    if any_of_classes and not (any_of_classes & functional_classes):
        return False
    if none_of_classes & functional_classes:
        return False

    candidate_products = set(matched_products)
    if product_type:
        candidate_products.add(product_type)

    product_hit = not any_of_products or bool(candidate_products & any_of_products)
    genre_hit = not any_of_genres or bool(product_genres & any_of_genres)

    if candidate_products & exclude_products:
        return False
    if product_genres & exclude_genres:
        return False
    if any_of_products and any_of_genres:
        if not (product_hit or genre_hit):
            return False
    elif not product_hit or not genre_hit:
        return False

    return True


def _legislation_sort_key(row: dict[str, Any]) -> tuple[int, int, str]:
    timing_rank = {"current": 0, "future": 1, "legacy": 2, "informational": 3}
    return (
        _directive_rank(str(row.get("directive_key") or "OTHER")),
        timing_rank.get(str(row.get("timing_status") or "current"), 9),
        str(row.get("code") or ""),
    )


def _directive_keys(items: list[LegislationItem]) -> list[str]:
    keys: list[str] = []
    for item in items:
        if item.directive_key not in keys:
            keys.append(item.directive_key)
    return keys


def _pick_legislations(
    traits: set[str],
    functional_classes: set[str],
    product_type: str | None,
    forced_directives: list[str] | None = None,
    matched_products: set[str] | None = None,
    product_genres: set[str] | None = None,
    confirmed_traits: set[str] | None = None,
) -> list[dict[str, Any]]:
    matched_products = matched_products or set()
    product_genres = product_genres or set()
    confirmed_traits = confirmed_traits or set(traits)
    forced_set = {item for item in (forced_directives or []) if item}
    today = _current_date()

    picked: list[dict[str, Any]] = []
    for row in load_legislations():
        directive_key = str(row.get("directive_key") or "OTHER")
        matched = _legislation_matches(row, traits, functional_classes, product_type, matched_products, product_genres)
        forced = directive_key in forced_set and row.get("bucket") != "informational"
        if not matched and not forced:
            continue

        enriched = dict(row)
        enriched["timing_status"] = _timing_status(enriched, today)
        enriched["evidence_strength"] = _fact_basis_for_legislation(enriched, traits, confirmed_traits)
        enriched["is_forced"] = forced
        if forced and not matched:
            enriched["applicability"] = "conditional"
        picked.append(enriched)

    picked.sort(key=_legislation_sort_key)
    return picked


def _confidence_from_score(score: int) -> ConfidenceLevel:
    if score >= 95:
        return "high"
    if score >= 55:
        return "medium"
    return "low"


def _derive_engine_traits(description: str, traits: set[str], matched_products: set[str]) -> tuple[set[str], list[str]]:
    text = normalize(description)
    diagnostics: list[str] = []
    derived = set(traits)

    if _has_any(text, POWER_EXTERNAL_NEGATION_PATTERNS):
        derived.discard("external_psu")
        derived.add("internal_power_supply")
        diagnostics.append("engine_trait=internal_power_supply")
    elif _has_any(text, POWER_EXTERNAL_PATTERNS):
        derived.add("external_psu")
        diagnostics.append("engine_trait=external_psu")
    elif _has_any(text, POWER_INTERNAL_PATTERNS):
        derived.add("internal_power_supply")
        diagnostics.append("engine_trait=internal_power_supply")

    if _has_any(text, WEARABLE_PATTERNS):
        derived.add("wearable")
        derived.add("body_worn_or_applied")
        diagnostics.append("engine_trait=wearable/body_worn_or_applied")
    if _has_any(text, HANDHELD_PATTERNS):
        derived.add("handheld")
        diagnostics.append("engine_trait=handheld")
    if _has_any(text, CLOSE_PROXIMITY_PATTERNS):
        derived.add("body_worn_or_applied")
        diagnostics.append("engine_trait=close_proximity")

    if matched_products & PERSONAL_CARE_PRODUCT_HINTS:
        derived.add("handheld")
        diagnostics.append("engine_trait=handheld_from_product")

    if "radio" in derived and ({"wearable", "handheld", "body_worn_or_applied"} & derived):
        derived.add("close_proximity_emf")
        diagnostics.append("engine_trait=close_proximity_emf")
    elif "radio" in derived and "clock" in matched_products:
        derived.add("low_power_radio")
        diagnostics.append("engine_trait=low_power_radio")

    return derived, diagnostics


def _match_standard(
    row: dict[str, Any],
    traits: set[str],
    matched_products: set[str],
    likely_standards: set[str],
) -> tuple[bool, int, dict[str, Any]]:
    applies_products = set(row.get("applies_if_products") or [])
    exclude_products = set(row.get("exclude_if_products") or [])
    requires_all = set(row.get("applies_if_all") or [])
    requires_any = set(row.get("applies_if_any") or [])
    excludes = set(row.get("exclude_if") or [])

    meta = {
        "matched_traits_all": sorted(requires_all & traits),
        "matched_traits_any": sorted(requires_any & traits),
        "missing_required_traits": sorted(requires_all - traits),
        "excluded_by_traits": sorted(excludes & traits),
        "product_match_type": None,
    }

    if exclude_products & matched_products:
        return False, 0, meta
    if excludes & traits:
        return False, 0, meta
    if requires_all and not requires_all.issubset(traits):
        return False, 0, meta

    product_match = False
    if applies_products:
        product_match = bool(applies_products & matched_products)
        if not product_match:
            return False, 0, meta
        meta["product_match_type"] = "product"

    if requires_any and not (requires_any & traits):
        return False, 0, meta

    score = 20
    if product_match:
        score += 42
    score += len(requires_all & traits) * 8
    score += len(requires_any & traits) * 5
    if row.get("code") in likely_standards or row.get("standard_family") in likely_standards:
        score += 28
        meta["product_match_type"] = meta["product_match_type"] or "preferred_product"
    if row.get("item_type", "standard") == "review":
        score -= 8
    return True, score, meta


def _standard_primary_directive(row: dict[str, Any], traits: set[str]) -> str:
    code = str(row.get("code") or "")
    directive = row.get("legislation_key") or (row.get("directives") or ["OTHER"])[0]

    if code.startswith("EN 18031-"):
        return "RED_CYBER"
    if code == "EN 62311":
        return "RED" if "radio" in traits else "LVD"
    if directive == "RED" and code.startswith("EN 301 489-"):
        return "RED"
    return directive or "OTHER"


def _derive_directives(traits: set[str], forced_directives: list[str] | None = None) -> list[str]:
    directives: list[str] = []

    if "electrical" in traits and ({"mains_powered", "mains_power_likely"} & traits):
        directives.append("LVD")
    if "electrical" in traits and "radio" not in traits:
        directives.append("EMC")
    if "radio" in traits:
        directives.append("RED")
    if "radio" in traits and ({"internet", "wifi", "bluetooth", "cellular", "app_control", "ota", "cloud"} & traits):
        directives.append("RED_CYBER")
    if "electrical" in traits or "electronic" in traits:
        directives.extend(["ROHS", "REACH"])
    if "battery_powered" in traits:
        directives.append("BATTERY")
    if "external_psu" in traits or "electronic" in traits or "radio" in traits:
        directives.append("ECO")
    if "electronic" in traits and ({"cloud", "internet", "ota", "app_control"} & traits):
        directives.append("CRA")
    if {"personal_data_likely", "camera", "microphone", "account", "location"} & traits:
        directives.append("GDPR")

    for directive in forced_directives or []:
        if directive and directive not in directives:
            directives.append(directive)

    return [d for i, d in enumerate(directives) if d not in directives[:i]]


def _apply_post_selection_gates_v1(
    selected: list[dict[str, Any]],
    traits: set[str],
    matched_products: set[str],
    diagnostics: list[str],
    allowed_directives: set[str],
    product_type: str | None = None,
    confirmed_traits: set[str] | None = None,
    description: str = "",
) -> list[dict[str, Any]]:
    kept: list[dict[str, Any]] = []
    scope_route, scope_reasons = _scope_route(traits, matched_products, product_type, confirmed_traits)
    diagnostics.append("scope_route=" + scope_route)
    if scope_reasons:
        diagnostics.append("scope_route_reasons=" + ";".join(scope_reasons))

    text = normalize(description)
    has_external_psu = "external_psu" in traits or bool(matched_products & {"battery_charger", "industrial_charger"})
    has_laser_source = "laser" in traits or _has_any(text, LASER_SOURCE_PATTERNS)
    has_photobiological_source = (
        has_laser_source
        or bool(matched_products & PHOTOBIO_PRODUCT_HINTS)
        or (product_type in PHOTOBIO_PRODUCT_HINTS if product_type else False)
        or _has_any(text, PHOTOBIOLOGICAL_SOURCE_PATTERNS)
    )
    prefer_specific_red_emf = bool(
        "radio" in traits and ({"cellular", "wearable", "handheld", "body_worn_or_applied", "close_proximity_emf"} & traits)
    )
    prefer_62233 = (
        scope_route != "av_ict"
        and "electrical" in traits
        and "consumer" in traits
        and "household" in traits
        and ({"heating", "motorized", "mains_powered", "mains_power_likely"} & traits)
        and "wearable" not in traits
        and "handheld" not in traits
        and "body_worn_or_applied" not in traits
    )
    prefer_62311 = (
        "electrical" in traits
        and (
            scope_route == "av_ict"
            or "wearable" in traits
            or "handheld" in traits
            or "body_worn_or_applied" in traits
            or ("radio" in traits and "consumer" not in traits)
            or bool(matched_products & PERSONAL_CARE_PRODUCT_HINTS)
        )
    )

    for item in selected:
        code = str(item.get("code") or "")
        route = str(item.get("directive") or "OTHER")

        if route not in allowed_directives and route != "OTHER":
            diagnostics.append(f"gate=drop_{code}:directive_{route}_not_selected")
            continue

        if code == "Charger / external PSU review":
            if not has_external_psu:
                diagnostics.append("gate=drop_external_psu_review:no_external_psu_signal")
                continue
            item["directive"] = "LVD"
            item["legislation_key"] = "LVD"
        elif code == "EN 50563":
            if not has_external_psu:
                diagnostics.append("gate=drop_EN50563:no_external_psu_signal")
                continue
            item["directive"] = "ECO"
            item["legislation_key"] = "ECO"

        if code == "EN 62368-1":
            if scope_route == "appliance":
                diagnostics.append("gate=drop_EN62368-1:appliance_primary")
                continue
            if "radio" in traits and "RED" in allowed_directives and "LVD" not in allowed_directives:
                item["directive"] = "RED"
                item["legislation_key"] = "RED"

        if code.startswith("EN 60335-") and scope_route == "av_ict":
            diagnostics.append(f"gate=drop_{code}:av_ict_primary")
            continue

        if code in {"EN 55032", "EN 55035"} and scope_route == "appliance":
            diagnostics.append(f"gate=drop_{code}:appliance_primary")
            continue

        if code.startswith("EN 55014-") and scope_route == "av_ict":
            diagnostics.append(f"gate=drop_{code}:av_ict_primary")
            continue

        if code == "EN 62233" and prefer_62311 and not prefer_62233:
            diagnostics.append("gate=drop_EN62233:prefer_EN62311")
            continue

        if code == "EN 62311":
            if prefer_62233 and not ("radio" in traits and ({"wearable", "handheld", "body_worn_or_applied"} & traits)):
                diagnostics.append("gate=drop_EN62311:prefer_EN62233")
                continue
            if "radio" in traits:
                item["directive"] = "RED"
                item["legislation_key"] = "RED"
            else:
                item["directive"] = "LVD"
                item["legislation_key"] = "LVD"

        if code == "EN 60825-1" and not has_laser_source:
            diagnostics.append("gate=drop_EN60825-1:no_laser_source")
            continue

        if code == "EN 62471" and not has_photobiological_source:
            diagnostics.append("gate=drop_EN62471:no_photobiological_source")
            continue

        if code == "EN 62479":
            if "radio" not in traits:
                diagnostics.append("gate=drop_EN62479:no_radio_signal")
                continue
            if prefer_specific_red_emf:
                diagnostics.append("gate=drop_EN62479:prefer_specific_red_emf_route")
                continue

        if code.startswith("EN 62209") and not (
            "radio" in traits and ({"wearable", "handheld", "body_worn_or_applied", "cellular"} & traits)
        ):
            diagnostics.append(f"gate=drop_{code}:not_close_proximity_radio")
            continue

        if route == "EMC" and code == "Charger / external PSU review":
            diagnostics.append("gate=drop_external_psu_from_emc")
            continue

        kept.append(item)

    household_part2_selected = any(
        str(item.get("code") or "").startswith("EN 60335-2-") and item.get("item_type") == "standard"
        for item in kept
    )
    if household_part2_selected:
        for item in kept:
            if str(item.get("code") or "") != "EN 60335-1" or item.get("item_type") != "review":
                continue
            item["item_type"] = "standard"
            item["fact_basis"] = "confirmed"
            reason = item.get("reason")
            if isinstance(reason, str):
                item["reason"] = reason.replace(
                    ". some routing traits are inferred from product context and still need confirmation",
                    "",
                )
            diagnostics.append("gate=promote_EN60335-1:paired_with_household_part2")

    codes = {str(item.get("code") or "") for item in kept}
    if "EN 62233" in codes and "EN 62311" in codes and prefer_62233:
        kept = [item for item in kept if item.get("code") != "EN 62311"]
        diagnostics.append("gate=prune_EN62311_after_pairing")
    elif "EN 62233" in codes and "EN 62311" in codes and prefer_62311:
        kept = [item for item in kept if item.get("code") != "EN 62233"]
        diagnostics.append("gate=prune_EN62233_after_pairing")

    codes = {str(item.get("code") or "") for item in kept}
    if (
        "Battery safety review" in codes
        and "EN 62133-2" in codes
        and scope_route == "av_ict"
        and not ({"wearable", "handheld", "body_worn_or_applied", "replaceable_battery"} & traits)
    ):
        kept = [item for item in kept if item.get("code") != "Battery safety review"]
        diagnostics.append("gate=prune_Battery_safety_review:covered_by_EN62133-2")

    return kept


def _standard_context(
    traits: set[str],
    matched_products: set[str],
    product_type: str | None,
    confirmed_traits: set[str] | None,
    description: str,
) -> dict[str, Any]:
    scope_route, scope_reasons = _scope_route(traits, matched_products, product_type, confirmed_traits)
    text = normalize(description)
    has_external_psu = "external_psu" in traits or bool(matched_products & {"battery_charger", "industrial_charger"})
    has_laser_source = "laser" in traits or _has_any(text, LASER_SOURCE_PATTERNS)
    has_photobiological_source = (
        has_laser_source
        or bool(matched_products & PHOTOBIO_PRODUCT_HINTS)
        or (product_type in PHOTOBIO_PRODUCT_HINTS if product_type else False)
        or _has_any(text, PHOTOBIOLOGICAL_SOURCE_PATTERNS)
    )
    prefer_specific_red_emf = bool(
        "radio" in traits and ({"cellular", "wearable", "handheld", "body_worn_or_applied", "close_proximity_emf"} & traits)
    )
    prefer_62233 = (
        scope_route != "av_ict"
        and "electrical" in traits
        and "consumer" in traits
        and "household" in traits
        and ({"heating", "motorized", "mains_powered", "mains_power_likely"} & traits)
        and "wearable" not in traits
        and "handheld" not in traits
        and "body_worn_or_applied" not in traits
    )
    prefer_62311 = (
        "electrical" in traits
        and (
            scope_route == "av_ict"
            or "wearable" in traits
            or "handheld" in traits
            or "body_worn_or_applied" in traits
            or ("radio" in traits and "consumer" not in traits)
            or bool(matched_products & PERSONAL_CARE_PRODUCT_HINTS)
        )
    )

    context_tags: set[str] = {f"scope:{scope_route}"}
    if has_external_psu:
        context_tags.add("power:external_psu")
    if has_laser_source:
        context_tags.add("optical:laser")
    if has_photobiological_source:
        context_tags.add("optical:photobio")
    if prefer_specific_red_emf:
        context_tags.add("exposure:close_proximity")
    if prefer_62233:
        context_tags.add("exposure:household_emf")

    return {
        "scope_route": scope_route,
        "scope_reasons": scope_reasons,
        "text": text,
        "context_tags": context_tags,
        "has_external_psu": has_external_psu,
        "has_laser_source": has_laser_source,
        "has_photobiological_source": has_photobiological_source,
        "prefer_specific_red_emf": prefer_specific_red_emf,
        "prefer_62233": prefer_62233,
        "prefer_62311": prefer_62311,
    }


def _apply_post_selection_gates(
    selected: list[dict[str, Any]],
    traits: set[str],
    matched_products: set[str],
    diagnostics: list[str],
    allowed_directives: set[str],
    product_type: str | None = None,
    confirmed_traits: set[str] | None = None,
    description: str = "",
) -> list[dict[str, Any]]:
    kept: list[dict[str, Any]] = []
    context = _standard_context(traits, matched_products, product_type, confirmed_traits, description)
    diagnostics.append("scope_route=" + context["scope_route"])
    if context["scope_reasons"]:
        diagnostics.append("scope_route_reasons=" + ";".join(context["scope_reasons"]))
    diagnostics.append("standard_context_tags=" + ",".join(sorted(context["context_tags"])))

    for item in selected:
        code = str(item.get("code") or "")
        route = str(item.get("directive") or item.get("legislation_key") or "OTHER")

        if code == "Charger / external PSU review":
            if not context["has_external_psu"]:
                diagnostics.append("gate=drop_external_psu_review:no_external_psu_signal")
                continue
            item["directive"] = "LVD"
            item["legislation_key"] = "LVD"
        elif code == "EN 50563":
            if not context["has_external_psu"]:
                diagnostics.append("gate=drop_EN50563:no_external_psu_signal")
                continue
            item["directive"] = "ECO"
            item["legislation_key"] = "ECO"

        if code == "EN 62368-1" and "radio" in traits and "RED" in allowed_directives and "LVD" not in allowed_directives:
            item["directive"] = "RED"
            item["legislation_key"] = "RED"

        if code == "EN 62311":
            if context["prefer_62233"] and not ("radio" in traits and ({"wearable", "handheld", "body_worn_or_applied"} & traits)):
                diagnostics.append("gate=drop_EN62311:prefer_EN62233")
                continue
            item["directive"] = "RED" if "radio" in traits else "LVD"
            item["legislation_key"] = item["directive"]

        if code == "EN 60825-1" and not context["has_laser_source"]:
            diagnostics.append("gate=drop_EN60825-1:no_laser_source")
            continue

        if code == "EN 62471" and not context["has_photobiological_source"]:
            diagnostics.append("gate=drop_EN62471:no_photobiological_source")
            continue

        if code == "EN 62479":
            if "radio" not in traits:
                diagnostics.append("gate=drop_EN62479:no_radio_signal")
                continue
            if context["prefer_specific_red_emf"]:
                diagnostics.append("gate=drop_EN62479:prefer_specific_red_emf_route")
                continue

        if code.startswith("EN 62209") and not (
            "radio" in traits and ({"wearable", "handheld", "body_worn_or_applied", "cellular"} & traits)
        ):
            diagnostics.append(f"gate=drop_{code}:not_close_proximity_radio")
            continue

        if route == "EMC" and code == "Charger / external PSU review":
            diagnostics.append("gate=drop_external_psu_from_emc")
            continue

        route = str(item.get("directive") or item.get("legislation_key") or "OTHER")
        if route not in allowed_directives and route != "OTHER":
            diagnostics.append(f"gate=drop_{code}:directive_{route}_not_selected")
            continue

        kept.append(item)

    household_part2_selected = any(
        str(item.get("code") or "").startswith("EN 60335-2-") and item.get("item_type") == "standard"
        for item in kept
    )
    if household_part2_selected:
        for item in kept:
            if str(item.get("code") or "") != "EN 60335-1" or item.get("item_type") != "review":
                continue
            item["item_type"] = "standard"
            item["fact_basis"] = "confirmed"
            reason = item.get("reason")
            if isinstance(reason, str):
                item["reason"] = reason.replace(
                    ". some routing traits are inferred from product context and still need confirmation",
                    "",
                )
            diagnostics.append("gate=promote_EN60335-1:paired_with_household_part2")

    codes = {str(item.get("code") or "") for item in kept}
    if "EN 62233" in codes and "EN 62311" in codes and context["prefer_62233"]:
        kept = [item for item in kept if item.get("code") != "EN 62311"]
        diagnostics.append("gate=prune_EN62311_after_pairing")
    elif "EN 62233" in codes and "EN 62311" in codes and context["prefer_62311"]:
        kept = [item for item in kept if item.get("code") != "EN 62233"]
        diagnostics.append("gate=prune_EN62233_after_pairing")

    codes = {str(item.get("code") or "") for item in kept}
    if (
        "Battery safety review" in codes
        and "EN 62133-2" in codes
        and context["scope_route"] == "av_ict"
        and not ({"wearable", "handheld", "body_worn_or_applied", "replaceable_battery"} & traits)
    ):
        kept = [item for item in kept if item.get("code") != "Battery safety review"]
        diagnostics.append("gate=prune_Battery_safety_review:covered_by_EN62133-2")

    codes = {str(item.get("code") or "") for item in kept}
    if "EN 60335 review" in codes and any(code == "EN 60335-1" or code.startswith("EN 60335-2-") for code in codes):
        kept = [item for item in kept if item.get("code") != "EN 60335 review"]
        diagnostics.append("gate=prune_EN60335_review:covered_by_specific_EN60335_route")

    return kept


def _sort_standard_items(items: list[StandardItem]) -> list[StandardItem]:
    def key(item: StandardItem) -> tuple[int, int, str]:
        code = item.code or ""
        if item.directive == "LVD":
            if code == "EN 60335-1":
                bucket = 0
            elif code.startswith("EN 60335-2-"):
                bucket = 1
            elif code in {"EN 62233", "EN 62311", "EN 62479"}:
                bucket = 2
            else:
                bucket = 3
        elif item.directive == "EMC":
            if code.startswith("EN 55014-"):
                bucket = 0
            elif code.startswith("EN 61000-3-"):
                bucket = 1
            else:
                bucket = 2
        elif item.directive == "RED":
            if code.startswith("EN 300 ") or code.startswith("EN 301 "):
                bucket = 0
            elif code in {"EN 62479", "EN 62311", "EN 50364"} or code.startswith("EN 62209"):
                bucket = 1
            else:
                bucket = 2
        else:
            bucket = 9
        return (_directive_rank(item.directive), bucket, code)

    return sorted(items, key=key)


def _build_legislation_sections(
    traits: set[str],
    functional_classes: set[str],
    product_type: str | None,
    matched_products: set[str],
    product_genres: set[str],
    confirmed_traits: set[str],
    forced_directives: list[str] | None = None,
) -> tuple[list[LegislationItem], list[dict[str, Any]], list[str]]:
    picked_rows = _pick_legislations(
        traits=traits,
        functional_classes=functional_classes,
        product_type=product_type,
        forced_directives=forced_directives,
        matched_products=matched_products,
        product_genres=product_genres,
        confirmed_traits=confirmed_traits,
    )

    items: list[LegislationItem] = []
    for row in picked_rows:
        items.append(
            LegislationItem(
                code=str(row.get("code") or ""),
                title=str(row.get("title") or ""),
                family=str(row.get("family") or row.get("title") or ""),
                legal_form=str(row.get("legal_form") or "Other"),
                priority=row.get("priority", "conditional"),
                applicability=row.get("applicability", "conditional"),
                directive_key=str(row.get("directive_key") or "OTHER"),
                bucket=row.get("bucket", "non_ce"),
                timing_status=row.get("timing_status", "current"),
                reason=row.get("reason"),
                triggers=_string_list(row.get("triggers")),
                doc_impacts=_string_list(row.get("doc_impacts")),
                notes=row.get("notes"),
                applicable_from=row.get("applicable_from"),
                applicable_until=row.get("applicable_until"),
                replaced_by=row.get("replaced_by"),
                evidence_strength=row.get("evidence_strength", "confirmed"),
                is_forced=bool(row.get("is_forced")),
            )
        )

    sections_dict: dict[str, dict[str, Any]] = {
        "ce": {"key": "ce", "title": "CE routes", "items": []},
        "non_ce": {"key": "non_ce", "title": "Parallel obligations", "items": []},
        "framework": {"key": "framework", "title": "Additional framework checks", "items": []},
        "future": {"key": "future", "title": "Future / lifecycle watchlist", "items": []},
        "informational": {"key": "informational", "title": "Informational notices", "items": []},
    }
    for item in items:
        sections_dict[item.bucket]["items"].append(item.model_dump())
    sections = [value for value in sections_dict.values() if value["items"]]

    return items, sections, _directive_keys(items)


def _missing_information(
    traits: set[str],
    matched_products: set[str],
    description: str,
) -> list[MissingInformationItem]:
    text = normalize(description)
    items: list[MissingInformationItem] = []

    def add(
        key: str,
        message: str,
        importance: MissingImportance = "medium",
        examples: list[str] | None = None,
        related: list[str] | None = None,
        route_impact: list[str] | None = None,
    ) -> None:
        items.append(
            MissingInformationItem(
                key=key,
                message=message,
                importance=importance,
                examples=examples or [],
                related_traits=related or [],
                route_impact=route_impact or [],
            )
        )

    if "mains_powered" not in traits and "mains_power_likely" not in traits and "battery_powered" not in traits:
        add(
            "power_source",
            "Confirm whether the product is mains-powered, battery-powered, or both.",
            "high",
            ["230 V mains powered", "rechargeable lithium battery", "mains plus battery backup"],
            ["mains_powered", "battery_powered"],
            ["LVD", "BATTERY", "ECO"],
        )
    if "radio" in traits and not any(t in traits for t in ["wifi", "bluetooth", "cellular", "zigbee", "thread", "nfc"]):
        add(
            "radio_technology",
            "Confirm the actual radio technology.",
            "high",
            ["Wi-Fi radio", "Bluetooth LE radio", "NFC radio"],
            ["radio"],
            ["RED", "RED_CYBER"],
        )
    if "wifi" in traits and "wifi_5ghz" not in traits:
        add(
            "wifi_band",
            "Confirm whether Wi-Fi is 2.4 GHz only or also 5 GHz.",
            "medium",
            ["2.4 GHz only", "dual-band 2.4/5 GHz"],
            ["wifi", "wifi_5ghz"],
            ["RED"],
        )
    if ({"usb_powered", "external_psu"} & traits or "adapter" in text) and "external_psu" not in traits and not _has_any(text, POWER_EXTERNAL_NEGATION_PATTERNS):
        add(
            "external_psu",
            "Confirm whether an external adapter or charger is supplied with the product.",
            "high",
            ["external AC/DC adapter included", "USB-C PD power adapter included", "internal PSU only"],
            ["external_psu"],
            ["LVD", "ECO"],
        )
    if "radio" in traits and not ({"wearable", "handheld", "body_worn_or_applied"} & traits) and bool(matched_products & PERSONAL_CARE_PRODUCT_HINTS):
        add(
            "emf_use_position",
            "Confirm whether the radio function is used close to the body or only at separation distance.",
            "medium",
            ["body-worn use", "handheld close to face", "countertop use only"],
            ["wearable", "handheld", "body_worn_or_applied"],
            ["RED"],
        )
    if "radio" in traits and ({"portable", "battery_powered", "cellular"} & traits or bool(matched_products & PERSONAL_CARE_PRODUCT_HINTS)) and not ({"handheld", "wearable", "body_worn_or_applied"} & traits):
        add(
            "rf_exposure_form_factor",
            "Confirm whether the radio product is handheld, body-worn, wearable, or used only with separation distance.",
            "medium",
            ["handheld use", "body-worn wearable use", "desktop use with separation distance"],
            ["handheld", "wearable", "body_worn_or_applied"],
            ["RED"],
        )
    if "cloud" in traits or "app_control" in traits or "ota" in traits:
        add(
            "connectivity_architecture",
            "Confirm cloud dependency, authentication, and software update route.",
            "high",
            ["cloud account required", "local LAN control without cloud dependency", "OTA firmware updates"],
            ["cloud", "app_control", "ota"],
            ["RED_CYBER", "CRA", "GDPR"],
        )
    if "av_ict" in traits and (APPLIANCE_PRIMARY_TRAITS & traits):
        add(
            "primary_function_boundary",
            "Confirm whether the primary function is household appliance operation or AV/ICT signal processing / communication equipment.",
            "high",
            [
                "primary function is heating, cleaning, cooking, pumping, or another appliance task",
                "primary function is audio, video, display, computing, or network communication",
            ],
            ["av_ict"],
            ["LVD", "EMC", "RED"],
        )
    return items[:8]


def _build_quick_adds(missing: list[MissingInformationItem]) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    seen: set[str] = set()
    for item in missing:
        for example in item.examples[:2]:
            if example in seen:
                continue
            seen.add(example)
            out.append({"label": item.key.replace("_", " "), "text": example})
    return out[:10]


def _build_standard_sections(items: list[StandardItem]) -> list[dict[str, Any]]:
    grouped: dict[str, list[StandardItem]] = defaultdict(list)
    for item in items:
        route_key = item.directive or (item.directives[0] if item.directives else "OTHER")
        grouped[route_key].append(item)
    sections: list[dict[str, Any]] = []
    for key in sorted(grouped.keys(), key=_directive_rank):
        route_items = _sort_standard_items(grouped[key])
        sections.append(
            {
                "key": key,
                "title": _route_title(key),
                "count": len(route_items),
                "items": [item.model_dump() for item in route_items],
            }
        )
    return sections


def _build_summary(directives: list[str], standards: list[StandardItem], review_items: list[StandardItem], traits: set[str]) -> str:
    parts: list[str] = []
    if standards:
        parts.append(f"{len(standards)} standard routes identified")
    if review_items:
        parts.append(f"{len(review_items)} review-dependent routes identified")
    if directives:
        readable = ", ".join(DIRECTIVE_TITLES.get(d, (d, d))[0] for d in directives)
        parts.append(f"primary legislation: {readable}")
    if "radio" in traits and "RED_CYBER" in directives:
        parts.append("RED cybersecurity gating is active because connected radio functionality was detected")
    if "external_psu" in traits:
        parts.append("external power supply route retained because adapter or charger evidence was explicitly detected")
    return ". ".join(parts).strip().rstrip(".") + "."


def _directive_label(key: str) -> str:
    return DIRECTIVE_TITLES.get(key, (key, key))[0]


def _join_readable(values: list[str], limit: int = 3) -> str:
    filtered = [value for value in values if value]
    if not filtered:
        return ""
    if len(filtered) <= limit:
        return ", ".join(filtered)
    return ", ".join(filtered[:limit]) + f", +{len(filtered) - limit} more"


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
    depth: str,
    legislation_items: list[LegislationItem],
    standards: list[StandardItem],
    review_items: list[StandardItem],
    missing_items: list[MissingInformationItem],
    contradictions: list[str],
    contradiction_severity: str,
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
        if item.examples:
            action = "Clarify with: " + _join_readable(item.examples, 2)
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


def _current_risk(
    product_confidence: str,
    contradiction_severity: str,
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


def _primary_legislation_by_directive(items: list[LegislationItem]) -> dict[str, LegislationItem]:
    by_directive: dict[str, LegislationItem] = {}
    for item in items:
        existing = by_directive.get(item.directive_key)
        if existing is None:
            by_directive[item.directive_key] = item
            continue

        existing_rank = 1 if existing.bucket == "informational" else 0
        current_rank = 1 if item.bucket == "informational" else 0
        if current_rank < existing_rank:
            by_directive[item.directive_key] = item
    return by_directive


def _standard_item_from_row(
    row: dict[str, Any],
    legislation_by_directive: dict[str, LegislationItem],
    traits: set[str],
) -> StandardItem:
    primary_directive = _standard_primary_directive(row, traits)
    legislation = legislation_by_directive.get(primary_directive)
    return StandardItem(
        code=str(row["code"]),
        title=str(row["title"]),
        directive=primary_directive,
        directives=[str(item) for item in (row.get("directives") or []) if isinstance(item, str)] or [primary_directive],
        legislation_key=row.get("legislation_key"),
        category=str(row.get("category", "other")),
        confidence=_confidence_from_score(int(row.get("score", 0))),
        item_type=row.get("item_type", "standard"),
        match_basis=row.get("match_basis", "traits"),
        fact_basis=row.get("fact_basis", "confirmed"),
        score=int(row.get("score", 0)),
        reason=row.get("reason"),
        notes=row.get("notes"),
        regime_bucket=legislation.bucket if legislation else None,
        timing_status=legislation.timing_status if legislation else "current",
        matched_traits_all=row.get("matched_traits_all", []),
        matched_traits_any=row.get("matched_traits_any", []),
        missing_required_traits=row.get("missing_required_traits", []),
        excluded_by_traits=row.get("excluded_by_traits", []),
        applies_if_products=row.get("applies_if_products", []),
        exclude_if_products=row.get("exclude_if_products", []),
        product_match_type=row.get("product_match_type"),
        standard_family=row.get("standard_family"),
        is_harmonized=row.get("is_harmonized"),
        harmonized_under=row.get("harmonized_under"),
        harmonization_status=row.get("harmonization_status", "unknown"),
        harmonized_reference=row.get("harmonized_reference"),
        version=row.get("version"),
        dated_version=row.get("dated_version"),
        supersedes=row.get("supersedes"),
        test_focus=row.get("test_focus", []),
        evidence_hint=row.get("evidence_hint", []),
        keywords=row.get("keywords", []),
        selection_group=row.get("selection_group"),
        selection_priority=int(row.get("selection_priority", 0)),
        required_fact_basis=row.get("required_fact_basis", "inferred"),
    )


def _normalize_trait_state_map(raw: Any) -> dict[str, dict[str, list[str]]]:
    states = {
        "text_explicit": {},
        "text_inferred": {},
        "product_core": {},
        "product_default": {},
        "engine_derived": {},
    }
    if not isinstance(raw, dict):
        return states

    for state in states:
        value = raw.get(state, {})
        if not isinstance(value, dict):
            continue
        for trait, evidence in value.items():
            if not isinstance(trait, str):
                continue
            if isinstance(evidence, list):
                states[state][trait] = [item for item in evidence if isinstance(item, str)]
            elif isinstance(evidence, str):
                states[state][trait] = [evidence]
    return states


def _trait_evidence_from_state_map(
    state_map: dict[str, dict[str, list[str]]],
    confirmed_traits: set[str],
) -> list[TraitEvidenceItem]:
    states: tuple[TraitEvidenceState, ...] = (
        "text_explicit",
        "text_inferred",
        "product_core",
        "product_default",
        "engine_derived",
    )
    fact_basis_by_state: dict[TraitEvidenceState, FactBasis] = {
        "text_explicit": "confirmed",
        "product_core": "confirmed",
        "text_inferred": "inferred",
        "product_default": "inferred",
        "engine_derived": "inferred",
    }
    items: list[TraitEvidenceItem] = []
    for state in states:
        for trait in sorted(state_map.get(state, {})):
            items.append(
                TraitEvidenceItem(
                    trait=trait,
                    state=state,
                    fact_basis=fact_basis_by_state[state],
                    confirmed=trait in confirmed_traits,
                    evidence=state_map[state][trait],
                )
            )
    return items


def _build_standard_match_audit(items_audit: dict[str, Any], context_tags: set[str]) -> StandardMatchAudit:
    return StandardMatchAudit(
        engine_version=ENGINE_VERSION,
        context_tags=sorted(context_tags),
        selected=[StandardAuditItem.model_validate(item) for item in items_audit.get("selected", [])],
        review=[StandardAuditItem.model_validate(item) for item in items_audit.get("review", [])],
        rejected=[StandardAuditItem.model_validate(item) for item in items_audit.get("rejected", [])],
    )


def _shadow_diff(v1: AnalysisResult, v2: AnalysisResult) -> list[dict[str, Any]]:
    v1_traits = set(v1.confirmed_traits)
    v2_traits = set(v2.confirmed_traits)
    v1_standards = {item.code for item in v1.standards}
    v2_standards = {item.code for item in v2.standards}
    trait_evidence = {item.trait for item in v2.trait_evidence if item.confirmed}
    audited_standard_codes = set()
    if v2.standard_match_audit:
        audited_standard_codes.update(item.code for item in v2.standard_match_audit.selected)
        audited_standard_codes.update(item.code for item in v2.standard_match_audit.review)

    diff: list[dict[str, Any]] = []
    for trait in sorted(v2_traits - v1_traits):
        diff.append(
            {
                "kind": "trait",
                "key": trait,
                "has_evidence": trait in trait_evidence,
            }
        )
    for code in sorted(v2_standards - v1_standards):
        diff.append(
            {
                "kind": "standard",
                "key": code,
                "has_evidence": code in audited_standard_codes,
            }
        )
    return diff


def analyze_v1(
    description: str,
    category: str = "",
    directives: list[str] | None = None,
    depth: str = "standard",
) -> AnalysisResult:
    depth = _analysis_depth(depth)
    traits_data = extract_traits_v1(description=description, category=category)
    diagnostics = list(traits_data.get("diagnostics") or [])
    matched_products = set(traits_data.get("matched_products") or [])
    routing_matched_products = set(traits_data.get("routing_matched_products") or [])
    product_genres = set(traits_data.get("product_genres") or [])
    product_type = traits_data.get("product_type")
    product_match_stage = str(traits_data.get("product_match_stage") or "ambiguous")
    routing_product_type = product_type if product_match_stage == "subtype" else None
    likely_standards: set[str] = set(traits_data.get("preferred_standard_codes") or [])
    for candidate in traits_data.get("product_candidates") or []:
        if candidate.get("id") in routing_matched_products:
            likely_standards.update(candidate.get("likely_standards") or [])

    trait_set = set(traits_data.get("all_traits") or [])
    confirmed_traits = set(traits_data.get("confirmed_traits") or [])
    functional_classes = set(traits_data.get("functional_classes") or [])
    trait_set, extra_diag = _derive_engine_traits(description, trait_set, routing_matched_products)
    diagnostics.extend(extra_diag)

    legislation_items, legislation_sections, detected_directives = _build_legislation_sections(
        traits=trait_set,
        functional_classes=functional_classes,
        product_type=routing_product_type,
        matched_products=routing_matched_products,
        product_genres=product_genres,
        confirmed_traits=confirmed_traits,
        forced_directives=directives,
    )
    legislation_by_directive = _primary_legislation_by_directive(legislation_items)
    allowed_directives = set(detected_directives)

    items = find_applicable_items_v1(
        traits=trait_set,
        directives=detected_directives,
        product_type=routing_product_type,
        matched_products=sorted(routing_matched_products),
        product_genres=sorted(product_genres),
        preferred_standard_codes=sorted(likely_standards),
        explicit_traits=set(traits_data.get("explicit_traits") or []),
        confirmed_traits=confirmed_traits,
    )
    selected_rows = list(items["standards"]) + list(items["review_items"])
    selected_rows = _apply_post_selection_gates_v1(
        selected_rows,
        trait_set,
        routing_matched_products,
        diagnostics,
        allowed_directives,
        product_type=routing_product_type,
        confirmed_traits=confirmed_traits,
        description=description,
    )

    dedup: dict[str, dict[str, Any]] = {}
    for row in selected_rows:
        key = str(row.get("code") or "")
        if key not in dedup or int(row.get("score", 0)) > int(dedup[key].get("score", 0)):
            dedup[key] = row

    standard_items: list[StandardItem] = []
    review_items: list[StandardItem] = []
    for row in dedup.values():
        item = _standard_item_from_row(row, legislation_by_directive, trait_set)
        if item.item_type == "review":
            review_items.append(item)
        else:
            standard_items.append(item)

    standard_items = _sort_standard_items(standard_items)
    review_items = _sort_standard_items(review_items)
    all_standard_items = _sort_standard_items(standard_items + review_items)
    current_review_items = [item for item in review_items if item.timing_status == "current"]
    missing_items = _missing_information(trait_set, routing_matched_products, description)
    standard_sections = _build_standard_sections(all_standard_items)
    primary_regimes = [section["key"] for section in standard_sections[:4]]

    current_risk = _current_risk(
        product_confidence=str(traits_data.get("product_match_confidence") or "low"),
        contradiction_severity=str(traits_data.get("contradiction_severity") or "none"),
        review_items=current_review_items,
        missing_items=missing_items,
    )
    future_risk = _future_risk(detected_directives, trait_set)
    overall_risk: RiskLevel = "LOW"
    if current_risk == "HIGH" or future_risk == "HIGH":
        overall_risk = "HIGH"
    elif current_risk == "MEDIUM" or future_risk == "MEDIUM":
        overall_risk = "MEDIUM"

    stats = AnalysisStats(
        legislation_count=len(legislation_items),
        current_legislation_count=len([x for x in legislation_items if x.timing_status == "current"]),
        future_legislation_count=len([x for x in legislation_items if x.timing_status == "future"]),
        standards_count=len(standard_items),
        review_items_count=len(review_items),
        current_review_items_count=len([x for x in review_items if x.timing_status == "current"]),
        future_review_items_count=len([x for x in review_items if x.timing_status == "future"]),
        harmonized_standards_count=len([x for x in standard_items if x.harmonization_status == "harmonized"]),
        state_of_the_art_standards_count=len([x for x in standard_items if x.harmonization_status == "state_of_the_art"]),
        product_gated_standards_count=len([x for x in standard_items if x.applies_if_products]),
        ambiguity_flag_count=1 if traits_data.get("contradictions") else 0,
        missing_information_count=len(missing_items),
    )

    summary = _build_summary(detected_directives, standard_items, review_items, trait_set)
    findings = _build_findings(
        depth=depth,
        legislation_items=legislation_items,
        standards=standard_items,
        review_items=review_items,
        missing_items=missing_items,
        contradictions=traits_data.get("contradictions") or [],
        contradiction_severity=traits_data.get("contradiction_severity", "none"),
    )
    top_actions_limit = {"quick": 2, "standard": 3, "deep": 5}[depth]
    suggested_questions_limit = {"quick": 2, "standard": 4, "deep": 6}[depth]
    quick_adds_limit = {"quick": 4, "standard": 8, "deep": 10}[depth]

    return AnalysisResult(
        product_summary=description.strip(),
        overall_risk=overall_risk,
        current_compliance_risk=current_risk,
        future_watchlist_risk=future_risk,
        summary=summary,
        product_type=traits_data.get("product_type"),
        product_family=traits_data.get("product_family"),
        product_family_confidence=traits_data.get("product_family_confidence", "low"),
        product_subtype=traits_data.get("product_subtype"),
        product_subtype_confidence=traits_data.get("product_subtype_confidence", "low"),
        product_match_stage=traits_data.get("product_match_stage", "ambiguous"),
        product_match_confidence=traits_data.get("product_match_confidence", "low"),
        product_candidates=traits_data.get("product_candidates") or [],
        functional_classes=traits_data.get("functional_classes") or [],
        confirmed_functional_classes=traits_data.get("confirmed_functional_classes") or [],
        explicit_traits=traits_data.get("explicit_traits") or [],
        confirmed_traits=sorted(confirmed_traits),
        inferred_traits=sorted(set(traits_data.get("inferred_traits") or []) | (trait_set - set(traits_data.get("explicit_traits") or []))),
        all_traits=sorted(trait_set),
        directives=detected_directives,
        forced_directives=[item for item in dict.fromkeys(directives or []) if item],
        legislations=legislation_items,
        ce_legislations=[x for x in legislation_items if x.bucket == "ce"],
        non_ce_obligations=[x for x in legislation_items if x.bucket == "non_ce"],
        framework_regimes=[x for x in legislation_items if x.bucket == "framework"],
        future_regimes=[x for x in legislation_items if x.bucket == "future"],
        informational_items=[x for x in legislation_items if x.bucket == "informational"],
        standards=standard_items,
        review_items=review_items,
        missing_information=[item.message for item in missing_items],
        missing_information_items=missing_items,
        contradictions=traits_data.get("contradictions") or [],
        contradiction_severity=traits_data.get("contradiction_severity", "none"),
        diagnostics=diagnostics,
        stats=stats,
        knowledge_base_meta=KnowledgeBaseMeta(**load_meta()),
        analysis_audit={
            "allowed_directives": detected_directives,
            "matched_products": sorted(matched_products),
            "routing_matched_products": sorted(routing_matched_products),
            "preferred_standards": sorted(likely_standards),
            "product_genres": sorted(product_genres),
            "product_family": traits_data.get("product_family"),
            "product_subtype": traits_data.get("product_subtype"),
            "product_match_stage": traits_data.get("product_match_stage", "ambiguous"),
            "depth": depth,
        },
        standard_sections=standard_sections,
        legislation_sections=legislation_sections,
        hero_summary={
            "title": "RuleGrid Regulatory Scoping",
            "subtitle": "Describe the product clearly to generate the standards route and the applicable legislation path.",
            "primary_regimes": primary_regimes,
            "confidence": traits_data.get("product_match_confidence", "low"),
            "depth": depth,
        },
        confidence_panel={
            "confidence": traits_data.get("product_match_confidence", "low"),
            "matched_products": sorted(matched_products),
            "product_family": traits_data.get("product_family"),
            "product_genres": sorted(product_genres),
            "product_subtype": traits_data.get("product_subtype"),
            "product_match_stage": traits_data.get("product_match_stage", "ambiguous"),
        },
        input_gaps_panel={
            "items": [item.model_dump() for item in missing_items],
        },
        top_actions=[item.message for item in missing_items[:top_actions_limit]],
        current_path=[section["title"] for section in standard_sections],
        future_watchlist=[item.title for item in legislation_items if item.bucket == "future"],
        suggested_questions=[item.message for item in missing_items[:suggested_questions_limit]],
        suggested_quick_adds=_build_quick_adds(missing_items)[:quick_adds_limit],
        findings=findings,
    )


def analyze(
    description: str,
    category: str = "",
    directives: list[str] | None = None,
    depth: str = "standard",
) -> AnalysisResult:
    depth = _analysis_depth(depth)
    traits_data = extract_traits(description=description, category=category)
    diagnostics = list(traits_data.get("diagnostics") or [])
    matched_products = set(traits_data.get("matched_products") or [])
    routing_matched_products = set(traits_data.get("routing_matched_products") or [])
    product_genres = set(traits_data.get("product_genres") or [])
    product_type = traits_data.get("product_type")
    product_match_stage = str(traits_data.get("product_match_stage") or "ambiguous")
    routing_product_type = product_type if product_match_stage == "subtype" else None
    likely_standards: set[str] = set(traits_data.get("preferred_standard_codes") or [])
    for candidate in traits_data.get("product_candidates") or []:
        if candidate.get("id") in routing_matched_products:
            likely_standards.update(candidate.get("likely_standards") or [])

    base_trait_set = set(traits_data.get("all_traits") or [])
    trait_set = set(base_trait_set)
    confirmed_traits = set(traits_data.get("confirmed_traits") or [])
    functional_classes = set(traits_data.get("functional_classes") or [])
    trait_set, extra_diag = _derive_engine_traits(description, trait_set, routing_matched_products)
    diagnostics.extend(extra_diag)
    engine_added_traits = trait_set - base_trait_set

    raw_state_map = _normalize_trait_state_map(traits_data.get("trait_state_map"))
    for trait in sorted(engine_added_traits):
        raw_state_map["engine_derived"].setdefault(trait, []).append("engine:derived")

    context = _standard_context(trait_set, routing_matched_products, routing_product_type, confirmed_traits, description)
    legislation_items, legislation_sections, detected_directives = _build_legislation_sections(
        traits=trait_set,
        functional_classes=functional_classes,
        product_type=routing_product_type,
        matched_products=routing_matched_products,
        product_genres=product_genres,
        confirmed_traits=confirmed_traits,
        forced_directives=directives,
    )
    legislation_by_directive = _primary_legislation_by_directive(legislation_items)
    allowed_directives = set(detected_directives)

    items = find_applicable_items(
        traits=trait_set,
        directives=detected_directives,
        product_type=routing_product_type,
        matched_products=sorted(routing_matched_products),
        preferred_standard_codes=sorted(likely_standards),
        explicit_traits=set(traits_data.get("explicit_traits") or []),
        confirmed_traits=confirmed_traits,
        normalized_text=normalize(description),
        context_tags=context["context_tags"],
    )
    selected_rows = list(items["standards"]) + list(items["review_items"])
    selected_rows = _apply_post_selection_gates(
        selected_rows,
        trait_set,
        routing_matched_products,
        diagnostics,
        allowed_directives,
        product_type=routing_product_type,
        confirmed_traits=confirmed_traits,
        description=description,
    )

    dedup: dict[str, dict[str, Any]] = {}
    for row in selected_rows:
        key = str(row.get("code") or "")
        if key not in dedup or int(row.get("score", 0)) > int(dedup[key].get("score", 0)):
            dedup[key] = row

    standard_items: list[StandardItem] = []
    review_items: list[StandardItem] = []
    for row in dedup.values():
        item = _standard_item_from_row(row, legislation_by_directive, trait_set)
        if item.item_type == "review":
            review_items.append(item)
        else:
            standard_items.append(item)

    standard_items = _sort_standard_items(standard_items)
    review_items = _sort_standard_items(review_items)
    all_standard_items = _sort_standard_items(standard_items + review_items)
    current_review_items = [item for item in review_items if item.timing_status == "current"]
    missing_items = _missing_information(trait_set, routing_matched_products, description)
    standard_sections = _build_standard_sections(all_standard_items)
    primary_regimes = [section["key"] for section in standard_sections[:4]]

    current_risk = _current_risk(
        product_confidence=str(traits_data.get("product_match_confidence") or "low"),
        contradiction_severity=str(traits_data.get("contradiction_severity") or "none"),
        review_items=current_review_items,
        missing_items=missing_items,
    )
    future_risk = _future_risk(detected_directives, trait_set)
    overall_risk: RiskLevel = "LOW"
    if current_risk == "HIGH" or future_risk == "HIGH":
        overall_risk = "HIGH"
    elif current_risk == "MEDIUM" or future_risk == "MEDIUM":
        overall_risk = "MEDIUM"

    stats = AnalysisStats(
        legislation_count=len(legislation_items),
        current_legislation_count=len([x for x in legislation_items if x.timing_status == "current"]),
        future_legislation_count=len([x for x in legislation_items if x.timing_status == "future"]),
        standards_count=len(standard_items),
        review_items_count=len(review_items),
        current_review_items_count=len([x for x in review_items if x.timing_status == "current"]),
        future_review_items_count=len([x for x in review_items if x.timing_status == "future"]),
        harmonized_standards_count=len([x for x in standard_items if x.harmonization_status == "harmonized"]),
        state_of_the_art_standards_count=len([x for x in standard_items if x.harmonization_status == "state_of_the_art"]),
        product_gated_standards_count=len([x for x in standard_items if x.applies_if_products]),
        ambiguity_flag_count=1 if traits_data.get("contradictions") else 0,
        missing_information_count=len(missing_items),
    )

    summary = _build_summary(detected_directives, standard_items, review_items, trait_set)
    findings = _build_findings(
        depth=depth,
        legislation_items=legislation_items,
        standards=standard_items,
        review_items=review_items,
        missing_items=missing_items,
        contradictions=traits_data.get("contradictions") or [],
        contradiction_severity=traits_data.get("contradiction_severity", "none"),
    )
    top_actions_limit = {"quick": 2, "standard": 3, "deep": 5}[depth]
    suggested_questions_limit = {"quick": 2, "standard": 4, "deep": 6}[depth]
    quick_adds_limit = {"quick": 4, "standard": 8, "deep": 10}[depth]

    trait_evidence = _trait_evidence_from_state_map(raw_state_map, confirmed_traits)
    product_match_audit_raw = traits_data.get("product_match_audit")
    product_match_audit = (
        ProductMatchAudit.model_validate(product_match_audit_raw)
        if isinstance(product_match_audit_raw, dict)
        else None
    )
    rejected_audit_rows = list(items.get("audit", {}).get("rejected", []))
    rejected_audit_rows.extend(
        {
            "code": row.get("code"),
            "title": row.get("code"),
            "outcome": "rejected",
            "score": 0,
            "confidence": "low",
            "fact_basis": "inferred",
            "selection_group": None,
            "selection_priority": 0,
            "keyword_hits": [],
            "reason": row.get("reason"),
        }
        for row in items.get("rejections", [])
        if row.get("code") not in {item.code for item in standard_items + review_items}
    )
    standard_match_audit = _build_standard_match_audit(
        {
            "selected": [
                {
                    "code": item.code,
                    "title": item.title,
                    "outcome": "selected",
                    "score": item.score,
                    "confidence": item.confidence,
                    "fact_basis": item.fact_basis,
                    "selection_group": item.selection_group,
                    "selection_priority": item.selection_priority,
                    "keyword_hits": item.keywords,
                    "reason": item.reason,
                }
                for item in standard_items
            ],
            "review": [
                {
                    "code": item.code,
                    "title": item.title,
                    "outcome": "review",
                    "score": item.score,
                    "confidence": item.confidence,
                    "fact_basis": item.fact_basis,
                    "selection_group": item.selection_group,
                    "selection_priority": item.selection_priority,
                    "keyword_hits": item.keywords,
                    "reason": item.reason,
                }
                for item in review_items
            ],
            "rejected": rejected_audit_rows,
        },
        context["context_tags"],
    )

    result = AnalysisResult(
        product_summary=description.strip(),
        overall_risk=overall_risk,
        current_compliance_risk=current_risk,
        future_watchlist_risk=future_risk,
        summary=summary,
        product_type=traits_data.get("product_type"),
        product_family=traits_data.get("product_family"),
        product_family_confidence=traits_data.get("product_family_confidence", "low"),
        product_subtype=traits_data.get("product_subtype"),
        product_subtype_confidence=traits_data.get("product_subtype_confidence", "low"),
        product_match_stage=traits_data.get("product_match_stage", "ambiguous"),
        product_match_confidence=traits_data.get("product_match_confidence", "low"),
        product_candidates=traits_data.get("product_candidates") or [],
        functional_classes=traits_data.get("functional_classes") or [],
        confirmed_functional_classes=traits_data.get("confirmed_functional_classes") or [],
        explicit_traits=traits_data.get("explicit_traits") or [],
        confirmed_traits=sorted(confirmed_traits),
        inferred_traits=sorted(set(traits_data.get("inferred_traits") or []) | (trait_set - set(traits_data.get("explicit_traits") or []))),
        all_traits=sorted(trait_set),
        directives=detected_directives,
        forced_directives=[item for item in dict.fromkeys(directives or []) if item],
        legislations=legislation_items,
        ce_legislations=[x for x in legislation_items if x.bucket == "ce"],
        non_ce_obligations=[x for x in legislation_items if x.bucket == "non_ce"],
        framework_regimes=[x for x in legislation_items if x.bucket == "framework"],
        future_regimes=[x for x in legislation_items if x.bucket == "future"],
        informational_items=[x for x in legislation_items if x.bucket == "informational"],
        standards=standard_items,
        review_items=review_items,
        missing_information=[item.message for item in missing_items],
        missing_information_items=missing_items,
        contradictions=traits_data.get("contradictions") or [],
        contradiction_severity=traits_data.get("contradiction_severity", "none"),
        diagnostics=diagnostics,
        stats=stats,
        knowledge_base_meta=KnowledgeBaseMeta(**load_meta()),
        analysis_audit={
            "allowed_directives": detected_directives,
            "matched_products": sorted(matched_products),
            "routing_matched_products": sorted(routing_matched_products),
            "preferred_standards": sorted(likely_standards),
            "product_family": traits_data.get("product_family"),
            "product_subtype": traits_data.get("product_subtype"),
            "product_match_stage": traits_data.get("product_match_stage", "ambiguous"),
            "depth": depth,
            "engine_version": ENGINE_VERSION,
            "context_tags": sorted(context["context_tags"]),
        },
        engine_version=ENGINE_VERSION,
        trait_evidence=trait_evidence,
        product_match_audit=product_match_audit,
        standard_match_audit=standard_match_audit,
        standard_sections=standard_sections,
        legislation_sections=legislation_sections,
        hero_summary={
            "title": "RuleGrid Regulatory Scoping",
            "subtitle": "Describe the product clearly to generate the standards route and the applicable legislation path.",
            "primary_regimes": primary_regimes,
            "confidence": traits_data.get("product_match_confidence", "low"),
            "depth": depth,
        },
        confidence_panel={
            "confidence": traits_data.get("product_match_confidence", "low"),
            "matched_products": sorted(matched_products),
            "product_family": traits_data.get("product_family"),
            "product_subtype": traits_data.get("product_subtype"),
            "product_match_stage": traits_data.get("product_match_stage", "ambiguous"),
        },
        input_gaps_panel={
            "items": [item.model_dump() for item in missing_items],
        },
        top_actions=[item.message for item in missing_items[:top_actions_limit]],
        current_path=[section["title"] for section in standard_sections],
        future_watchlist=[item.title for item in legislation_items if item.bucket == "future"],
        suggested_questions=[item.message for item in missing_items[:suggested_questions_limit]],
        suggested_quick_adds=_build_quick_adds(missing_items)[:quick_adds_limit],
        findings=findings,
    )

    if ENABLE_ENGINE_V2_SHADOW:
        legacy = analyze_v1(description=description, category=category, directives=directives, depth=depth)
        result.analysis_audit["shadow_diff"] = _shadow_diff(legacy, result)

    return result
