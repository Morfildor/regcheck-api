from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
import re
from time import perf_counter
from typing import Any, Literal

from app.domain.catalog_types import ProductCatalogRow
from app.domain.models import (
    ConfidenceLevel,
    ContradictionSeverity,
    KnownFactItem,
    LegislationItem,
    LegislationSection,
    MissingInformationItem,
    ProductMatchStage,
    RouteContext,
    StandardItem,
    StandardSection,
)
from app.services.classifier import ENGINE_VERSION as CLASSIFIER_ENGINE_VERSION, extract_traits, normalize
from app.services.knowledge_base import get_knowledge_base_snapshot


AnalysisDepth = Literal["quick", "standard", "deep"]


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


def _products_by_id() -> dict[str, ProductCatalogRow]:
    return {
        str(row.get("id")): row
        for row in get_knowledge_base_snapshot().products
        if isinstance(row.get("id"), str)
    }


def _route_product_row(product_type: str | None, matched_products: set[str] | None = None) -> ProductCatalogRow | None:
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
    for row in get_knowledge_base_snapshot().legislations:
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
    from .result_builder import _normalize_trait_state_map

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
    from .result_builder import _primary_legislation_by_directive

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



__all__ = [
    "ENGINE_VERSION",
    "AnalysisDepth",
    "AnalysisTrace",
    "DIRECTIVE_ORDER",
    "DIRECTIVE_TITLES",
    "LegislationSelection",
    "PreparedAnalysis",
    "ROUTE_FAMILY_SCOPE",
    "ROUTE_FAMILY_PRIMARY_DIRECTIVE",
    "RoutePlan",
    "_analysis_depth",
    "_build_legislation_sections",
    "_build_route_plan",
    "_collect_preferred_standard_codes",
    "_confidence_from_score",
    "_confidence_level",
    "_contradiction_severity",
    "_current_date",
    "_derive_directives",
    "_derive_engine_traits",
    "_directive_keys",
    "_directive_rank",
    "_filter_legislation_items_for_route_plan",
    "_has_any",
    "_has_small_avict_lvd_power_signal",
    "_has_wireless_fact_signal",
    "_infer_forced_directives",
    "_keep_preferred_62368_review_in_appliance_scope",
    "_legislation_applicability_state",
    "_legislation_sections_from_items",
    "_match_standard",
    "_parse_date",
    "_pick_legislations",
    "_prepare_analysis",
    "_product_match_stage",
    "_products_by_id",
    "_route_context_summary",
    "_route_product_row",
    "_route_scope_from_family",
    "_route_selection_traits",
    "_route_title",
    "_scope_route",
    "_select_legislation_routes",
    "_standard_applicability_state",
    "_standard_context",
    "_standard_primary_directive",
    "_string_list",
    "_text_evidenced_traits",
    "_timing_status",
]
