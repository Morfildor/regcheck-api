from __future__ import annotations

import logging
import re
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date
from time import perf_counter
from typing import Any, Callable, Literal

from pydantic import ValidationError

from app.core.degradation import DegradationCollector, guarded_step
from app.core.runtime_state import API_VERSION
from app.core.settings import get_settings
from app.domain.models import (
    AnalysisAudit,
    AnalysisResult,
    AnalysisStats,
    ConfidenceLevel,
    ConfidencePanel,
    ContradictionSeverity,
    FactBasis,
    Finding,
    HeroSummary,
    InputGapsPanel,
    KnownFactItem,
    KnowledgeBaseMeta,
    LegislationItem,
    LegislationSection,
    MissingInformationItem,
    ProductMatchAudit,
    ProductMatchStage,
    QuickAddItem,
    RiskLevel,
    RiskBucketSummary,
    RiskReason,
    RiskSummary,
    RouteContext,
    ShadowDiffItem,
    StandardAuditItem,
    StandardMatchAudit,
    StandardSection,
    StandardSectionItem,
    StandardItem,
    TraitEvidenceItem,
    TraitEvidenceState,
)
from app.services.classifier import ENGINE_VERSION as CLASSIFIER_ENGINE_VERSION, extract_traits, extract_traits_v1, normalize
from app.services.knowledge_base import get_knowledge_base_snapshot, load_legislations, load_meta
from app.services.standards_engine import find_applicable_items, find_applicable_items_v1

AnalysisDepth = Literal["quick", "standard", "deep"]
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
    "ESPR": ("ESPR", "Ecodesign for Sustainable Products Regulation (EU) 2024/1781"),
    "CRA": ("CRA", "Cyber Resilience Act review"),
    "GDPR": ("GDPR", "GDPR review"),
    "AI_Act": ("AI Act", "Artificial Intelligence Act (EU) 2024/1689"),
    "FCM": ("FCM", "Framework Regulation on food contact materials (EC) No 1935/2004"),
    "FCM_PLASTIC": ("FCM Plastic", "Plastic food contact materials regulation (EU) No 10/2011"),
    "MD": ("MD", "Machinery Directive 2006/42/EC"),
    "MACH_REG": ("Machinery Reg.", "Machinery Regulation (EU) 2023/1230"),
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
    "ESPR",
    "CRA",
    "GDPR",
    "AI_Act",
    "FCM",
    "FCM_PLASTIC",
    "MD",
    "MACH_REG",
    "MDR",
    "OTHER",
]

ENGINE_VERSION = CLASSIFIER_ENGINE_VERSION
ENABLE_ENGINE_V2_SHADOW = get_settings().enable_engine_v2_shadow

logger = logging.getLogger(__name__)

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
    r"\bsmart watch\b",
    r"\bsmartwatch\b",
    r"\bfitness tracker\b",
    r"\bsmart band\b",
    r"\bactivity tracker\b",
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
    r"\bbody contact\b",
    r"\bchest strap\b",
    r"\bwrist worn\b",
    r"\bwristband\b",
    r"\bclip on\b",
]

HANDHELD_PATTERNS = [
    r"\bhandheld\b",
    r"\bhand held\b",
    r"\bportable\b",
    r"\bheld in hand\b",
    r"\bbarcode scanner\b",
    r"\bhandheld scanner\b",
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
    r"\bbody contact\b",
    r"\bskin contact\b",
    r"\bchest strap\b",
    r"\bwrist worn\b",
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

WIFI_5GHZ_EXPLICIT_PATTERNS = [
    r"\b5 ?ghz\b",
    r"\b5ghz\b",
    r"\b5 g hz\b",
    r"\bdual band\b",
    r"\bdual-band\b",
    r"\btri band\b",
    r"\btri-band\b",
    r"\b802\.11a\b",
    r"\b802 11a\b",
    r"\b802\.11ac\b",
    r"\b802 11ac\b",
    r"\b802\.11ax\b",
    r"\b802 11ax\b",
    r"\bwifi 5\b",
    r"\bwifi 6\b",
    r"\bwifi 6e\b",
    r"\bwifi 7\b",
]

WIFI_24_ONLY_PATTERNS = [
    r"\b2\.4 ?ghz only\b",
    r"\b2 4 ?ghz only\b",
    r"\b2\.4ghz only\b",
    r"\b2 4ghz only\b",
    r"\bonly 2\.4 ?ghz\b",
    r"\bonly 2 4 ?ghz\b",
    r"\bonly 2\.4ghz\b",
    r"\bonly 2 4ghz\b",
    r"\b2\.4 ?ghz wifi only\b",
    r"\b2 4 ?ghz wifi only\b",
    r"\bsingle band wifi\b",
    r"\bsingle-band wifi\b",
]

WIFI_5GHZ_DEFAULT_PRODUCT_HINTS = {
    "air_conditioner",
    "air_fryer",
    "air_purifier",
    "coffee_machine",
    "dishwasher",
    "home_projector",
    "projector",
    "refrigerator",
    "robot_lawn_mower",
    "robot_vacuum",
    "smart_display",
    "smart_plug",
    "smart_speaker",
    "smart_tv",
    "washing_machine",
}

WIRELESS_FACT_PATTERNS = [
    r"\bwi[ -]?fi\b",
    r"\bwlan\b",
    r"\bbluetooth\b",
    r"\bble\b",
    r"\bzigbee\b",
    r"\bthread\b",
    r"\bmatter\b",
    r"\bnfc\b",
    r"\brfid\b",
    r"\bcellular\b",
    r"\blte\b",
    r"\b4g\b",
    r"\b5g\b",
    r"\bgsm\b",
    r"\bdect\b",
    r"\buwb\b",
    r"\blora\b",
    r"\blorawan\b",
    r"\bsigfox\b",
    r"\bsatellite connectivity\b",
    r"\bradio\b",
    r"\brf\b",
    r"\bwireless\b",
]

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
    "smart_doorbell",
    "video_doorbell",
    "smart_security_camera",
    "ip_camera",
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
TEXT_EVIDENCE_STATES = ("text_explicit", "text_inferred")
RADIO_ROUTE_TRAITS = {
    "radio",
    "wifi",
    "wifi_5ghz",
    "wifi_6",
    "wifi_7",
    "bluetooth",
    "zigbee",
    "thread",
    "matter",
    "nfc",
    "cellular",
    "dect",
    "gsm",
    "uwb",
    "5g_nr",
    "lora",
    "lorawan",
    "sigfox",
    "lte_m",
    "satellite_connectivity",
}
CONNECTED_ROUTE_TRAITS = {
    "app_control",
    "cloud",
    "internet",
    "internet_connected",
    "ota",
    "account",
    "authentication",
    "monetary_transaction",
}
SENSITIVE_ROUTE_TRAITS = RADIO_ROUTE_TRAITS | CONNECTED_ROUTE_TRAITS
DEFAULT_CONNECTED_ROUTE_GENRES = {
    "smart_home_iot",
    "security_access_iot",
    "connected_toy_childcare",
    "pet_tech",
}
SMALL_SMART_62368_GENRES = {
    "smart_home_iot",
    "security_access_iot",
    "pet_tech",
}

ROUTE_FAMILY_SCOPE = {
    "household_appliance": "appliance",
    "av_ict": "av_ict",
    "av_ict_wearable": "av_ict",
    "lighting_device": "appliance",
    "building_hardware": "appliance",
    "hvac_control": "appliance",
    "life_safety_alarm": "appliance",
    "ev_charging": "appliance",
    "machinery_power_tool": "machinery",
    "toy": "toy",
}

ROUTE_FAMILY_PRIMARY_DIRECTIVE = {
    "machinery_power_tool": "MD",
    "toy": "TOY",
}

PRIMARY_DIRECTIVE_EXCLUSIONS = {
    "MD": {"LVD"},
    "TOY": {"LVD"},
}

OVERLAY_DIRECTIVE_KEYS = {
    "RED",
    "EMC",
    "BATTERY",
    "RED_CYBER",
    "GDPR",
    "ROHS",
    "REACH",
    "WEEE",
    "ECO",
    "ESPR",
    "CRA",
}


@dataclass(slots=True)
class PreparedAnalysis:
    depth: AnalysisDepth
    normalized_description: str
    traits_data: dict[str, Any]
    diagnostics: list[str]
    degraded_reasons: list[str]
    warnings: list[str]
    matched_products: set[str]
    routing_matched_products: set[str]
    product_genres: set[str]
    product_type: str | None
    product_match_stage: ProductMatchStage
    routing_product_type: str | None
    likely_standards: set[str]
    trait_set: set[str]
    route_traits: set[str]
    confirmed_traits: set[str]
    functional_classes: set[str]
    raw_state_map: dict[str, dict[str, list[str]]]
    route_plan: RoutePlan


@dataclass(slots=True)
class RoutePlan:
    primary_route_family: str | None = None
    primary_standard_code: str | None = None
    supporting_standard_codes: list[str] = field(default_factory=list)
    primary_directive: str | None = None
    reason: str = ""
    confidence: ConfidenceLevel = "low"
    scope_route: str = "generic"


@dataclass(slots=True)
class LegislationSelection:
    items: list[LegislationItem]
    sections: list[LegislationSection]
    detected_directives: list[str]
    forced_directives: list[str]
    allowed_directives: set[str]
    legislation_by_directive: dict[str, LegislationItem]


@dataclass(slots=True)
class StandardsSelection:
    context: dict[str, Any]
    standard_items: list[StandardItem]
    review_items: list[StandardItem]
    current_review_items: list[StandardItem]
    missing_items: list[MissingInformationItem]
    standard_sections: list[StandardSection]
    items_audit: dict[str, Any]
    rejections: list[dict[str, Any]]


@dataclass(slots=True)
class AnalysisTrace:
    request_id: str | None = None
    stage_timings_ms: dict[str, int] = field(default_factory=dict)

    def record_stage(self, stage: str, started_at: float) -> None:
        self.stage_timings_ms[stage] = int((perf_counter() - started_at) * 1000)


def _products_by_id() -> dict[str, dict[str, Any]]:
    return {
        str(row.get("id")): row
        for row in get_knowledge_base_snapshot().products
        if isinstance(row.get("id"), str)
    }


def _route_product_row(product_type: str | None, matched_products: set[str] | None = None) -> dict[str, Any] | None:
    products = _products_by_id()
    candidate_ids: list[str] = []
    if product_type:
        candidate_ids.append(product_type)
    for candidate_id in sorted(matched_products or set()):
        if candidate_id not in candidate_ids:
            candidate_ids.append(candidate_id)
    for candidate_id in candidate_ids:
        row = products.get(candidate_id)
        if row and (row.get("route_family") or row.get("primary_standard_code")):
            return row
    return None


def _route_scope_from_family(route_family: str | None) -> str | None:
    if not route_family:
        return None
    return ROUTE_FAMILY_SCOPE.get(route_family)


def _build_route_plan(
    traits_data: dict[str, Any],
    traits: set[str],
    matched_products: set[str],
    product_type: str | None,
) -> RoutePlan:
    product_match_confidence = _confidence_level(traits_data.get("product_match_confidence"), default="low")
    route_row = _route_product_row(product_type, matched_products)
    if route_row:
        route_family = str(route_row.get("route_family") or "") or None
        primary_standard_code = str(route_row.get("primary_standard_code") or "") or None
        supporting_standard_codes = _string_list(route_row.get("supporting_standard_codes"))
        scope_route = _route_scope_from_family(route_family) or "generic"
        label = str(route_row.get("label") or route_row.get("id") or product_type or "product")
        if primary_standard_code:
            reason = f"{label} maps to {primary_standard_code} as the primary product-safety route."
        elif route_family:
            reason = f"{label} maps to the {route_family.replace('_', ' ')} product-safety route."
        else:
            reason = f"{label} maps to a product-specific safety route."
        return RoutePlan(
            primary_route_family=route_family,
            primary_standard_code=primary_standard_code,
            supporting_standard_codes=supporting_standard_codes,
            primary_directive=ROUTE_FAMILY_PRIMARY_DIRECTIVE.get(route_family or ""),
            reason=reason,
            confidence=product_match_confidence,
            scope_route=scope_route,
        )

    if "toy" in traits:
        return RoutePlan(
            primary_route_family="toy",
            primary_directive="TOY",
            reason="Toy intent is explicit in the description.",
            confidence=product_match_confidence,
            scope_route="toy",
        )

    return RoutePlan(confidence=product_match_confidence)


def _scope_route(
    traits: set[str],
    matched_products: set[str],
    product_type: str | None,
    confirmed_traits: set[str] | None = None,
    route_family: str | None = None,
) -> tuple[str, list[str]]:
    confirmed_traits = confirmed_traits or set()
    reasons: list[str] = []

    scoped_family = route_family
    if not scoped_family:
        route_row = _route_product_row(product_type, matched_products)
        scoped_family = str(route_row.get("route_family") or "") or None if route_row else None
    family_scope = _route_scope_from_family(scoped_family)
    if family_scope:
        reasons.append(f"primary_route_family={scoped_family}")
        return family_scope, reasons

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


def _has_wireless_fact_signal(text: str) -> bool:
    return _has_any(text, WIRELESS_FACT_PATTERNS)


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


def _analysis_depth(depth: str) -> AnalysisDepth:
    if depth == "quick":
        return "quick"
    if depth == "deep":
        return "deep"
    return "standard"


def _confidence_level(value: Any, default: ConfidenceLevel = "medium") -> ConfidenceLevel:
    if value == "low":
        return "low"
    if value == "high":
        return "high"
    if value == "medium":
        return "medium"
    return default


def _contradiction_severity(value: Any) -> ContradictionSeverity:
    if value == "low":
        return "low"
    if value == "medium":
        return "medium"
    if value == "high":
        return "high"
    return "none"


def _product_match_stage(value: Any) -> ProductMatchStage:
    if value == "family":
        return "family"
    if value == "subtype":
        return "subtype"
    return "ambiguous"


def _current_date() -> date:
    return date.today()


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, str) and item]


def _keep_preferred_62368_review_in_appliance_scope(
    item: dict[str, Any],
    product_genres: set[str] | None,
    preferred_standard_codes: set[str] | None,
) -> bool:
    if str(item.get("code") or "") != "EN 62368-1":
        return False
    if str(item.get("item_type") or "standard") != "review":
        return False
    preferred_standard_codes = preferred_standard_codes or set()
    product_genres = product_genres or set()
    return "EN 62368-1" in preferred_standard_codes and bool(product_genres & SMALL_SMART_62368_GENRES)


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

    product_hit = bool(candidate_products & any_of_products)
    genre_hit = bool(product_genres & any_of_genres)

    if candidate_products & exclude_products:
        return False
    if product_genres & exclude_genres:
        return False
    if any_of_products and any_of_genres:
        if row.get("bucket") == "informational":
            if not (product_hit and genre_hit):
                return False
        elif not (product_hit or genre_hit):
            return False
    elif any_of_products and not product_hit:
        return False
    elif any_of_genres and not genre_hit:
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
    has_non_informational = {item.directive_key for item in items if item.bucket != "informational"}
    for item in items:
        if item.directive_key not in has_non_informational:
            continue
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


def _collect_preferred_standard_codes(traits_data: dict[str, Any]) -> set[str]:
    preferred: set[str] = set(traits_data.get("preferred_standard_codes") or [])
    product_match_stage = _product_match_stage(traits_data.get("product_match_stage"))
    routing_matched_products = set(traits_data.get("routing_matched_products") or [])

    if product_match_stage != "subtype":
        return preferred

    for candidate in traits_data.get("product_candidates") or []:
        if candidate.get("id") in routing_matched_products:
            preferred.update(candidate.get("likely_standards") or [])
    return preferred


def _has_small_avict_lvd_power_signal(traits: set[str], matched_products: set[str], product_type: str | None) -> bool:
    if "electrical" not in traits or "av_ict" not in traits:
        return False
    avict_product_hit = bool(matched_products & AV_ICT_PRODUCT_HINTS) or (product_type in AV_ICT_PRODUCT_HINTS if product_type else False)
    power_signal = bool({"usb_powered", "external_psu", "poe_powered", "mains_powered", "mains_power_likely"} & traits)
    compact_avict_signal = bool(
        {"wearable", "body_worn_or_applied", "camera", "display", "microphone", "data_storage", "fixed_installation"} & traits
    )
    return power_signal or avict_product_hit or compact_avict_signal


def _infer_forced_directives(
    traits: set[str],
    matched_products: set[str],
    product_type: str | None,
    confirmed_traits: set[str],
    preferred_standard_codes: set[str] | None = None,
) -> set[str]:
    preferred_standard_codes = preferred_standard_codes or set()
    normalized_codes = {
        str(code or "").upper().replace("IEC", "EN").replace("  ", " ").strip()
        for code in preferred_standard_codes
        if str(code or "").strip()
    }

    inferred: set[str] = set()
    scope_route, _ = _scope_route(traits, matched_products, product_type, confirmed_traits)
    has_household_safety_preference = any(code.startswith("EN 60335-") for code in normalized_codes)
    has_avict_safety_preference = any(code.startswith("EN 62368-1") for code in normalized_codes)
    has_lvd_voltage_signal = bool({"mains_powered", "mains_power_likely"} & traits)
    has_small_avict_lvd_signal = _has_small_avict_lvd_power_signal(traits, matched_products, product_type)

    if "electrical" in traits and (has_lvd_voltage_signal or has_small_avict_lvd_signal) and (
        has_household_safety_preference
        or has_avict_safety_preference
        or scope_route in {"appliance", "av_ict"}
        or bool(matched_products & (AV_ICT_PRODUCT_HINTS | PERSONAL_CARE_PRODUCT_HINTS | WIFI_5GHZ_DEFAULT_PRODUCT_HINTS))
    ):
        inferred.add("LVD")

    return inferred


def _derive_engine_traits(
    description: str,
    traits: set[str],
    matched_products: set[str],
) -> tuple[set[str], set[str], list[str]]:
    text = normalize(description)
    diagnostics: list[str] = []
    derived = set(traits)
    confirmed: set[str] = set()

    if _has_any(text, POWER_EXTERNAL_NEGATION_PATTERNS):
        derived.discard("external_psu")
        derived.add("internal_power_supply")
        confirmed.add("internal_power_supply")
        diagnostics.append("engine_trait=internal_power_supply")
    elif _has_any(text, POWER_EXTERNAL_PATTERNS):
        derived.add("external_psu")
        confirmed.add("external_psu")
        diagnostics.append("engine_trait=external_psu")
    elif _has_any(text, POWER_INTERNAL_PATTERNS):
        derived.add("internal_power_supply")
        confirmed.add("internal_power_supply")
        diagnostics.append("engine_trait=internal_power_supply")

    if _has_any(text, WEARABLE_PATTERNS):
        derived.add("wearable")
        derived.add("body_worn_or_applied")
        confirmed.update({"wearable", "body_worn_or_applied"})
        diagnostics.append("engine_trait=wearable/body_worn_or_applied")
    if _has_any(text, HANDHELD_PATTERNS):
        derived.add("handheld")
        confirmed.add("handheld")
        diagnostics.append("engine_trait=handheld")
    if _has_any(text, CLOSE_PROXIMITY_PATTERNS):
        derived.add("body_worn_or_applied")
        confirmed.add("body_worn_or_applied")
        diagnostics.append("engine_trait=close_proximity")

    if matched_products & PERSONAL_CARE_PRODUCT_HINTS:
        derived.add("handheld")
        diagnostics.append("engine_trait=handheld_from_product")

    if _has_any(text, WIFI_5GHZ_EXPLICIT_PATTERNS):
        derived.update({"wifi", "wifi_5ghz"})
        confirmed.add("wifi_5ghz")
        diagnostics.append("engine_trait=wifi_5ghz:explicit")
    elif "wifi" in derived and "wifi_5ghz" not in derived and not _has_any(text, WIFI_24_ONLY_PATTERNS):
        smart_wifi_default = bool(
            matched_products & (AV_ICT_PRODUCT_HINTS | WIFI_5GHZ_DEFAULT_PRODUCT_HINTS)
            or {"internet", "ota", "cloud", "app_control", "mains_powered", "mains_power_likely", "av_ict"} & derived
        )
        if smart_wifi_default:
            derived.add("wifi_5ghz")
            confirmed.add("wifi_5ghz")
            diagnostics.append("engine_trait=wifi_5ghz:smart_wifi_default")

    if "radio" in derived and ({"wearable", "handheld", "body_worn_or_applied"} & derived):
        derived.add("close_proximity_emf")
        diagnostics.append("engine_trait=close_proximity_emf")
    elif "radio" in derived and "clock" in matched_products:
        derived.add("low_power_radio")
        diagnostics.append("engine_trait=low_power_radio")

    return derived, confirmed & derived, diagnostics


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

    appliance_lvd_signal = bool(
        "electrical" in traits
        and "radio" not in traits
        and "consumer" in traits
        and "household" in traits
        and ({"heating", "motorized", "water_contact", "mains_powered", "mains_power_likely"} & traits)
    )

    if "electrical" in traits and ({"mains_powered", "mains_power_likely"} & traits):
        directives.append("LVD")
    elif _has_small_avict_lvd_power_signal(traits, set(), None):
        directives.append("LVD")
    elif appliance_lvd_signal:
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
    route_plan: RoutePlan | None = None,
) -> dict[str, Any]:
    route_plan = route_plan or RoutePlan()
    scope_route, scope_reasons = _scope_route(
        traits,
        matched_products,
        product_type,
        confirmed_traits,
        route_plan.primary_route_family,
    )
    if route_plan.reason:
        scope_reasons = [route_plan.reason, *scope_reasons]
    text = normalize(description)
    has_external_psu = "external_psu" in traits or bool(matched_products & {"battery_charger", "industrial_charger"})
    has_portable_battery = bool({"battery_powered", "backup_battery"} & traits)
    has_laser_source = "laser" in traits or _has_any(text, LASER_SOURCE_PATTERNS)
    has_photobiological_source = (
        has_laser_source
        or bool(matched_products & PHOTOBIO_PRODUCT_HINTS)
        or (product_type in PHOTOBIO_PRODUCT_HINTS if product_type else False)
        or _has_any(text, PHOTOBIOLOGICAL_SOURCE_PATTERNS)
    )
    has_body_contact = bool({"wearable", "body_worn_or_applied", "personal_care"} & traits) or bool(
        re.search(r"\b(?:body contact|skin contact|body worn|on body|on skin|chest strap|sensor patch|wearable patch|armband)\b", text)
    )
    has_skin_contact = bool(re.search(r"\b(?:skin contact|on skin|chest strap|sensor patch|wearable patch)\b", text))
    has_personal_or_health_data = bool(
        {"personal_data_likely", "health_related", "biometric", "account", "camera", "microphone", "location"} & traits
    )
    has_connected_radio = bool(
        "radio" in traits and ({"wifi", "bluetooth", "cellular", "app_control", "cloud", "ota", "internet", "account", "authentication"} & traits)
    )
    has_medical_boundary = bool({"possible_medical_boundary", "medical_context", "medical_claims"} & traits)
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
    if route_plan.primary_route_family:
        context_tags.add("primary:" + route_plan.primary_route_family)
    if route_plan.primary_standard_code:
        context_tags.add("primary_standard:" + route_plan.primary_standard_code)
    if has_external_psu:
        context_tags.add("power:external_psu")
    if has_portable_battery:
        context_tags.add("power:portable_battery")
    if has_laser_source:
        context_tags.add("optical:laser")
    if has_photobiological_source:
        context_tags.add("optical:photobio")
    if prefer_specific_red_emf:
        context_tags.add("exposure:close_proximity")
    if prefer_62233:
        context_tags.add("exposure:household_emf")
    if has_body_contact:
        context_tags.add("contact:body")
    if has_skin_contact or has_body_contact:
        context_tags.add("contact:skin")
    if has_personal_or_health_data:
        context_tags.add("data:personal_or_health")
    if {"health_related", "biometric"} & traits:
        context_tags.add("data:health")
    if has_connected_radio:
        context_tags.add("cyber:connected_radio")
    if has_medical_boundary:
        context_tags.add("boundary:medical_wellness")

    return {
        "scope_route": scope_route,
        "scope_reasons": scope_reasons,
        "text": text,
        "context_tags": context_tags,
        "primary_route_family": route_plan.primary_route_family,
        "primary_standard_code": route_plan.primary_standard_code,
        "primary_route_reason": route_plan.reason,
        "route_confidence": route_plan.confidence,
        "has_external_psu": has_external_psu,
        "has_portable_battery": has_portable_battery,
        "has_laser_source": has_laser_source,
        "has_photobiological_source": has_photobiological_source,
        "has_body_contact": has_body_contact,
        "has_personal_or_health_data": has_personal_or_health_data,
        "has_connected_radio": has_connected_radio,
        "has_medical_boundary": has_medical_boundary,
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
    product_genres: set[str] | None = None,
    preferred_standard_codes: set[str] | None = None,
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

        if code in {"EN 55032", "EN 55035"} and context["scope_route"] == "appliance":
            diagnostics.append(f"gate=drop_{code}:appliance_primary")
            continue

        if code == "EN 62368-1" and context["scope_route"] == "appliance":
            if _keep_preferred_62368_review_in_appliance_scope(item, product_genres, preferred_standard_codes):
                diagnostics.append("gate=keep_EN62368-1:preferred_small_smart_review")
            else:
                diagnostics.append("gate=drop_EN62368-1:appliance_primary")
                continue

        if code.startswith("EN 60335-") and context["scope_route"] == "av_ict":
            diagnostics.append(f"gate=drop_{code}:av_ict_primary")
            continue

        if code.startswith("EN 55014-") and context["scope_route"] == "av_ict":
            diagnostics.append(f"gate=drop_{code}:av_ict_primary")
            continue

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

        route = str(item.get("directive") or "OTHER")
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


def _route_condition_hint(row: dict[str, Any]) -> str | None:
    route_traits = set(_string_list(row.get("all_of_traits"))) | set(_string_list(row.get("any_of_traits")))
    if {"medical_claims", "medical_context", "possible_medical_boundary"} & route_traits:
        return "conditional on claim / medical-use context"
    if {"personal_data_likely", "health_related", "account", "authentication", "camera", "microphone", "location"} & route_traits:
        return "conditional on data handling"
    if route_traits:
        return "conditional on product function"
    return None


def _legislation_applicability_state(row: dict[str, Any]) -> str:
    if row.get("timing_status") == "future":
        return "upcoming"
    if row.get("applicability") == "conditional":
        return "conditional"
    return "current"


def _standard_applicability_state(row: dict[str, Any], timing_status: str) -> str:
    if timing_status == "future":
        return "upcoming"
    if row.get("item_type") == "review":
        return "review-dependent"
    return "current"


def _build_legislation_sections(
    traits: set[str],
    functional_classes: set[str],
    product_type: str | None,
    matched_products: set[str],
    product_genres: set[str],
    confirmed_traits: set[str],
    forced_directives: list[str] | None = None,
) -> tuple[list[LegislationItem], list[LegislationSection], list[str]]:
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
                jurisdiction="EU",
                applicability_state=_legislation_applicability_state(row),
                applicability_hint=_route_condition_hint(row),
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
        sections_dict[item.bucket]["items"].append(item)
    sections = [
        LegislationSection(
            key=value["key"],
            title=value["title"],
            count=len(value["items"]),
            items=value["items"],
        )
        for value in sections_dict.values()
        if value["items"]
    ]

    return items, sections, _directive_keys(items)


def _legislation_sections_from_items(items: list[LegislationItem]) -> list[LegislationSection]:
    sections_dict: dict[str, dict[str, Any]] = {
        "ce": {"key": "ce", "title": "CE routes", "items": []},
        "non_ce": {"key": "non_ce", "title": "Parallel obligations", "items": []},
        "framework": {"key": "framework", "title": "Additional framework checks", "items": []},
        "future": {"key": "future", "title": "Future / lifecycle watchlist", "items": []},
        "informational": {"key": "informational", "title": "Informational notices", "items": []},
    }
    for item in items:
        sections_dict[item.bucket]["items"].append(item)
    return [
        LegislationSection(
            key=value["key"],
            title=value["title"],
            count=len(value["items"]),
            items=value["items"],
        )
        for value in sections_dict.values()
        if value["items"]
    ]


def _filter_legislation_items_for_route_plan(items: list[LegislationItem], route_plan: RoutePlan) -> list[LegislationItem]:
    if not route_plan.primary_directive:
        return items
    excluded = PRIMARY_DIRECTIVE_EXCLUSIONS.get(route_plan.primary_directive, set())
    if not excluded:
        return items
    return [item for item in items if item.directive_key not in excluded]


def _build_known_facts(description: str) -> list[KnownFactItem]:
    text = normalize(description)
    facts: list[KnownFactItem] = []
    seen: set[str] = set()

    def add(key: str, label: str, value: str, related_traits: list[str]) -> None:
        if key in seen:
            return
        seen.add(key)
        facts.append(
            KnownFactItem(
                key=key,
                label=label,
                value=value,
                source="parsed",
                related_traits=related_traits,
            )
        )

    if re.search(r"\b(?:bluetooth|ble|bluetooth low energy)\b", text):
        add("connectivity.bluetooth", "Bluetooth", "Bluetooth is explicitly stated.", ["bluetooth", "radio"])
    if re.search(r"\b(?:wifi|wi fi|wlan|802 11)\b", text):
        add("connectivity.wifi", "Wi-Fi", "Wi-Fi is explicitly stated.", ["wifi", "radio"])
    if re.search(r"\bnfc\b", text):
        add("connectivity.nfc", "NFC", "NFC is explicitly stated.", ["nfc", "radio"])
    if re.search(
        r"\b(?:mobile app|smartphone app|companion app|app control|app controlled|app connected|app sync(?:ed)?|syncs? with (?:the )?(?:mobile )?app|via (?:the )?(?:mobile )?app|bluetooth app|wifi app)\b",
        text,
    ):
        add("service.app_control", "App control", "App control or app sync is explicitly stated.", ["app_control"])
    if re.search(r"\b(?:cloud account required|cloud account|account required|requires account|vendor account|cloud login)\b", text):
        add("service.cloud_account_required", "Cloud/account requirement", "A cloud or account requirement is explicitly stated.", ["cloud", "account"])
    elif re.search(r"\b(?:cloud|cloud service|cloud required|requires cloud|cloud dependency|cloud dependent)\b", text):
        add("service.cloud_dependency", "Cloud connectivity", "Cloud connectivity is explicitly stated.", ["cloud"])
    if re.search(r"\b(?:local only|offline only|no cloud|cloud free|lan only)\b", text):
        add("service.local_only", "Local-only operation", "Local-only or no-cloud operation is explicitly stated.", ["local_only"])
    if re.search(r"\b(?:ota|ota updates?|firmware updates?|firmware update|over the air|software updates?|wireless firmware update)\b", text):
        add("software.ota_updates", "OTA / firmware updates", "OTA or firmware updates are explicitly stated.", ["ota"])
    if re.search(r"\b(?:rechargeable battery|rechargeable|battery powered|battery operated|cordless|battery pack|battery cell)\b", text):
        add("power.rechargeable_battery", "Rechargeable / battery power", "Battery-powered or rechargeable operation is explicitly stated.", ["battery_powered"])
    if re.search(r"\b(?:li[ -]?ion|lithium ion|lithium battery|li ion)\b", text):
        add("power.lithium_ion", "Lithium-ion battery", "Lithium-ion battery chemistry is explicitly stated.", ["battery_powered"])
    if re.search(r"\b(?:consumer use|consumer|domestic|household|home use|personal use)\b", text):
        add("use.consumer", "Consumer use", "Consumer or household use is explicitly stated.", ["consumer", "household"])
    if re.search(r"\b(?:professional use|for professional use|professional|commercial use|commercial|industrial use|industrial|warehouse|enterprise)\b", text):
        add("use.professional", "Professional use", "Professional, commercial, or industrial use is explicitly stated.", ["professional"])
    if re.search(r"\b(?:indoor|indoor use|indoors)\b", text):
        add("environment.indoor", "Indoor use", "Indoor use is explicitly stated.", ["indoor_use"])
    if re.search(r"\b(?:outdoor|outdoor use|garden|lawn)\b", text):
        add("environment.outdoor", "Outdoor use", "Outdoor use is explicitly stated.", ["outdoor_use"])
    if re.search(r"\b(?:wearable|fitness tracker|smart band|smart watch|smartwatch|activity tracker|smart ring|wrist worn|wristband)\b", text):
        add("contact.wearable", "Wearable use", "Wearable or body-worn use is explicitly stated.", ["wearable", "body_worn_or_applied"])
    if re.search(r"\b(?:body contact|skin contact|body worn|on body|on skin|chest strap|sensor patch|wearable patch|armband)\b", text):
        add("contact.body_contact", "Body contact", "Body-contact or skin-contact use is explicitly stated.", ["body_worn_or_applied"])
    if re.search(r"\b(?:heart rate|pulse|spo2|blood oxygen|oxygen saturation|ecg|ekg|biometric|physiological)\b", text):
        add("data.health_related", "Health / biometric data", "Health, biometric, or physiological monitoring wording is explicitly stated.", ["health_related", "biometric"])
    if re.search(
        r"\b(?:diagnos(?:e|is|tic)|treat(?:ment|s|ing)?|therapy|therapeutic|disease monitoring|patient monitoring|clinical use|medical claims?|medical grade|wellness monitor|physiological monitoring|heart rate monitor|pulse oximeter|ecg monitor|ekg monitor)\b",
        text,
    ):
        add("boundary.possible_medical", "Possible medical boundary", "Medical, clinical, or physiological monitoring wording is explicitly stated.", ["possible_medical_boundary"])
    if not _has_wireless_fact_signal(text):
        add("connectivity.no_wifi", "No Wi-Fi stated", "No Wi-Fi is stated in the description.", [])
        add("connectivity.no_radio", "No radio stated", "No radio or wireless connectivity is stated in the description.", [])

    return facts


def _has_battery_chemistry_detail(text: str) -> bool:
    return bool(
        re.search(
            r"\b(?:li[ -]?ion|lithium(?:[ -](?:ion|iron phosphate))?|lifepo4|nimh|ni[ -]?mh|nicd|ni[ -]?cd|lead[ -]?acid|alkaline)\b",
            text,
        )
    )


def _has_battery_capacity_detail(text: str) -> bool:
    return bool(re.search(r"\b\d+(?:\.\d+)?\s*(?:mah|ah|wh|v)\b", text))


def _has_battery_pack_format_detail(text: str) -> bool:
    return bool(re.search(r"\b(?:integrated battery|built in battery|removable battery|replaceable battery|battery pack supplied)\b", text))


def _has_data_storage_detail(text: str) -> bool:
    return bool(
        re.search(
            r"\b(?:data storage|local storage|cloud storage|sd card|event history|recording|logs?|telemetry|retention|video storage)\b",
            text,
        )
    )


def _has_update_route_detail(text: str) -> bool:
    return bool(
        re.search(
            r"\b(?:ota|over the air|firmware update|software update|manual update|usb update|no updates?|security updates?)\b",
            text,
        )
    )


def _has_cloud_dependency_detail(text: str) -> bool:
    return bool(
        re.search(
            r"\b(?:cloud|cloud required|requires cloud|cloud dependency|cloud account|required account|account required|local only|offline only|cloud free|no cloud)\b",
            text,
        )
    )


def _has_access_model_detail(text: str) -> bool:
    return bool(
        re.search(
            r"\b(?:account|login|log in|sign in|pairing|pairing code|authentication|password|pin|guest mode|local only|cloud only|offline only)\b",
            text,
        )
    )


def _has_data_category_detail(text: str) -> bool:
    return bool(
        re.search(
            r"\b(?:personal data|health data|biometric|heart rate|pulse|spo2|blood oxygen|oxygen saturation|location data|video|audio|camera|microphone|voice|diagnostic data|telemetry|user profile)\b",
            text,
        )
    )


def _has_radio_band_detail(text: str) -> bool:
    return bool(
        re.search(
            r"\b(?:2\.4 ?ghz|5 ?ghz|6 ?ghz|868 ?mhz|915 ?mhz|433 ?mhz|13\.56 ?mhz|ble|bluetooth le|wifi 6|wifi 7|802\.11|802 11)\b",
            text,
        )
    )


def _has_radio_power_detail(text: str) -> bool:
    return bool(re.search(r"\b(?:eirp|dbm|mw|output power|transmit power|tx power)\b", text))


def _has_pressure_detail(text: str) -> bool:
    return bool(re.search(r"\b\d+(?:\.\d+)?\s*(?:bar|psi|mpa|kpa|l|litre|liter|gallon)\b", text))


def _has_installation_detail(text: str) -> bool:
    return bool(re.search(r"\b(?:portable|handheld|bench(?:top)?|stationary|fixed(?:[ -]?installation)?|floor[ -]?standing)\b", text))


def _has_body_contact_material_detail(text: str) -> bool:
    return bool(
        re.search(
            r"\b(?:silicone|tpu|stainless steel|polycarbonate|skin contact material|biocompatib|irritation|sensitization|contact duration)\b",
            text,
        )
    )


def _has_medical_boundary_resolution(text: str) -> bool:
    return bool(
        re.search(
            r"\b(?:not a medical device|wellness only|fitness only|clinical use|patient use|diagnosis|treatment|therapeutic|medical grade)\b",
            text,
        )
    )


def _missing_information(
    traits: set[str],
    matched_products: set[str],
    description: str,
    product_type: str | None = None,
    product_match_stage: ProductMatchStage = "ambiguous",
    route_plan: RoutePlan | None = None,
) -> list[MissingInformationItem]:
    text = normalize(description)
    items: list[MissingInformationItem] = []
    seen_keys: set[str] = set()
    route_plan = route_plan or RoutePlan()

    def add(
        key: str,
        message: str,
        importance: MissingImportance = "medium",
        examples: list[str] | None = None,
        related: list[str] | None = None,
        route_impact: list[str] | None = None,
        next_actions: list[str] | None = None,
    ) -> None:
        if key in seen_keys:
            return
        seen_keys.add(key)
        items.append(
            MissingInformationItem(
                key=key,
                message=message,
                importance=importance,
                examples=examples or [],
                related_traits=related or [],
                route_impact=route_impact or [],
                next_actions=next_actions or [],
            )
        )

    known_fact_keys = {item.key for item in _build_known_facts(description)}
    route_family = route_plan.primary_route_family

    def stated(pattern: str) -> bool:
        return bool(re.search(pattern, text))

    def stated_any(patterns: list[str]) -> bool:
        return any(stated(pattern) for pattern in patterns)

    tool_signal = bool(
        matched_products
        & {"industrial_power_tool", "corded_power_drill", "cordless_power_drill", "portable_power_saw", "industrial_air_compressor"}
    ) or bool(re.search(r"\b(?:power tool|drill|saw|compressor)\b", text))
    smart_signal = bool({"cloud", "app_control", "ota", "wifi", "bluetooth", "radio", "internet"} & traits) or bool(
        re.search(r"\b(?:smart|connected|app|wireless|ota)\b", text)
    )
    battery_signal = bool({"battery_powered", "backup_battery"} & traits) or bool(
        re.search(r"\b(?:battery|rechargeable|cordless|cell pack|battery pack)\b", text)
    )
    compressor_signal = bool(matched_products & {"industrial_air_compressor"}) or bool(
        re.search(r"\b(?:air compressor|compressed air|pneumatic compressor|workshop compressor)\b", text)
    )
    body_contact_signal = bool({"wearable", "body_worn_or_applied", "personal_care"} & traits) or bool(
        {"contact.wearable", "contact.body_contact"} & known_fact_keys
    )
    health_data_signal = bool({"health_related", "biometric", "personal_data_likely"} & traits) or "data.health_related" in known_fact_keys
    medical_boundary_signal = bool({"possible_medical_boundary", "medical_context", "medical_claims"} & traits) or (
        "boundary.possible_medical" in known_fact_keys
    )
    cloud_detail_known = _has_cloud_dependency_detail(text) or bool(
        {"service.cloud_dependency", "service.cloud_account_required", "service.local_only"} & known_fact_keys
    )
    access_detail_known = _has_access_model_detail(text) or "service.cloud_account_required" in known_fact_keys
    update_detail_known = _has_update_route_detail(text) or "software.ota_updates" in known_fact_keys
    battery_pack_detail_known = _has_battery_pack_format_detail(text)
    radio_band_known = _has_radio_band_detail(text)
    radio_power_known = _has_radio_power_detail(text)
    data_category_known = _has_data_category_detail(text) or "data.health_related" in known_fact_keys

    if product_type == "smart_lock":
        if not stated_any([r"\bindoor\b", r"\boutdoor\b", r"\bweather(?:proof|resistant)\b", r"\bexternal door\b"]):
            add(
                "smart_lock_installation",
                "Confirm whether the lock is indoor-only or intended for exposed outdoor use.",
                "medium",
                ["indoor apartment door", "outdoor gate or exterior door"],
                ["fixed_installation"],
                ["LVD", "GPSR"],
            )
        if "biometric" in traits and not stated_any([r"\blocal only\b", r"\bon device\b", r"\bcloud\b", r"\bremote unlock history\b"]):
            add(
                "smart_lock_biometric_storage",
                "Confirm whether biometric data is processed locally only or backed up to the cloud.",
                "high",
                ["fingerprint templates stored locally only", "biometric data synced to cloud account"],
                ["biometric", "cloud", "personal_data_likely"],
                ["GDPR", "RED_CYBER"],
            )
        if not stated_any([r"\bpanic\b", r"\bemergency exit\b", r"\bescape route\b", r"\bfire exit\b"]):
            add(
                "smart_lock_escape_route",
                "Confirm whether the lock is used on an emergency-exit, panic, or escape-route door.",
                "medium",
                ["standard residential entry door", "panic-exit application"],
                ["safety_function"],
                ["GPSR"],
            )
        if ("app_control" in traits or "voice_assistant" in traits) and "radio" not in traits:
            add(
                "smart_lock_actual_radio",
                "Confirm the actual radio modules present, if any.",
                "high",
                ["Wi-Fi", "Bluetooth", "Zigbee", "Z-Wave", "NFC", "no wireless communication"],
                ["radio", "wifi", "bluetooth", "zigbee", "nfc"],
                ["RED", "RED_CYBER"],
            )

    if route_family == "ev_charging" or product_type in {"ev_charger_home", "portable_ev_charger"}:
        if not stated_any([r"\bmode ?2\b", r"\bmode ?3\b", r"\bmode ?4\b"]):
            add(
                "ev_mode",
                "Confirm whether the product is mode 2, mode 3, or mode 4 charging equipment.",
                "high",
                ["mode 2 portable EVSE", "mode 3 wallbox", "mode 4 DC charger"],
                ["ev_charging"],
                ["LVD", "EMC"],
            )
        if not stated_any([r"\bac charging\b", r"\bdc charging\b", r"\bac\b", r"\bdc\b"]):
            add(
                "ev_ac_dc",
                "Confirm whether the charging equipment is AC or DC.",
                "high",
                ["single-phase AC", "three-phase AC", "DC fast charging"],
                ["ev_charging"],
                ["LVD", "EMC"],
            )
        if not stated_any([r"\bportable\b", r"\bfixed\b", r"\bwallbox\b", r"\bcharging station\b", r"\bwall mount\b"]):
            add(
                "ev_installation_type",
                "Confirm whether it is a portable EVSE or a fixed charging station.",
                "high",
                ["portable mode 2 EVSE", "fixed wallbox charging station"],
                ["portable", "fixed_installation"],
                ["LVD", "EMC"],
            )
        if not stated_any([r"\btype ?1\b", r"\btype ?2\b", r"\bccs\b", r"\bconnector\b", r"\binlet\b", r"\bcoupler\b", r"\bsocket\b"]):
            add(
                "ev_connector_type",
                "Confirm whether the connector, coupler, or inlet type is relevant.",
                "medium",
                ["Type 2 vehicle connector", "CCS interface", "socket-outlet only"],
                ["vehicle_supply"],
                ["LVD"],
            )
        if not stated_any([r"\baccessory\b", r"\bconnector only\b", r"\bcoupler only\b", r"\binlet only\b", r"\boff board\b", r"\boff-board\b"]):
            add(
                "ev_equipment_boundary",
                "Confirm whether the product is off-board charging equipment or only a connector/accessory.",
                "high",
                ["off-board EV charging equipment", "connector-only accessory"],
                ["ev_charging", "vehicle_supply"],
                ["LVD", "EMC"],
            )
        if ("app_control" in traits or "ota" in traits or "cloud" in traits) and "radio" not in traits:
            add(
                "ev_actual_radio",
                "Confirm whether any actual radio modules are present.",
                "medium",
                ["Wi-Fi present", "Bluetooth present", "wired control only"],
                ["radio"],
                ["RED", "RED_CYBER"],
            )

    if product_type == "air_purifier":
        if not stated_any([r"\buv ?c\b", r"\bultraviolet\b", r"\bgermicidal\b", r"\bno uv\b"]):
            add(
                "air_purifier_uvc",
                "Confirm whether the air purifier intentionally emits UV-C or other germicidal radiation.",
                "high",
                ["HEPA filter only", "UV-C disinfection lamp included"],
                ["air_treatment"],
                ["LVD", "GPSR"],
            )
        if not stated_any([r"\bportable\b", r"\btabletop\b", r"\broom\b", r"\bhvac\b", r"\bintegrated\b", r"\bduct\b"]):
            add(
                "air_purifier_installation",
                "Confirm whether it is a portable appliance or an integrated HVAC component.",
                "medium",
                ["portable room appliance", "ducted HVAC module"],
                ["air_treatment"],
                ["LVD", "GPSR"],
            )

    if route_family == "lighting_device" or product_type in {"smart_led_bulb", "smart_desk_lamp"}:
        if not stated_any([r"\bbulb\b", r"\blamp\b", r"\blight source\b", r"\bluminaire\b", r"\bfixture\b", r"\bdesk lamp\b"]):
            add(
                "lighting_form_factor",
                "Confirm whether the product is a lamp only or a luminaire / fixture.",
                "medium",
                ["E27 LED lamp only", "integrated desk-lamp luminaire"],
                ["lighting"],
                ["LVD", "ECO"],
            )
        if not stated_any([r"\bmains\b", r"\bdriver\b", r"\bcontrol gear\b", r"\btransformer\b", r"\busb powered\b"]):
            add(
                "lighting_power_architecture",
                "Confirm whether the light source is mains-direct or relies on external / integrated control gear.",
                "medium",
                ["mains-direct E27 lamp", "external driver or control gear"],
                ["mains_powered", "electrical"],
                ["LVD", "ECO"],
            )
        if not stated_any([r"\bdimmable\b", r"\bnon dimmable\b"]):
            add(
                "lighting_dimming",
                "Confirm whether the lamp is dimmable.",
                "low",
                ["phase-cut dimmable", "non-dimmable"],
                ["lighting"],
                ["ECO"],
            )

    if product_type == "refrigerator_freezer":
        if not stated_any([r"\bhousehold\b", r"\bdomestic\b", r"\bcommercial\b", r"\bprofessional\b"]):
            add(
                "refrigerator_use_class",
                "Confirm whether the refrigerator is for household/domestic use or commercial use.",
                "high",
                ["household fridge-freezer", "commercial upright refrigerator"],
                ["household", "professional"],
                ["LVD", "GPSR"],
            )
        if not stated_any([r"\brefrigerant\b", r"\bsealed system\b", r"\br600a\b", r"\br290\b", r"\bcompressor\b"]):
            add(
                "refrigerator_cooling_system",
                "Confirm whether the sealed cooling system and refrigerant details are relevant.",
                "medium",
                ["sealed system with R600a", "thermoelectric cooler"],
                ["motorized"],
                ["LVD", "GPSR"],
            )

    if product_type == "robot_vacuum":
        if not stated_any([r"\bmop\b", r"\bvacuum only\b", r"\bsweep\b"]):
            add(
                "robot_vacuum_function",
                "Confirm whether the robot performs vacuum-only cleaning or vacuum plus mopping.",
                "medium",
                ["vacuum only", "vacuum and mop"],
                ["cleaning"],
                ["LVD", "GPSR"],
            )
        if not stated_any([r"\bdocking station\b", r"\bcharging dock\b", r"\bself empty\b", r"\bbase station\b"]):
            add(
                "robot_vacuum_dock",
                "Confirm whether a docking station or charger is included.",
                "low",
                ["charging dock included", "robot only without dock"],
                ["battery_powered"],
                ["BATTERY", "ECO"],
            )

    if route_family == "life_safety_alarm" or product_type == "smart_smoke_co_alarm":
        if not stated_any([r"\bsmoke\b", r"\bco\b", r"\bcarbon monoxide\b", r"\bcombined\b"]):
            add(
                "alarm_detection_type",
                "Confirm whether the alarm is for smoke, carbon monoxide, or both.",
                "high",
                ["smoke alarm only", "CO alarm only", "combined smoke and CO alarm"],
                ["smoke_detection", "co_detection"],
                ["LVD", "GPSR"],
            )
        if not stated_any([r"\bstandalone\b", r"\bdomestic\b", r"\bhousehold\b", r"\bsystem component\b", r"\bpanel\b"]):
            add(
                "alarm_system_boundary",
                "Confirm whether it is a domestic standalone alarm or a system component.",
                "high",
                ["standalone residential alarm", "alarm-system component"],
                ["safety_function"],
                ["LVD", "GPSR"],
            )

    if route_family == "machinery_power_tool" or product_type in {"corded_power_drill", "cordless_power_drill", "industrial_power_tool"}:
        if ("app_control" in traits or "ota" in traits) and "radio" not in traits:
            add(
                "tool_actual_radio",
                "Confirm whether the tool has any actual radio functionality.",
                "high",
                ["Bluetooth module present", "no wireless communication"],
                ["radio"],
                ["RED", "RED_CYBER"],
            )
        if not stated_any([r"\bhandheld\b", r"\bhand held\b", r"\btransportable\b", r"\bbench\b", r"\bstationary\b"]):
            add(
                "tool_form_factor",
                "Confirm whether the tool is handheld or transportable/stationary.",
                "medium",
                ["handheld drill", "transportable bench tool"],
                ["handheld", "portable"],
                ["MD"],
            )
        if not stated_any([r"\bconsumer\b", r"\bdomestic\b", r"\bprofessional\b", r"\bindustrial\b"]):
            add(
                "tool_use_class",
                "Confirm whether the tool is a consumer tool or industrial/professional machinery.",
                "medium",
                ["consumer cordless drill", "industrial/professional power tool"],
                ["consumer", "professional", "industrial"],
                ["MD", "GPSR"],
            )

    if "child_targeted" in traits and "toy" not in traits:
        if not stated_any([r"\bnot intended for play\b", r"\bdesigned for play\b", r"\btoy\b", r"\bplay\b"]):
            add(
                "toy_play_intent",
                "Confirm whether the product is designed or intended for play by children under 14.",
                "high",
                ["not intended for play", "marketed as a toy for children under 14"],
                ["toy", "child_targeted"],
                ["TOY", "GPSR"],
            )
        if not stated_any([r"\bmain(?:ly)? for play\b", r"\bplay(?:ful)? function\b", r"\beducational aid\b", r"\bsafety product\b"]):
            add(
                "toy_primary_function",
                "Confirm whether play is the main intended function.",
                "high",
                ["primary function is play", "primary function is monitoring or safety"],
                ["toy"],
                ["TOY", "GPSR"],
            )

    if product_match_stage != "subtype" and tool_signal:
        add(
            "tool_type",
            "Specify the exact equipment type, such as drill, saw, grinder, sander, or compressor.",
            "high",
            ["corded drill", "circular saw", "portable air compressor"],
            ["motorized"],
            ["MD", "MACH_REG", "LVD", "BATTERY"],
            ["Confirm the exact equipment family before relying on machinery or tool routes."],
        )

    if "mains_powered" not in traits and "mains_power_likely" not in traits and "battery_powered" not in traits:
        add(
            "power_source",
            "Confirm whether the product is mains-powered, battery-powered, or both.",
            "high",
            ["230 V mains powered", "rechargeable lithium battery", "mains plus battery backup"],
            ["mains_powered", "battery_powered"],
            ["LVD", "BATTERY", "ECO"],
            ["Confirm the power architecture and whether the product is mains-powered, battery-powered, or both."],
        )
    if "radio" in traits and not any(t in traits for t in ["wifi", "bluetooth", "cellular", "zigbee", "thread", "nfc"]):
        add(
            "radio_technology",
            "Confirm the actual radio technology.",
            "high",
            ["Wi-Fi radio", "Bluetooth LE radio", "NFC radio"],
            ["radio"],
            ["RED", "RED_CYBER"],
            ["Confirm the actual radio technology used by the product."],
        )
    if "radio" in traits and (not radio_band_known or not radio_power_known):
        add(
            "radio_rf_detail",
            "Confirm the radio bands and declared output power.",
            "medium",
            ["Bluetooth LE 2.4 GHz", "Wi-Fi 2.4/5 GHz", "maximum output power 10 dBm"],
            ["radio", "wifi", "bluetooth", "cellular", "nfc"],
            ["RED", "RED_CYBER"],
            ["Confirm radio bands, channel families, and declared output power / EIRP."],
        )
    if "wifi" in traits and "wifi_5ghz" not in traits:
        add(
            "wifi_band",
            "Confirm whether Wi-Fi is 2.4 GHz only or also 5 GHz.",
            "medium",
            ["2.4 GHz only", "dual-band 2.4/5 GHz"],
            ["wifi", "wifi_5ghz"],
            ["RED"],
            ["Confirm whether Wi-Fi is limited to 2.4 GHz or also uses 5 GHz / 6 GHz bands."],
        )
    if ({"usb_powered", "external_psu"} & traits or "adapter" in text) and "external_psu" not in traits and not _has_any(text, POWER_EXTERNAL_NEGATION_PATTERNS):
        add(
            "external_psu",
            "Confirm whether an external adapter or charger is supplied with the product.",
            "high",
            ["external AC/DC adapter included", "USB-C PD power adapter included", "internal PSU only"],
            ["external_psu"],
            ["LVD", "ECO"],
            ["Confirm whether the shipped product includes an external PSU, adapter, dock, or charger."],
        )
    if "radio" in traits and not ({"wearable", "handheld", "body_worn_or_applied"} & traits) and bool(matched_products & PERSONAL_CARE_PRODUCT_HINTS):
        add(
            "emf_use_position",
            "Confirm whether the radio function is used close to the body or only at separation distance.",
            "medium",
            ["body-worn use", "handheld close to face", "countertop use only"],
            ["wearable", "handheld", "body_worn_or_applied"],
            ["RED"],
            ["Confirm whether the radio is used on-body, handheld near the face, or only at separation distance."],
        )
    if "radio" in traits and ({"portable", "battery_powered", "cellular"} & traits or bool(matched_products & PERSONAL_CARE_PRODUCT_HINTS)) and not ({"handheld", "wearable", "body_worn_or_applied"} & traits):
        add(
            "rf_exposure_form_factor",
            "Confirm whether the radio product is handheld, body-worn, wearable, or used only with separation distance.",
            "medium",
            ["handheld use", "body-worn wearable use", "desktop use with separation distance"],
            ["handheld", "wearable", "body_worn_or_applied"],
            ["RED"],
            ["Confirm the RF exposure form factor used in normal operation."],
        )
    if smart_signal and not cloud_detail_known:
        add(
            "cloud_dependency",
            "Confirm whether the smart features require cloud dependency or can operate locally.",
            "high",
            ["cloud account required", "local LAN control without cloud dependency", "OTA firmware updates"],
            ["cloud", "app_control", "ota"],
            ["RED_CYBER", "CRA", "GDPR"],
            ["Confirm cloud dependency, account requirement, and whether core functions still work without cloud access."],
        )
    if medical_boundary_signal and not _has_medical_boundary_resolution(text):
        add(
            "medical_wellness_boundary",
            "Confirm whether the intended purpose stays in wellness scope or crosses into medical diagnosis, treatment, disease monitoring, or patient use.",
            "high",
            ["wellness-only activity tracking", "patient monitoring / clinical use", "diagnosis or treatment claim"],
            ["possible_medical_boundary", "medical_claims", "medical_context"],
            ["MDR", "GDPR", "GPSR"],
            ["Confirm the medical / wellness claim boundary and intended-use statement."],
        )
    if battery_signal and not _has_battery_chemistry_detail(text):
        add(
            "battery_chemistry",
            "Confirm the battery chemistry or cell type.",
            "high",
            ["lithium-ion pack", "LiFePO4 pack", "NiMH cells", "sealed lead-acid battery"],
            ["battery_powered"],
            ["BATTERY", "WEEE", "GPSR"],
            ["Confirm the battery chemistry or cell type used in the product."],
        )
    if battery_signal and not _has_battery_capacity_detail(text):
        add(
            "battery_capacity",
            "Confirm battery voltage and capacity or energy rating.",
            "medium",
            ["18 V 5 Ah pack", "36 V 4 Ah battery", "54 Wh integrated battery"],
            ["battery_powered"],
            ["BATTERY", "RED"],
            ["Confirm nominal voltage and capacity / energy rating for the battery pack."],
        )
    if battery_signal and not battery_pack_detail_known:
        add(
            "battery_pack_format",
            "Confirm whether the battery is integrated, removable, or supplied as a separate pack.",
            "medium",
            ["integrated battery", "removable battery pack", "tool sold without battery pack"],
            ["battery_powered"],
            ["BATTERY", "WEEE"],
            ["Confirm battery chemistry and removability, including whether the pack is integrated or user-removable."],
        )
    if smart_signal and not _has_data_storage_detail(text):
        add(
            "data_storage_scope",
            (
                "Confirm where the stated personal or health-related data are stored, retained, and sent, including any cloud or app transfer."
                if health_data_signal and data_category_known
                else "Confirm which personal or health-related data categories are processed and whether they are stored locally, in the app, in the cloud, or not retained."
                if health_data_signal
                else "Confirm whether the product stores user, event, diagnostic, or media data locally, in the cloud, or not at all."
            ),
            "high",
            (
                ["heart rate data stored only in mobile app", "cloud account retains activity history", "no personal or health data retained"]
                if health_data_signal and data_category_known
                else ["heart rate and activity data in app account", "cloud video history", "no personal or health data retained"]
                if health_data_signal
                else ["local event log only", "cloud video history", "no user or event data retained"]
            ),
            ["data_storage", "personal_data_likely", "health_related"],
            ["GDPR", "CRA", "RED_CYBER"],
            ["Confirm personal / health data categories, storage locations, retention, and cloud transfer scope."],
        )
    if smart_signal and not update_detail_known:
        add(
            "software_update_route",
            "Confirm whether firmware or software updates are supported, and whether they are OTA, app-driven, local-only, or unavailable.",
            "high",
            ["OTA firmware updates", "USB-only local update", "no field updates supported"],
            ["ota"],
            ["CRA", "RED_CYBER"],
            ["Confirm whether updates are OTA, app-driven, local-only, or unavailable in the field."],
        )
    if smart_signal and not access_detail_known:
        add(
            "smart_access_model",
            "Confirm whether the smart features require an account, pairing flow, local-only control, or permanent cloud access.",
            "medium",
            ["local pairing without account", "vendor account required", "LAN-only operation"],
            ["account", "authentication", "local_only", "cloud"],
            ["GDPR", "CRA", "RED_CYBER"],
            ["Confirm whether an account, login, pairing flow, or permanent cloud access is required."],
        )
    if body_contact_signal and not _has_body_contact_material_detail(text):
        add(
            "body_contact_materials",
            "Confirm the skin-contact surfaces, contact duration, and main body-contact materials.",
            "medium",
            ["silicone wrist strap with daily skin contact", "stainless-steel sensor surface", "brief grooming contact only"],
            ["wearable", "body_worn_or_applied", "personal_care"],
            ["GPSR", "MDR"],
            ["Confirm skin-contact materials, contact duration, and whether a biocompatibility review is needed."],
        )
    if tool_signal and not _has_installation_detail(text):
        add(
            "tool_form_factor",
            "Confirm whether the equipment is handheld / portable or stationary / fixed-installation.",
            "medium",
            ["handheld power tool", "portable workshop unit", "stationary bench machine"],
            ["handheld", "portable", "fixed_installation"],
            ["MD", "MACH_REG", "LVD"],
            ["Confirm whether the equipment is handheld, portable, bench-top, or fixed-installation."],
        )
    if compressor_signal and not _has_pressure_detail(text):
        add(
            "pressure_rating",
            "Confirm the compressor maximum working pressure and receiver volume.",
            "high",
            ["8 bar with 24 L receiver", "10 bar oil-free compressor", "16 bar line pressure"],
            ["pressure"],
            ["MD", "MACH_REG"],
            ["Confirm the maximum working pressure and receiver volume."],
        )
    if compressor_signal and not re.search(r"\b(?:oil free|lubricated|duty cycle|continuous duty|intermittent duty)\b", text):
        add(
            "compressor_duty",
            "Confirm whether the compressor is oil-free or lubricated, and whether it is continuous-duty or intermittent-duty.",
            "medium",
            ["oil-free portable compressor", "lubricated workshop compressor", "continuous-duty installation"],
            ["pressure", "motorized"],
            ["MD", "MACH_REG"],
            ["Confirm lubrication type and duty-cycle classification."],
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
            ["Confirm the primary function so the correct appliance or AV/ICT route is retained."],
        )
    return items[:8]


def _build_quick_adds(missing: list[MissingInformationItem]) -> list[QuickAddItem]:
    out: list[QuickAddItem] = []
    seen: set[str] = set()
    for item in missing:
        for example in item.examples[:2]:
            if example in seen:
                continue
            seen.add(example)
            out.append(QuickAddItem(label=item.key.replace("_", " "), text=example))
    return out[:10]


def _top_actions_from_missing(missing: list[MissingInformationItem], limit: int) -> list[str]:
    actions: list[str] = []
    seen: set[str] = set()
    for item in missing:
        for action in item.next_actions or [item.message]:
            if action in seen:
                continue
            seen.add(action)
            actions.append(action)
            if len(actions) >= limit:
                return actions
    return actions[:limit]


def _route_context_summary(
    context: dict[str, Any],
    known_facts: list[KnownFactItem],
    overlay_routes: list[str] | None = None,
) -> RouteContext:
    scope_reasons = [reason for reason in context.get("scope_reasons", []) if isinstance(reason, str)]
    return RouteContext(
        scope_route=str(context.get("scope_route") or "generic"),
        scope_reasons=scope_reasons,
        context_tags=sorted(context.get("context_tags", [])),
        known_fact_keys=[item.key for item in known_facts],
        jurisdiction="EU",
        route_trigger_reasons=scope_reasons,
        primary_route_family=str(context.get("primary_route_family") or "") or None,
        primary_route_standard_code=str(context.get("primary_standard_code") or "") or None,
        primary_route_reason=str(context.get("primary_route_reason") or ""),
        overlay_routes=list(overlay_routes or []),
        route_confidence=_confidence_level(context.get("route_confidence"), default="low"),
    )


def _build_standard_sections(items: list[StandardItem]) -> list[StandardSection]:
    grouped: dict[str, list[StandardItem]] = defaultdict(list)
    for item in items:
        route_keys = [item.directive] if item.category in {"safety", "radio_emc"} else ([key for key in item.directives if key] or [item.directive])
        for key in route_keys:
            grouped[key].append(item)
    sections: list[StandardSection] = []
    for key in sorted(grouped.keys(), key=_directive_rank):
        route_items = _sort_standard_items(grouped[key])
        directive_label, directive_title = DIRECTIVE_TITLES.get(key, (key, key))
        section_items = [
            StandardSectionItem(
                **item.model_dump(),
                triggered_by_directive=key,
                triggered_by_label=directive_label,
                triggered_by_title=directive_title,
            )
            for item in route_items
        ]
        sections.append(
            StandardSection(
                key=key,
                directive_key=key,
                directive_label=directive_label,
                directive_title=directive_title,
                title=_route_title(key),
                count=len(section_items),
                items=section_items,
            )
        )
    return sections


def _build_summary(
    directives: list[str],
    standards: list[StandardItem],
    review_items: list[StandardItem],
    traits: set[str],
    description: str = "",
) -> str:
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
    if description and not _has_wireless_fact_signal(normalize(description)) and not (RADIO_ROUTE_TRAITS & traits):
        parts.append("no Wi-Fi or radio connectivity was stated in the description")
    return ". ".join(parts).strip().rstrip(".") + "."


def _directive_label(key: str) -> str:
    return DIRECTIVE_TITLES.get(key, (key, key))[0]


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
    timing_status = legislation.timing_status if legislation else "current"
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
        timing_status=timing_status,
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
        keyword_hits=row.get("keyword_hits", []),
        selection_group=row.get("selection_group"),
        selection_priority=int(row.get("selection_priority", 0)),
        required_fact_basis=row.get("required_fact_basis", "inferred"),
        jurisdiction=str(row.get("region") or "EU"),
        applicability_state=_standard_applicability_state(row, timing_status),
        applicability_hint=_route_condition_hint(row),
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


def _text_evidenced_traits(state_map: dict[str, dict[str, list[str]]]) -> set[str]:
    evidenced: set[str] = set()
    for state in TEXT_EVIDENCE_STATES:
        evidenced.update(state_map.get(state, {}).keys())

    if evidenced & (RADIO_ROUTE_TRAITS - {"radio"}):
        evidenced.add("radio")
    if evidenced & {"wifi_5ghz", "wifi_6", "wifi_7"}:
        evidenced.add("wifi")
    if evidenced & {"gsm", "lte_m", "5g_nr"}:
        evidenced.add("cellular")
    if "lorawan" in evidenced:
        evidenced.add("lora")
    if evidenced & {"cloud", "ota", "internet_connected"}:
        evidenced.update({"internet", "internet_connected"})
    return evidenced


def _route_selection_traits(
    traits: set[str],
    confirmed_traits: set[str],
    state_map: dict[str, dict[str, list[str]]],
    product_genres: set[str],
) -> tuple[set[str], list[str]]:
    if product_genres & DEFAULT_CONNECTED_ROUTE_GENRES:
        return set(traits), []

    route_traits = set(traits)
    backed_traits = confirmed_traits | _text_evidenced_traits(state_map)

    suppressed = sorted((route_traits & SENSITIVE_ROUTE_TRAITS) - backed_traits)
    route_traits.difference_update(suppressed)

    if not (route_traits & (RADIO_ROUTE_TRAITS - {"radio"})):
        route_traits.discard("radio")

    return route_traits, suppressed


def _prepare_analysis(
    description: str,
    category: str,
    depth: AnalysisDepth,
) -> PreparedAnalysis:
    normalized_description = normalize(f"{category} {description}")
    traits_data = extract_traits(description=description, category=category)
    diagnostics = list(traits_data.get("diagnostics") or [])
    matched_products = set(traits_data.get("matched_products") or [])
    routing_matched_products = set(traits_data.get("routing_matched_products") or [])
    product_genres = set(traits_data.get("product_genres") or [])
    product_type = traits_data.get("product_type")
    product_match_stage = _product_match_stage(traits_data.get("product_match_stage"))
    product_match_confidence = _confidence_level(traits_data.get("product_match_confidence"), default="low")
    routing_product_type = product_type if (product_type and product_match_confidence != "low") else None
    likely_standards = _collect_preferred_standard_codes(traits_data)

    base_trait_set = set(traits_data.get("all_traits") or [])
    trait_set = set(base_trait_set)
    confirmed_traits = set(traits_data.get("confirmed_traits") or [])
    functional_classes = set(traits_data.get("functional_classes") or [])
    trait_set, confirmed_engine_traits, extra_diag = _derive_engine_traits(description, trait_set, routing_matched_products)
    confirmed_traits.update(confirmed_engine_traits)
    diagnostics.extend(extra_diag)

    raw_state_map = _normalize_trait_state_map(traits_data.get("trait_state_map"))
    for trait in sorted(trait_set - base_trait_set):
        raw_state_map["engine_derived"].setdefault(trait, []).append("engine:derived")

    route_traits, suppressed_traits = _route_selection_traits(trait_set, confirmed_traits, raw_state_map, product_genres)
    if suppressed_traits:
        diagnostics.append("route_trait_suppressed=" + ",".join(suppressed_traits))

    route_plan = _build_route_plan(
        traits_data=traits_data,
        traits=route_traits,
        matched_products=routing_matched_products or matched_products,
        product_type=routing_product_type or product_type,
    )
    if route_plan.primary_standard_code:
        likely_standards.add(route_plan.primary_standard_code)
    likely_standards.update(route_plan.supporting_standard_codes)
    if route_plan.primary_route_family:
        diagnostics.append("primary_route_family=" + route_plan.primary_route_family)
    if route_plan.primary_standard_code:
        diagnostics.append("primary_route_standard=" + route_plan.primary_standard_code)

    return PreparedAnalysis(
        depth=depth,
        normalized_description=normalized_description,
        traits_data=traits_data,
        diagnostics=diagnostics,
        degraded_reasons=[],
        warnings=[],
        matched_products=matched_products,
        routing_matched_products=routing_matched_products,
        product_genres=product_genres,
        product_type=product_type,
        product_match_stage=product_match_stage,
        routing_product_type=routing_product_type,
        likely_standards=likely_standards,
        trait_set=trait_set,
        route_traits=route_traits,
        confirmed_traits=confirmed_traits,
        functional_classes=functional_classes,
        raw_state_map=raw_state_map,
        route_plan=route_plan,
    )


def _select_legislation_routes(
    prepared: PreparedAnalysis,
    directives: list[str] | None,
) -> LegislationSelection:
    forced_directives = [item for item in dict.fromkeys(directives or []) if item]
    if prepared.route_plan.primary_directive and prepared.route_plan.primary_directive not in forced_directives:
        forced_directives.append(prepared.route_plan.primary_directive)
    legislation_items, legislation_sections, detected_directives = _build_legislation_sections(
        traits=prepared.route_traits,
        functional_classes=prepared.functional_classes,
        product_type=prepared.routing_product_type,
        matched_products=prepared.routing_matched_products,
        product_genres=prepared.product_genres,
        confirmed_traits=prepared.confirmed_traits,
        forced_directives=forced_directives,
    )
    inferred_directive_hints = _infer_forced_directives(
        prepared.route_traits,
        prepared.routing_matched_products,
        prepared.routing_product_type,
        prepared.confirmed_traits,
        prepared.likely_standards,
    )
    if inferred_directive_hints - set(detected_directives):
        prepared.diagnostics.append("directive_hints=" + ",".join(sorted(inferred_directive_hints - set(detected_directives))))
        effective_forced_directives = sorted(set(forced_directives) | inferred_directive_hints)
        legislation_items, legislation_sections, detected_directives = _build_legislation_sections(
            traits=prepared.route_traits,
            functional_classes=prepared.functional_classes,
            product_type=prepared.routing_product_type,
            matched_products=prepared.routing_matched_products,
            product_genres=prepared.product_genres,
            confirmed_traits=prepared.confirmed_traits,
            forced_directives=effective_forced_directives,
        )
        forced_directives = effective_forced_directives
    legislation_items = _filter_legislation_items_for_route_plan(legislation_items, prepared.route_plan)
    legislation_sections = _legislation_sections_from_items(legislation_items)
    detected_directives = _directive_keys(legislation_items)
    return LegislationSelection(
        items=legislation_items,
        sections=legislation_sections,
        detected_directives=detected_directives,
        forced_directives=forced_directives,
        allowed_directives=set(detected_directives),
        legislation_by_directive=_primary_legislation_by_directive(legislation_items),
    )


def _select_standards(
    prepared: PreparedAnalysis,
    routes: LegislationSelection,
    description: str,
) -> StandardsSelection:
    collector = DegradationCollector(prepared.degraded_reasons, prepared.warnings)
    context = _standard_context(
        prepared.route_traits,
        prepared.routing_matched_products,
        prepared.routing_product_type,
        prepared.confirmed_traits,
        description,
        prepared.route_plan,
    )
    prepared.diagnostics.append("scope_route=" + context["scope_route"])
    if context["scope_reasons"]:
        prepared.diagnostics.append("scope_route_reasons=" + ";".join(context["scope_reasons"]))
    prepared.diagnostics.append("standard_context_tags=" + ",".join(sorted(context["context_tags"])))

    items = guarded_step(
        logger=logger,
        collector=collector,
        step="standards_enrichment",
        reason="standards_enrichment_failed",
        warning="Standards enrichment failed; returning classification and legislation without standards.",
        fallback={"standards": [], "review_items": [], "audit": {}, "rejections": []},
        operation=lambda: find_applicable_items(
            traits=prepared.route_traits,
            directives=routes.detected_directives,
            product_type=prepared.routing_product_type,
            matched_products=sorted(prepared.routing_matched_products),
            product_genres=sorted(prepared.product_genres),
            preferred_standard_codes=sorted(prepared.likely_standards),
            explicit_traits=set(prepared.traits_data.get("explicit_traits") or []),
            confirmed_traits=prepared.confirmed_traits,
            normalized_text=normalize(description),
            context_tags=context["context_tags"],
            allowed_directives=routes.allowed_directives,
            selection_context=context,
        ),
    )

    selected_rows = list(items.get("standards", [])) + list(items.get("review_items", []))

    dedup: dict[str, dict[str, Any]] = {}
    for row in selected_rows:
        key = str(row.get("code") or "")
        if key not in dedup or int(row.get("score", 0)) > int(dedup[key].get("score", 0)):
            dedup[key] = row

    standard_items: list[StandardItem] = []
    review_items: list[StandardItem] = []
    for row in dedup.values():
        item = _standard_item_from_row(row, routes.legislation_by_directive, prepared.route_traits)
        if item.item_type == "review":
            review_items.append(item)
        else:
            standard_items.append(item)

    standard_items = _sort_standard_items(standard_items)
    review_items = _sort_standard_items(review_items)
    current_review_items = [item for item in review_items if item.timing_status == "current"]
    missing_items = _missing_information(
        prepared.route_traits,
        prepared.routing_matched_products,
        description,
        product_type=prepared.product_type,
        product_match_stage=prepared.product_match_stage,
        route_plan=prepared.route_plan,
    )

    standard_sections = guarded_step(
        logger=logger,
        collector=collector,
        step="standard_sections",
        reason="standard_sections_failed",
        warning="Standards sections could not be assembled; standards remain available as a flat list.",
        fallback=[],
        operation=lambda: _build_standard_sections(_sort_standard_items(standard_items + review_items)),
    )

    return StandardsSelection(
        context=context,
        standard_items=standard_items,
        review_items=review_items,
        current_review_items=current_review_items,
        missing_items=missing_items,
        standard_sections=standard_sections,
        items_audit=dict(items.get("audit", {})),
        rejections=list(items.get("rejections", [])),
    )


def _compute_risk_profile(
    prepared: PreparedAnalysis,
    routes: LegislationSelection,
    standards: StandardsSelection,
) -> tuple[RiskLevel, RiskLevel, RiskLevel, list[RiskReason], RiskSummary]:
    current_risk = _current_risk(
        product_confidence=_confidence_level(prepared.traits_data.get("product_match_confidence"), default="low"),
        contradiction_severity=_contradiction_severity(prepared.traits_data.get("contradiction_severity")),
        review_items=standards.current_review_items,
        missing_items=standards.missing_items,
    )
    future_risk = _future_risk(routes.detected_directives, prepared.route_traits)
    overall_risk: RiskLevel = "LOW"
    if current_risk == "HIGH" or future_risk == "HIGH":
        overall_risk = "HIGH"
    elif current_risk == "MEDIUM" or future_risk == "MEDIUM":
        overall_risk = "MEDIUM"

    risk_reasons = _risk_reasons(
        overall_risk=overall_risk,
        current_risk=current_risk,
        future_risk=future_risk,
        traits=prepared.route_traits,
        directives=routes.detected_directives,
        product_confidence=str(prepared.traits_data.get("product_match_confidence") or "low"),
        contradictions=prepared.traits_data.get("contradictions") or [],
        review_items=standards.review_items,
        missing_items=standards.missing_items,
    )
    return (
        overall_risk,
        current_risk,
        future_risk,
        risk_reasons,
        _make_risk_summary(
            overall_risk=overall_risk,
            current_risk=current_risk,
            future_risk=future_risk,
            risk_reasons=risk_reasons,
        ),
    )


def _build_standard_match_audit(items_audit: dict[str, Any], context_tags: set[str]) -> StandardMatchAudit:
    return StandardMatchAudit(
        engine_version=ENGINE_VERSION,
        context_tags=sorted(context_tags),
        selected=[StandardAuditItem.model_validate(item) for item in items_audit.get("selected", [])],
        review=[StandardAuditItem.model_validate(item) for item in items_audit.get("review", [])],
        rejected=[StandardAuditItem.model_validate(item) for item in items_audit.get("rejected", [])],
    )


def _shadow_diff(v1: AnalysisResult, v2: AnalysisResult) -> list[ShadowDiffItem]:
    v1_traits = set(v1.confirmed_traits)
    v2_traits = set(v2.confirmed_traits)
    v1_standards = {item.code for item in v1.standards}
    v2_standards = {item.code for item in v2.standards}
    trait_evidence = {item.trait for item in v2.trait_evidence if item.confirmed}
    audited_standard_codes = {item.code for item in v2.standard_match_audit.selected}
    audited_standard_codes.update(item.code for item in v2.standard_match_audit.review)

    diff: list[ShadowDiffItem] = []
    for trait in sorted(v2_traits - v1_traits):
        diff.append(ShadowDiffItem(kind="trait", key=trait, has_evidence=trait in trait_evidence))
    for code in sorted(v2_standards - v1_standards):
        diff.append(ShadowDiffItem(kind="standard", key=code, has_evidence=code in audited_standard_codes))
    return diff


def _classification_summary(
    *,
    product_type: str | None,
    product_family: str | None,
    product_subtype: str | None,
    product_match_stage: ProductMatchStage,
    product_match_confidence: ConfidenceLevel,
    classification_is_ambiguous: bool,
) -> str:
    if product_match_stage == "subtype" and product_subtype:
        return f"Classified as {product_subtype} with {product_match_confidence} confidence."
    if product_match_stage == "family" and product_family:
        return f"Matched to the {product_family} family with {product_match_confidence} confidence; subtype remains unresolved."
    if product_type:
        return f"Detected product signal leans toward {product_type}, but the result remains provisional."
    if classification_is_ambiguous:
        return "The description does not provide enough product-specific evidence for a stable product match."
    return "Classification completed."


def _primary_uncertainties(
    contradictions: list[str],
    missing_items: list[MissingInformationItem],
    degraded_reasons: list[str],
    warnings: list[str],
) -> list[str]:
    items: list[str] = []
    seen: set[str] = set()
    for value in contradictions:
        if value and value not in seen:
            seen.add(value)
            items.append(value)
    for item in missing_items:
        if item.message and item.message not in seen:
            seen.add(item.message)
            items.append(item.message)
    for value in warnings + degraded_reasons:
        if value and value not in seen:
            seen.add(value)
            items.append(value)
    return items[:8]


def _safe_product_match_audit(traits_data: dict[str, Any], normalized_description: str) -> ProductMatchAudit:
    raw = traits_data.get("product_match_audit") or traits_data.get("audit")
    if isinstance(raw, dict):
        try:
            return ProductMatchAudit.model_validate(raw)
        except (ValidationError, TypeError, ValueError):
            logger.exception("analysis_degraded step=product_match_audit")
    return ProductMatchAudit(engine_version=ENGINE_VERSION, normalized_text=normalized_description)


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


def _safe_knowledge_base_meta(
    degraded_reasons: list[str],
    warnings: list[str],
) -> KnowledgeBaseMeta:
    collector = DegradationCollector(degraded_reasons, warnings)
    return guarded_step(
        logger=logger,
        collector=collector,
        step="knowledge_base_meta",
        reason="knowledge_base_meta_unavailable",
        warning="Catalog metadata could not be loaded during result assembly; core analysis remains available.",
        fallback=KnowledgeBaseMeta(),
        operation=lambda: KnowledgeBaseMeta(**load_meta()),
        handled_exceptions=(ValidationError, TypeError, ValueError, RuntimeError),
    )


def _maybe_attach_shadow_diff(
    result: AnalysisResult,
    *,
    description: str,
    category: str,
    directives: list[str] | None,
    depth: AnalysisDepth,
    prepared: PreparedAnalysis,
) -> AnalysisResult:
    if not ENABLE_ENGINE_V2_SHADOW:
        return result

    collector = DegradationCollector(prepared.degraded_reasons, prepared.warnings)
    shadow_diff = guarded_step(
        logger=logger,
        collector=collector,
        step="shadow_diff",
        reason="shadow_diff_failed",
        warning="Shadow comparison could not be computed; the primary analysis remains available.",
        fallback=None,
        operation=lambda: _shadow_diff(
            analyze_v1(description=description, category=category, directives=directives, depth=depth),
            result,
        ),
        handled_exceptions=(TypeError, ValueError, RuntimeError, ValidationError),
    )
    if shadow_diff is None:
        result.degraded_mode = True
        result.degraded_reasons = prepared.degraded_reasons
        result.warnings = prepared.warnings
        return result
    result.analysis_audit.shadow_diff = shadow_diff

    return result


def _build_analysis_result(
    *,
    description: str,
    depth: AnalysisDepth,
    normalized_description: str,
    traits_data: dict[str, Any],
    diagnostics: list[str],
    matched_products: set[str],
    routing_matched_products: set[str],
    product_genres: set[str],
    likely_standards: set[str],
    trait_set: set[str],
    confirmed_traits: set[str],
    detected_directives: list[str],
    forced_directives: list[str],
    legislation_items: list[LegislationItem],
    legislation_sections: list[LegislationSection],
    standard_items: list[StandardItem],
    review_items: list[StandardItem],
    missing_items: list[MissingInformationItem],
    standard_sections: list[StandardSection],
    risk_reasons: list[RiskReason],
    risk_summary: RiskSummary,
    summary: str,
    findings: list[Finding],
    known_facts: list[KnownFactItem],
    trait_evidence: list[TraitEvidenceItem],
    product_match_audit: ProductMatchAudit,
    standard_match_audit: StandardMatchAudit,
    route_context: RouteContext,
    overall_risk: RiskLevel,
    current_risk: RiskLevel,
    future_risk: RiskLevel,
    degraded_reasons: list[str],
    warnings: list[str],
) -> AnalysisResult:
    product_match_stage = _product_match_stage(traits_data.get("product_match_stage"))
    product_match_confidence = _confidence_level(traits_data.get("product_match_confidence"), default="low")
    classification_confidence_below_threshold = product_match_confidence == "low"
    classification_is_ambiguous = classification_confidence_below_threshold or product_match_stage != "subtype"
    contradictions = list(traits_data.get("contradictions") or [])
    contradiction_severity = _contradiction_severity(traits_data.get("contradiction_severity"))
    inferred_traits = sorted(set(traits_data.get("inferred_traits") or []) | (trait_set - set(traits_data.get("explicit_traits") or [])))
    top_actions_limit = {"quick": 2, "standard": 3, "deep": 5}[depth]
    suggested_questions_limit = {"quick": 2, "standard": 6, "deep": 8}[depth]
    quick_adds_limit = {"quick": 4, "standard": 8, "deep": 10}[depth]
    top_actions = _top_actions_from_missing(missing_items, top_actions_limit)
    knowledge_base_meta = _safe_knowledge_base_meta(degraded_reasons, warnings)
    primary_regimes = [section.key for section in standard_sections[:4]]

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
        ambiguity_flag_count=1 if (contradictions or classification_is_ambiguous) else 0,
        missing_information_count=len(missing_items),
    )

    analysis_audit = AnalysisAudit(
        allowed_directives=detected_directives,
        matched_products=sorted(matched_products),
        routing_matched_products=sorted(routing_matched_products),
        preferred_standards=sorted(likely_standards),
        product_genres=sorted(product_genres),
        product_family=traits_data.get("product_family"),
        product_subtype=traits_data.get("product_subtype"),
        product_match_stage=product_match_stage,
        classification_is_ambiguous=classification_is_ambiguous,
        classification_confidence_below_threshold=classification_confidence_below_threshold,
        depth=depth,
        engine_version=ENGINE_VERSION,
        normalized_description=normalized_description,
        context_tags=route_context.context_tags,
    )

    return AnalysisResult(
        product_summary=description.strip(),
        overall_risk=overall_risk,
        current_compliance_risk=current_risk,
        future_watchlist_risk=future_risk,
        summary=summary,
        analyzed_description=description.strip(),
        normalized_description=normalized_description,
        product_type=traits_data.get("product_type"),
        product_family=traits_data.get("product_family"),
        product_family_confidence=traits_data.get("product_family_confidence", "low"),
        product_subtype=traits_data.get("product_subtype"),
        product_subtype_confidence=traits_data.get("product_subtype_confidence", "low"),
        product_match_stage=product_match_stage,
        product_match_confidence=product_match_confidence,
        classification_is_ambiguous=classification_is_ambiguous,
        classification_confidence_below_threshold=classification_confidence_below_threshold,
        classification_summary=_classification_summary(
            product_type=traits_data.get("product_type"),
            product_family=traits_data.get("product_family"),
            product_subtype=traits_data.get("product_subtype"),
            product_match_stage=product_match_stage,
            product_match_confidence=product_match_confidence,
            classification_is_ambiguous=classification_is_ambiguous,
        ),
        primary_uncertainties=_primary_uncertainties(contradictions, missing_items, degraded_reasons, warnings),
        route_trigger_reasons=route_context.route_trigger_reasons,
        triggered_routes=detected_directives,
        primary_route_standard_code=route_context.primary_route_standard_code,
        primary_route_reason=route_context.primary_route_reason,
        overlay_routes=route_context.overlay_routes,
        route_confidence=route_context.route_confidence,
        product_candidates=traits_data.get("product_candidates") or [],
        functional_classes=traits_data.get("functional_classes") or [],
        confirmed_functional_classes=traits_data.get("confirmed_functional_classes") or [],
        explicit_traits=traits_data.get("explicit_traits") or [],
        confirmed_traits=sorted(confirmed_traits),
        inferred_traits=inferred_traits,
        assumptions_or_inferred_traits=inferred_traits,
        all_traits=sorted(trait_set),
        directives=detected_directives,
        forced_directives=forced_directives,
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
        contradictions=contradictions,
        contradiction_severity=contradiction_severity,
        diagnostics=diagnostics,
        warnings=warnings,
        degraded_mode=bool(degraded_reasons),
        degraded_reasons=degraded_reasons,
        stats=stats,
        knowledge_base_meta=knowledge_base_meta,
        analysis_audit=analysis_audit,
        api_version=API_VERSION,
        engine_version=ENGINE_VERSION,
        catalog_version=knowledge_base_meta.version,
        trait_evidence=trait_evidence,
        product_match_audit=product_match_audit,
        standard_match_audit=standard_match_audit,
        standard_sections=standard_sections,
        standards_by_directive=standard_sections,
        legislation_sections=legislation_sections,
        risk_reasons=risk_reasons,
        risk_summary=risk_summary,
        hero_summary=HeroSummary(
            title="RuleGrid Regulatory Scoping",
            subtitle="Describe the product clearly to generate the standards route and the applicable legislation path.",
            primary_regimes=primary_regimes,
            confidence=product_match_confidence,
            depth=depth,
        ),
        confidence_panel=ConfidencePanel(
            confidence=product_match_confidence,
            classification_is_ambiguous=classification_is_ambiguous,
            classification_confidence_below_threshold=classification_confidence_below_threshold,
            matched_products=sorted(matched_products),
            product_family=traits_data.get("product_family"),
            product_genres=sorted(product_genres),
            product_subtype=traits_data.get("product_subtype"),
            product_match_stage=product_match_stage,
        ),
        input_gaps_panel=InputGapsPanel(
            items=missing_items,
            next_actions=top_actions,
            high_importance_count=len([item for item in missing_items if item.importance == "high"]),
        ),
        top_actions=top_actions,
        next_actions=top_actions,
        current_path=[section.title for section in standard_sections],
        future_watchlist=[item.title for item in legislation_items if item.bucket == "future"],
        suggested_questions=[item.message for item in missing_items[:suggested_questions_limit]],
        suggested_quick_adds=_build_quick_adds(missing_items)[:quick_adds_limit],
        known_facts=known_facts,
        known_fact_keys=[item.key for item in known_facts],
        route_context=route_context,
        primary_jurisdiction="EU",
        supported_jurisdictions=["EU"],
        findings=findings,
    )


def analyze_v1(
    description: str,
    category: str = "",
    directives: list[str] | None = None,
    depth: str = "standard",
) -> AnalysisResult:
    analysis_depth = _analysis_depth(depth)
    traits_data = extract_traits_v1(description=description, category=category)
    diagnostics = list(traits_data.get("diagnostics") or [])
    matched_products = set(traits_data.get("matched_products") or [])
    routing_matched_products = set(traits_data.get("routing_matched_products") or [])
    product_genres = set(traits_data.get("product_genres") or [])
    product_type = traits_data.get("product_type")
    product_match_stage = _product_match_stage(traits_data.get("product_match_stage"))
    routing_product_type = product_type if product_match_stage == "subtype" else None
    likely_standards = _collect_preferred_standard_codes(traits_data)

    trait_set = set(traits_data.get("all_traits") or [])
    confirmed_traits = set(traits_data.get("confirmed_traits") or [])
    functional_classes = set(traits_data.get("functional_classes") or [])
    trait_set, confirmed_engine_traits, extra_diag = _derive_engine_traits(description, trait_set, routing_matched_products)
    confirmed_traits.update(confirmed_engine_traits)
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
    inferred_directive_hints = _infer_forced_directives(
        trait_set,
        routing_matched_products,
        routing_product_type,
        confirmed_traits,
        likely_standards,
    )
    if inferred_directive_hints - set(detected_directives):
        diagnostics.append("directive_hints=" + ",".join(sorted(inferred_directive_hints - set(detected_directives))))
        legislation_items, legislation_sections, detected_directives = _build_legislation_sections(
            traits=trait_set,
            functional_classes=functional_classes,
            product_type=routing_product_type,
            matched_products=routing_matched_products,
            product_genres=product_genres,
            confirmed_traits=confirmed_traits,
            forced_directives=sorted({item for item in (directives or []) if item} | inferred_directive_hints),
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
    missing_items = _missing_information(
        trait_set,
        routing_matched_products,
        description,
        product_type=product_type,
        product_match_stage=product_match_stage,
    )
    standard_sections = _build_standard_sections(all_standard_items)

    current_risk = _current_risk(
        product_confidence=_confidence_level(traits_data.get("product_match_confidence"), default="low"),
        contradiction_severity=_contradiction_severity(traits_data.get("contradiction_severity")),
        review_items=current_review_items,
        missing_items=missing_items,
    )
    future_risk = _future_risk(detected_directives, trait_set)
    overall_risk: RiskLevel = "LOW"
    if current_risk == "HIGH" or future_risk == "HIGH":
        overall_risk = "HIGH"
    elif current_risk == "MEDIUM" or future_risk == "MEDIUM":
        overall_risk = "MEDIUM"
    risk_reasons = _risk_reasons(
        overall_risk=overall_risk,
        current_risk=current_risk,
        future_risk=future_risk,
        traits=trait_set,
        directives=detected_directives,
        product_confidence=str(traits_data.get("product_match_confidence") or "low"),
        contradictions=traits_data.get("contradictions") or [],
        review_items=review_items,
        missing_items=missing_items,
    )
    risk_summary = _make_risk_summary(
        overall_risk=overall_risk,
        current_risk=current_risk,
        future_risk=future_risk,
        risk_reasons=risk_reasons,
    )

    summary = _build_summary(detected_directives, standard_items, review_items, trait_set, description)
    findings = _build_findings(
        depth=analysis_depth,
        legislation_items=legislation_items,
        standards=standard_items,
        review_items=review_items,
        missing_items=missing_items,
        contradictions=traits_data.get("contradictions") or [],
        contradiction_severity=_contradiction_severity(traits_data.get("contradiction_severity")),
    )
    known_facts = _build_known_facts(description)
    return _build_analysis_result(
        description=description,
        depth=analysis_depth,
        normalized_description=normalize(f"{category} {description}"),
        traits_data=traits_data,
        diagnostics=diagnostics,
        matched_products=matched_products,
        routing_matched_products=routing_matched_products,
        product_genres=product_genres,
        likely_standards=likely_standards,
        trait_set=trait_set,
        confirmed_traits=confirmed_traits,
        detected_directives=detected_directives,
        forced_directives=[item for item in dict.fromkeys(directives or []) if item],
        legislation_items=legislation_items,
        legislation_sections=legislation_sections,
        standard_items=standard_items,
        review_items=review_items,
        missing_items=missing_items,
        standard_sections=standard_sections,
        risk_reasons=risk_reasons,
        risk_summary=risk_summary,
        summary=summary,
        findings=findings,
        known_facts=known_facts,
        trait_evidence=[],
        product_match_audit=_safe_product_match_audit(traits_data, normalize(f"{category} {description}")),
        standard_match_audit=StandardMatchAudit(engine_version=ENGINE_VERSION),
        route_context=RouteContext(known_fact_keys=[item.key for item in known_facts], jurisdiction="EU"),
        overall_risk=overall_risk,
        current_risk=current_risk,
        future_risk=future_risk,
        degraded_reasons=[],
        warnings=[],
    )


def analyze(
    description: str,
    category: str = "",
    directives: list[str] | None = None,
    depth: str = "standard",
    trace: AnalysisTrace | None = None,
) -> AnalysisResult:
    analysis_depth = _analysis_depth(depth)
    stage_started = perf_counter()
    prepared = _prepare_analysis(description, category, analysis_depth)
    collector = DegradationCollector(prepared.degraded_reasons, prepared.warnings)
    if trace is not None:
        trace.record_stage("classification", stage_started)

    stage_started = perf_counter()
    routes = _select_legislation_routes(prepared, directives)
    if trace is not None:
        trace.record_stage("legislation_routing", stage_started)

    stage_started = perf_counter()
    standards = _select_standards(prepared, routes, description)
    if trace is not None:
        trace.record_stage("standards_selection", stage_started)

    overall_risk, current_risk, future_risk, risk_reasons, risk_summary = _compute_risk_profile(prepared, routes, standards)

    stage_started = perf_counter()
    summary = guarded_step(
        logger=logger,
        collector=collector,
        step="summary",
        reason="summary_failed",
        warning="The narrative summary could not be assembled; returning a compact fallback summary.",
        fallback=(
            f"{len(routes.detected_directives)} legislation routes, {len(standards.standard_items)} standards, "
            f"and {len(standards.review_items)} review items identified."
        ),
        operation=lambda: _build_summary(
            routes.detected_directives,
            standards.standard_items,
            standards.review_items,
            prepared.route_traits,
            description,
        ),
    )

    findings = guarded_step(
        logger=logger,
        collector=collector,
        step="findings",
        reason="findings_failed",
        warning="Actionable findings could not be assembled; the route output remains available.",
        fallback=[],
        operation=lambda: _build_findings(
            depth=analysis_depth,
            legislation_items=routes.items,
            standards=standards.standard_items,
            review_items=standards.review_items,
            missing_items=standards.missing_items,
            contradictions=prepared.traits_data.get("contradictions") or [],
            contradiction_severity=_contradiction_severity(prepared.traits_data.get("contradiction_severity")),
        ),
    )

    known_facts = guarded_step(
        logger=logger,
        collector=collector,
        step="known_facts",
        reason="known_facts_failed",
        warning="Known-fact extraction could not be completed; the core analysis remains available.",
        fallback=[],
        operation=lambda: _build_known_facts(description),
    )

    trait_evidence = _trait_evidence_from_state_map(prepared.raw_state_map, prepared.confirmed_traits)
    product_match_audit = _safe_product_match_audit(prepared.traits_data, prepared.normalized_description)
    rejected_audit_rows = list(standards.items_audit.get("rejected", []))
    selected_audit_rows = list(standards.items_audit.get("selected", []))
    review_audit_rows = list(standards.items_audit.get("review", []))
    audited_rejected_codes = {str(row.get("code") or "") for row in rejected_audit_rows}
    rejected_audit_rows.extend(
        {
            "code": row.get("code"),
            "title": row.get("title", row.get("code")),
            "outcome": "rejected",
            "score": 0,
            "confidence": "low",
            "fact_basis": "inferred",
            "selection_group": None,
            "selection_priority": 0,
            "keyword_hits": row.get("keyword_hits", []),
            "reason": row.get("reason") or row.get("rejection_reason"),
        }
        for row in standards.rejections
        if str(row.get("code") or "") not in audited_rejected_codes
    )
    standard_match_audit = guarded_step(
        logger=logger,
        collector=collector,
        step="standard_match_audit",
        reason="standard_match_audit_failed",
        warning="Standard audit details could not be assembled; returning the selected routes without full audit detail.",
        fallback=StandardMatchAudit(
            engine_version=ENGINE_VERSION,
            context_tags=sorted(standards.context["context_tags"]),
        ),
        operation=lambda: _build_standard_match_audit(
            {
                "selected": selected_audit_rows
                or [
                    {
                        "code": item.code,
                        "title": item.title,
                        "outcome": "selected",
                        "score": item.score,
                        "confidence": item.confidence,
                        "fact_basis": item.fact_basis,
                        "selection_group": item.selection_group,
                        "selection_priority": item.selection_priority,
                        "keyword_hits": item.keyword_hits,
                        "reason": item.reason,
                    }
                    for item in standards.standard_items
                ],
                "review": review_audit_rows
                or [
                    {
                        "code": item.code,
                        "title": item.title,
                        "outcome": "review",
                        "score": item.score,
                        "confidence": item.confidence,
                        "fact_basis": item.fact_basis,
                        "selection_group": item.selection_group,
                        "selection_priority": item.selection_priority,
                        "keyword_hits": item.keyword_hits,
                        "reason": item.reason,
                    }
                    for item in standards.review_items
                ],
                "rejected": rejected_audit_rows,
            },
            standards.context["context_tags"],
        ),
        handled_exceptions=(ValidationError, TypeError, ValueError, RuntimeError),
    )

    result = _build_analysis_result(
        description=description,
        depth=analysis_depth,
        normalized_description=prepared.normalized_description,
        traits_data=prepared.traits_data,
        diagnostics=prepared.diagnostics,
        matched_products=prepared.matched_products,
        routing_matched_products=prepared.routing_matched_products,
        product_genres=prepared.product_genres,
        likely_standards=prepared.likely_standards,
        trait_set=prepared.trait_set,
        confirmed_traits=prepared.confirmed_traits,
        detected_directives=routes.detected_directives,
        forced_directives=routes.forced_directives,
        legislation_items=routes.items,
        legislation_sections=routes.sections,
        standard_items=standards.standard_items,
        review_items=standards.review_items,
        missing_items=standards.missing_items,
        standard_sections=standards.standard_sections,
        risk_reasons=risk_reasons,
        risk_summary=risk_summary,
        summary=summary,
        findings=findings,
        known_facts=known_facts,
        trait_evidence=trait_evidence,
        product_match_audit=product_match_audit,
        standard_match_audit=standard_match_audit,
        route_context=_route_context_summary(
            standards.context,
            known_facts,
            [directive for directive in routes.detected_directives if directive in OVERLAY_DIRECTIVE_KEYS],
        ),
        overall_risk=overall_risk,
        current_risk=current_risk,
        future_risk=future_risk,
        degraded_reasons=prepared.degraded_reasons,
        warnings=prepared.warnings,
    )
    if trace is not None:
        trace.record_stage("response_assembly", stage_started)

    return _maybe_attach_shadow_diff(
        result,
        description=description,
        category=category,
        directives=directives,
        depth=analysis_depth,
        prepared=prepared,
    )
