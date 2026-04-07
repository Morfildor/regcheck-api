from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import date
from typing import Any, Literal, TypedDict, cast

from app.domain.catalog_types import LegislationCatalogRow, ProductCatalogRow, StandardCatalogRow
from app.domain.models import (
    ConfidenceLevel,
    ContradictionSeverity,
    FactBasis,
    KnownFactItem,
    LegislationItem,
    LegislationSection,
    ProductMatchStage,
    RouteContext,
    TimingStatus,
)
from app.services.classifier import ENGINE_VERSION as CLASSIFIER_ENGINE_VERSION, extract_traits, normalize
from app.services.knowledge_base import get_knowledge_base_snapshot
from app.services.standards_engine.contracts import SelectionContext

from . import routing_context_helpers as _context_helpers
from . import routing_gate_helpers as _gate_helpers
from . import routing_legislation_helpers as _legislation_helpers
from . import routing_plan_helpers as _plan_helpers
from . import routing_scalar_helpers as _scalar_helpers
from .contracts import ClassifierTraitsSnapshot, NormalizedTraitStateMap
from .route_anchors import (
    best_primary_standard_for_family as _best_primary_standard_for_family_shared,
    family_from_standard_code as _family_from_standard_code_shared,
    normalized_standard_codes as _normalized_standard_codes_shared,
    route_family_primary_directive_map,
    route_family_scope_map,
    route_standard_family_rules,
)
from .routing_models import AnalysisDepth, AnalysisTrace, LegislationSelection, PreparedAnalysis, RoutePlan, StandardsSelection


LegislationRowLike = LegislationCatalogRow | Mapping[str, Any]
StandardRowLike = StandardCatalogRow | Mapping[str, Any]
StandardMatchProductType = Literal["product", "preferred_product"]


class StandardMatchMeta(TypedDict):
    matched_traits_all: list[str]
    matched_traits_any: list[str]
    missing_required_traits: list[str]
    excluded_by_traits: list[str]
    product_match_type: StandardMatchProductType | None


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
    r"\bsmart ring\b",
    r"\bwearable ring\b",
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
    "wifi_extender",
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
    "document_scanner",
    "external_power_supply",
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
    "wifi_extender",
    "laptop",
    "desktop_pc",
    "server",
    "nas",
    "monitor",
    "nvr_dvr_recorder",
    "office_printer",
    "smart_tv",
    "streaming_device",
    "set_top_box",
    "projector",
    "usb_wall_charger",
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
    "heating_element",
    "heating_personal_environment",
    "humidification",
    "lighting",
    "motorized",
    "oral_care",
    "optical_emission",
    "personal_care",
    "pump_system",
    "compressor_system",
    "fan_air_mover",
    "surface_cleaning",
    "steam",
    "textile_care",
    "water_contact",
    "water_heating",
    "washing",
}

AV_ICT_SUPPORTING_TRAITS = {
    "av_ict",
    "access_point_role",
    "camera",
    "data_storage",
    "display",
    "gateway_role",
    "home_security",
    "microphone",
    "repeater_role",
    "router_role",
    "speaker",
    "surveillance",
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
    "cloud_dependent",
    "cloud",
    "internet",
    "internet_connected",
    "ota",
    "account",
    "account_required",
    "authentication",
    "monetary_transaction",
}

SENSITIVE_ROUTE_TRAITS = RADIO_ROUTE_TRAITS | CONNECTED_ROUTE_TRAITS

RED_ART_33_TRAITS = {
    "account",
    "authentication",
    "personal_data_likely",
    "health_data",
    "monetary_transaction",
    "internet",
    "cloud",
    "camera",
    "microphone",
    "location",
    "emergency_use",
}

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

def _classifier_snapshot(traits_data: ClassifierTraitsSnapshot | Mapping[str, Any]) -> ClassifierTraitsSnapshot:
    if isinstance(traits_data, ClassifierTraitsSnapshot):
        return traits_data
    return ClassifierTraitsSnapshot.from_mapping(traits_data)


def _legislation_row(row: LegislationRowLike) -> LegislationCatalogRow:
    if isinstance(row, LegislationCatalogRow):
        return row
    return LegislationCatalogRow.model_validate(dict(row))


def _standard_row(row: StandardRowLike) -> StandardCatalogRow:
    if isinstance(row, StandardCatalogRow):
        return row
    return StandardCatalogRow.model_validate(dict(row))


def _products_by_id() -> dict[str, ProductCatalogRow]:
    return _plan_helpers._products_by_id(get_knowledge_base_snapshot().products)


def _route_product_row(product_type: str | None, matched_products: set[str] | None = None) -> ProductCatalogRow | None:
    return _plan_helpers._route_product_row(_products_by_id(), product_type, matched_products)


def _route_scope_from_family(route_family: str | None) -> str | None:
    return _plan_helpers._route_scope_from_family(route_family_scope_map(), route_family)


def _normalized_standard_codes(codes: set[str] | list[str] | None) -> list[str]:
    return _normalized_standard_codes_shared(codes)


def _family_from_standard_code(code: str, prefer_wearable: bool) -> str | None:
    return _family_from_standard_code_shared(code, prefer_wearable)


def _best_primary_standard_for_family(route_family: str, preferred_codes: list[str]) -> str | None:
    return _best_primary_standard_for_family_shared(route_family, preferred_codes)


def _build_route_plan(
    traits_data: ClassifierTraitsSnapshot | Mapping[str, Any],
    traits: set[str],
    matched_products: set[str],
    product_type: str | None,
) -> RoutePlan:
    snapshot = _classifier_snapshot(traits_data)
    return _plan_helpers._build_route_plan(
        snapshot,
        traits,
        matched_products,
        product_type,
        route_product_row=_route_product_row,
        route_family_scope=route_family_scope_map(),
        route_family_primary_directive=route_family_primary_directive_map(),
        route_standard_family_rules=route_standard_family_rules(),
    )


def _scope_route(
    traits: set[str],
    matched_products: set[str],
    product_type: str | None,
    confirmed_traits: set[str] | None = None,
    route_family: str | None = None,
) -> tuple[str, list[str]]:
    return _context_helpers._scope_route(
        traits,
        matched_products,
        product_type,
        confirmed_traits,
        route_family,
        route_product_row=_route_product_row,
        route_scope_from_family=_route_scope_from_family,
        appliance_primary_traits=APPLIANCE_PRIMARY_TRAITS,
        av_ict_product_hints=AV_ICT_PRODUCT_HINTS,
        av_ict_supporting_traits=AV_ICT_SUPPORTING_TRAITS,
    )


def _has_any(text: str, patterns: list[str]) -> bool:
    return _scalar_helpers._has_any(text, patterns)


def _has_wireless_fact_signal(text: str) -> bool:
    return _scalar_helpers._has_wireless_fact_signal(text, WIRELESS_FACT_PATTERNS)


def _directive_rank(key: str) -> int:
    return _scalar_helpers._directive_rank(DIRECTIVE_ORDER, key)


def _route_title(key: str) -> str:
    return _scalar_helpers._route_title(key)


def _analysis_depth(depth: str) -> AnalysisDepth:
    return _scalar_helpers._analysis_depth(depth)


def _confidence_level(value: Any, default: ConfidenceLevel = "medium") -> ConfidenceLevel:
    return _scalar_helpers._confidence_level(value, default)


def _contradiction_severity(value: Any) -> ContradictionSeverity:
    return _scalar_helpers._contradiction_severity(value)


def _product_match_stage(value: Any) -> ProductMatchStage:
    return _scalar_helpers._product_match_stage(value)


def _current_date() -> date:
    return date.today()


def _string_list(value: Any) -> list[str]:
    return _scalar_helpers._string_list(value)


def _parse_date(value: Any) -> date | None:
    return _scalar_helpers._parse_date(value)


def _timing_status(row: LegislationRowLike, today: date) -> str:
    return _legislation_helpers._timing_status(_legislation_row(row), today, _parse_date)


def _fact_basis_for_legislation(
    row: LegislationRowLike,
    traits: set[str],
    confirmed_traits: set[str],
) -> str:
    return _legislation_helpers._fact_basis_for_legislation(_legislation_row(row), traits, confirmed_traits)


def _legislation_matches(
    row: LegislationRowLike,
    traits: set[str],
    functional_classes: set[str],
    product_type: str | None,
    matched_products: set[str],
    product_genres: set[str],
) -> bool:
    return _legislation_helpers._legislation_matches(
        _legislation_row(row),
        traits,
        functional_classes,
        product_type,
        matched_products,
        product_genres,
    )


def _legislation_sort_key(row: LegislationRowLike) -> tuple[int, int, str]:
    return _legislation_helpers._legislation_sort_key(_legislation_row(row), _directive_rank)


def _directive_keys(items: list[LegislationItem]) -> list[str]:
    return _legislation_helpers._directive_keys(items)


def _build_red_sub_articles(traits: set[str]) -> list[dict[str, Any]]:
    return _legislation_helpers._build_red_sub_articles(traits, RED_ART_33_TRAITS)


def _remove_standalone_lvd_emc_for_radio(items: list[LegislationItem]) -> list[LegislationItem]:
    return _legislation_helpers._remove_standalone_lvd_emc_for_radio(items)


def _attach_red_sub_articles(items: list[LegislationItem], traits: set[str]) -> list[LegislationItem]:
    return _legislation_helpers._attach_red_sub_articles(items, traits, RED_ART_33_TRAITS)


def _pick_legislations(
    traits: set[str],
    functional_classes: set[str],
    product_type: str | None,
    forced_directives: list[str] | None = None,
    matched_products: set[str] | None = None,
    product_genres: set[str] | None = None,
    confirmed_traits: set[str] | None = None,
) -> list[LegislationCatalogRow]:
    matched_products = matched_products or set()
    product_genres = product_genres or set()
    confirmed_traits = confirmed_traits or set(traits)
    forced_set = {item for item in (forced_directives or []) if item}
    today = _current_date()

    picked: list[LegislationCatalogRow] = []
    for row in get_knowledge_base_snapshot().legislations:
        directive_key = row.directive_key or "OTHER"
        matched = _legislation_matches(row, traits, functional_classes, product_type, matched_products, product_genres)
        forced = directive_key in forced_set and row.bucket != "informational"
        if not matched and not forced:
            continue

        picked.append(
            row.model_copy(
                update={
                    "timing_status": _timing_status(row, today),
                    "evidence_strength": _fact_basis_for_legislation(row, traits, confirmed_traits),
                    "is_forced": forced,
                    "applicability": "conditional" if forced and not matched else row.applicability,
                }
            )
        )

    picked.sort(key=_legislation_sort_key)
    return picked


def _confidence_from_score(score: int) -> ConfidenceLevel:
    return _scalar_helpers._confidence_from_score(score)


def _collect_preferred_standard_codes(traits_data: ClassifierTraitsSnapshot | Mapping[str, Any]) -> set[str]:
    snapshot = _classifier_snapshot(traits_data)
    preferred = set(snapshot.preferred_standard_codes)
    if snapshot.product_match_stage == "family" and snapshot.product_type:
        for candidate in snapshot.product_candidates:
            if candidate.id == snapshot.product_type:
                preferred.update(code for code in candidate.likely_standards if "review" in str(code).lower())
                break
        return preferred
    if snapshot.product_match_stage != "subtype":
        return preferred

    routing_matched_products = set(snapshot.routing_matched_products)
    for candidate in snapshot.product_candidates:
        if candidate.id in routing_matched_products:
            preferred.update(candidate.likely_standards)
    return preferred


def _keep_preferred_62368_review_in_appliance_scope(
    item: StandardRowLike,
    product_genres: set[str] | None,
    preferred_standard_codes: set[str] | None,
) -> bool:
    return _context_helpers._keep_preferred_62368_review_in_appliance_scope(
        _standard_row(item),
        product_genres,
        preferred_standard_codes,
        SMALL_SMART_62368_GENRES,
    )


def _has_small_avict_lvd_power_signal(traits: set[str], matched_products: set[str], product_type: str | None) -> bool:
    return _context_helpers._has_small_avict_lvd_power_signal(
        traits,
        matched_products,
        product_type,
        AV_ICT_PRODUCT_HINTS,
        WIFI_5GHZ_DEFAULT_PRODUCT_HINTS,
    )


def _infer_forced_directives(
    traits: set[str],
    matched_products: set[str],
    product_type: str | None,
    confirmed_traits: set[str],
    preferred_standard_codes: set[str] | None = None,
) -> set[str]:
    return _context_helpers._infer_forced_directives(
        traits,
        matched_products,
        product_type,
        confirmed_traits,
        preferred_standard_codes,
        scope_route=lambda scope_traits, scope_products, scope_product_type, scope_confirmed_traits: _scope_route(
            scope_traits,
            scope_products,
            scope_product_type,
            scope_confirmed_traits,
        ),
        av_ict_product_hints=AV_ICT_PRODUCT_HINTS,
        personal_care_product_hints=PERSONAL_CARE_PRODUCT_HINTS,
        wifi_5ghz_default_product_hints=WIFI_5GHZ_DEFAULT_PRODUCT_HINTS,
    )


def _derive_engine_traits(
    description: str,
    traits: set[str],
    matched_products: set[str],
) -> tuple[set[str], set[str], list[str]]:
    return _context_helpers._derive_engine_traits(
        description,
        traits,
        matched_products,
        has_any=_has_any,
        power_external_negation_patterns=POWER_EXTERNAL_NEGATION_PATTERNS,
        power_external_patterns=POWER_EXTERNAL_PATTERNS,
        power_internal_patterns=POWER_INTERNAL_PATTERNS,
        wearable_patterns=WEARABLE_PATTERNS,
        handheld_patterns=HANDHELD_PATTERNS,
        close_proximity_patterns=CLOSE_PROXIMITY_PATTERNS,
        wifi_5ghz_explicit_patterns=WIFI_5GHZ_EXPLICIT_PATTERNS,
        wifi_24_only_patterns=WIFI_24_ONLY_PATTERNS,
        av_ict_product_hints=AV_ICT_PRODUCT_HINTS,
        wifi_5ghz_default_product_hints=WIFI_5GHZ_DEFAULT_PRODUCT_HINTS,
        personal_care_product_hints=PERSONAL_CARE_PRODUCT_HINTS,
    )


def _match_standard(
    row: StandardRowLike,
    traits: set[str],
    matched_products: set[str],
    likely_standards: set[str],
) -> tuple[bool, int, StandardMatchMeta]:
    matched, score, meta = _context_helpers._match_standard(_standard_row(row), traits, matched_products, likely_standards)
    return matched, score, cast(StandardMatchMeta, meta)


def _standard_primary_directive(row: StandardRowLike, traits: set[str]) -> str:
    return _context_helpers._standard_primary_directive(_standard_row(row), traits)


def _derive_directives(traits: set[str], forced_directives: list[str] | None = None) -> list[str]:
    directives: list[str] = []
    is_radio = "radio" in traits

    if not is_radio:
        appliance_lvd_signal = bool(
            "electrical" in traits
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

        if "electrical" in traits:
            directives.append("EMC")

    if is_radio:
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

    return [directive for index, directive in enumerate(directives) if directive not in directives[:index]]


def _apply_post_selection_gates_v1(
    selected: Sequence[StandardRowLike],
    traits: set[str],
    matched_products: set[str],
    diagnostics: list[str],
    allowed_directives: set[str],
    product_type: str | None = None,
    confirmed_traits: set[str] | None = None,
    description: str = "",
) -> list[StandardCatalogRow]:
    kept: list[StandardCatalogRow] = []
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
    prefer_62233 = bool(
        scope_route != "av_ict"
        and "electrical" in traits
        and "consumer" in traits
        and "household" in traits
        and ({"heating", "motorized", "mains_powered", "mains_power_likely"} & traits)
        and "wearable" not in traits
        and "handheld" not in traits
        and "body_worn_or_applied" not in traits
    )
    prefer_62311 = bool(
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

    for selected_item in selected:
        item = _standard_row(selected_item)
        code = item.code
        route = str(item.get("directive") or "OTHER")

        if route not in allowed_directives and route != "OTHER":
            diagnostics.append(f"gate=drop_{code}:directive_{route}_not_selected")
            continue

        if code == "Charger / external PSU review":
            if not has_external_psu:
                diagnostics.append("gate=drop_external_psu_review:no_external_psu_signal")
                continue
            item = item.model_copy(update={"directive": "LVD", "legislation_key": "LVD"})
        elif code == "EN 50563":
            if not has_external_psu:
                diagnostics.append("gate=drop_EN50563:no_external_psu_signal")
                continue
            item = item.model_copy(update={"directive": "ECO", "legislation_key": "ECO"})

        if code == "EN 62368-1" and scope_route == "appliance":
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
            directive = "RED" if "radio" in traits else "LVD"
            item = item.model_copy(update={"directive": directive, "legislation_key": directive})

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

    household_part2_selected = any(item.code.startswith("EN 60335-2-") and item.item_type == "standard" for item in kept)
    if household_part2_selected:
        promoted: list[StandardCatalogRow] = []
        for item in kept:
            if item.code != "EN 60335-1" or item.item_type != "review":
                promoted.append(item)
                continue
            reason = item.get("reason")
            if isinstance(reason, str):
                reason = reason.replace(
                    ". some routing traits are inferred from product context and still need confirmation",
                    "",
                )
            promoted.append(item.model_copy(update={"item_type": "standard", "fact_basis": "confirmed", "reason": reason}))
            diagnostics.append("gate=promote_EN60335-1:paired_with_household_part2")
        kept = promoted

    codes = {item.code for item in kept}
    if "EN 62233" in codes and "EN 62311" in codes and prefer_62233:
        kept = [item for item in kept if item.code != "EN 62311"]
        diagnostics.append("gate=prune_EN62311_after_pairing")
    elif "EN 62233" in codes and "EN 62311" in codes and prefer_62311:
        kept = [item for item in kept if item.code != "EN 62233"]
        diagnostics.append("gate=prune_EN62233_after_pairing")

    codes = {item.code for item in kept}
    if (
        "Battery safety review" in codes
        and "EN 62133-2" in codes
        and scope_route == "av_ict"
        and not ({"wearable", "handheld", "body_worn_or_applied", "replaceable_battery"} & traits)
    ):
        kept = [item for item in kept if item.code != "Battery safety review"]
        diagnostics.append("gate=prune_Battery_safety_review:covered_by_EN62133-2")

    return kept


def _standard_context(
    traits: set[str],
    matched_products: set[str],
    product_type: str | None,
    confirmed_traits: set[str] | None,
    description: str,
    route_plan: RoutePlan | None = None,
) -> SelectionContext:
    return _context_helpers._standard_context(
        traits,
        matched_products,
        product_type,
        confirmed_traits,
        description,
        route_plan,
        scope_route=lambda scope_traits, scope_products, scope_product_type, scope_confirmed_traits, scope_route_family: _scope_route(
            scope_traits,
            scope_products,
            scope_product_type,
            scope_confirmed_traits,
            scope_route_family,
        ),
        has_any=_has_any,
        laser_source_patterns=LASER_SOURCE_PATTERNS,
        photobiological_source_patterns=PHOTOBIOLOGICAL_SOURCE_PATTERNS,
        personal_care_product_hints=PERSONAL_CARE_PRODUCT_HINTS,
    )


def _apply_post_selection_gates(
    selected: Sequence[StandardRowLike],
    traits: set[str],
    matched_products: set[str],
    diagnostics: list[str],
    allowed_directives: set[str],
    product_type: str | None = None,
    confirmed_traits: set[str] | None = None,
    description: str = "",
    product_genres: set[str] | None = None,
    preferred_standard_codes: set[str] | None = None,
) -> list[StandardCatalogRow]:
    context = _standard_context(traits, matched_products, product_type, confirmed_traits, description)
    diagnostics.append("scope_route=" + context.scope_route)
    if context.scope_reasons:
        diagnostics.append("scope_route_reasons=" + ";".join(context.scope_reasons))
    diagnostics.append("standard_context_tags=" + ",".join(sorted(context.context_tags)))

    kept: list[StandardCatalogRow] = []
    for selected_item in selected:
        gated_item = _gate_helpers._gate_per_item(
            _standard_row(selected_item),
            context,
            traits,
            allowed_directives,
            product_genres,
            preferred_standard_codes,
            diagnostics,
            keep_preferred_62368_review_in_appliance_scope=_keep_preferred_62368_review_in_appliance_scope,
        )
        if gated_item is not None:
            kept.append(gated_item)

    kept = _gate_helpers._promote_household_part1(kept, diagnostics)
    kept = _gate_helpers._prune_emf_duplicate(kept, context, diagnostics)
    kept = _gate_helpers._prune_battery_safety_review(kept, context, traits, diagnostics)
    return kept


def _route_condition_hint(row: LegislationRowLike | StandardRowLike) -> str | None:
    if isinstance(row, LegislationCatalogRow):
        return _legislation_helpers._route_condition_hint(row)
    return _legislation_helpers._route_condition_hint(_standard_row(row))


def _legislation_applicability_state(row: LegislationRowLike) -> str:
    return _legislation_helpers._legislation_applicability_state(_legislation_row(row))


def _standard_applicability_state(row: StandardRowLike, timing_status: str) -> str:
    return _legislation_helpers._standard_applicability_state(_standard_row(row), timing_status)


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
    items = [
        LegislationItem(
            code=row.code,
            title=row.title,
            family=row.family or row.title,
            legal_form=row.legal_form,
            priority=row.priority,
            applicability=row.applicability,
            directive_key=row.directive_key,
            bucket=row.bucket,
            timing_status=cast(TimingStatus, str(row.get("timing_status") or "current")),
            reason=row.get("reason"),
            triggers=list(row.triggers),
            doc_impacts=list(row.doc_impacts),
            notes=row.notes,
            applicable_from=row.applicable_from,
            applicable_until=row.applicable_until,
            replaced_by=row.replaced_by,
            evidence_strength=cast(FactBasis, str(row.get("evidence_strength") or "confirmed")),
            is_forced=bool(row.get("is_forced")),
            jurisdiction="EU",
            applicability_state=_legislation_applicability_state(row),
            applicability_hint=_route_condition_hint(row),
        )
        for row in picked_rows
    ]
    return items, _legislation_sections_from_items(items), _directive_keys(items)


def _legislation_sections_from_items(items: list[LegislationItem]) -> list[LegislationSection]:
    return _legislation_helpers._legislation_sections_from_items(items)


def _filter_legislation_items_for_route_plan(items: list[LegislationItem], route_plan: RoutePlan) -> list[LegislationItem]:
    return _legislation_helpers._filter_legislation_items_for_route_plan(
        items,
        route_plan.primary_directive,
        PRIMARY_DIRECTIVE_EXCLUSIONS,
    )


def _route_context_summary(
    context: SelectionContext | Mapping[str, Any],
    known_facts: list[KnownFactItem],
    overlay_routes: list[str] | None = None,
) -> RouteContext:
    return _context_helpers._route_context_summary(SelectionContext.from_mapping(context), known_facts, overlay_routes)


def _text_evidenced_traits(state_map: NormalizedTraitStateMap) -> set[str]:
    return _context_helpers._text_evidenced_traits(
        cast(Mapping[str, dict[str, list[str]]], state_map),
        TEXT_EVIDENCE_STATES,
        RADIO_ROUTE_TRAITS,
    )


def _route_selection_traits(
    traits: set[str],
    confirmed_traits: set[str],
    state_map: NormalizedTraitStateMap,
    product_genres: set[str],
) -> tuple[set[str], list[str]]:
    return _context_helpers._route_selection_traits(
        traits,
        confirmed_traits,
        cast(Mapping[str, dict[str, list[str]]], state_map),
        product_genres,
        default_connected_route_genres=DEFAULT_CONNECTED_ROUTE_GENRES,
        sensitive_route_traits=SENSITIVE_ROUTE_TRAITS,
        text_evidence_states=TEXT_EVIDENCE_STATES,
        radio_route_traits=RADIO_ROUTE_TRAITS,
    )


def _prepare_analysis(
    description: str,
    category: str,
    depth: AnalysisDepth,
) -> PreparedAnalysis:
    from .result_builder import _normalize_trait_state_map

    normalized_description = normalize(f"{category} {description}")
    traits_snapshot = _classifier_snapshot(extract_traits(description=description, category=category))
    diagnostics = list(traits_snapshot.diagnostics)
    matched_products = set(traits_snapshot.matched_products)
    routing_matched_products = set(traits_snapshot.routing_matched_products)
    product_genres = set(traits_snapshot.product_genres)
    product_type = traits_snapshot.product_type
    product_match_stage = _product_match_stage(traits_snapshot.product_match_stage)
    product_match_confidence = _confidence_level(traits_snapshot.product_match_confidence, default="low")
    routing_product_type = product_type if (product_type and product_match_confidence != "low") else None
    likely_standards = _collect_preferred_standard_codes(traits_snapshot)

    base_trait_set = set(traits_snapshot.all_traits)
    trait_set = set(base_trait_set)
    confirmed_traits = set(traits_snapshot.confirmed_traits)
    functional_classes = set(traits_snapshot.functional_classes)
    trait_set, confirmed_engine_traits, extra_diag = _derive_engine_traits(description, trait_set, routing_matched_products)
    confirmed_traits.update(confirmed_engine_traits)
    diagnostics.extend(extra_diag)

    raw_state_map = _normalize_trait_state_map(traits_snapshot.trait_state_map)
    for trait in sorted(trait_set - base_trait_set):
        raw_state_map["engine_derived"].setdefault(trait, []).append("engine:derived")

    route_traits, suppressed_traits = _route_selection_traits(trait_set, confirmed_traits, raw_state_map, product_genres)
    if suppressed_traits:
        diagnostics.append("route_trait_suppressed=" + ",".join(suppressed_traits))

    route_plan = _build_route_plan(
        traits_data=traits_snapshot,
        traits=route_traits,
        matched_products=routing_matched_products or (matched_products if product_match_confidence != "low" else set()),
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
        traits_data=traits_snapshot,
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
        forced_directives = sorted(set(forced_directives) | inferred_directive_hints)
        legislation_items, legislation_sections, detected_directives = _build_legislation_sections(
            traits=prepared.route_traits,
            functional_classes=prepared.functional_classes,
            product_type=prepared.routing_product_type,
            matched_products=prepared.routing_matched_products,
            product_genres=prepared.product_genres,
            confirmed_traits=prepared.confirmed_traits,
            forced_directives=forced_directives,
        )

    legislation_items = _filter_legislation_items_for_route_plan(legislation_items, prepared.route_plan)
    full_directives_for_standards = set(_directive_keys(legislation_items))
    if "radio" in prepared.route_traits:
        full_directives_for_standards.update({"LVD", "EMC"})
        legislation_items = _remove_standalone_lvd_emc_for_radio(legislation_items)

    legislation_items = _attach_red_sub_articles(legislation_items, prepared.route_traits)
    legislation_sections = _legislation_sections_from_items(legislation_items)
    detected_directives = _directive_keys(legislation_items)
    return LegislationSelection(
        items=legislation_items,
        sections=legislation_sections,
        detected_directives=detected_directives,
        forced_directives=forced_directives,
        allowed_directives=full_directives_for_standards,
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
    "route_family_scope_map",
    "route_family_primary_directive_map",
    "RoutePlan",
    "StandardsSelection",
    "_analysis_depth",
    "_apply_post_selection_gates_v1",
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
    "_family_from_standard_code",
    "_filter_legislation_items_for_route_plan",
    "_has_any",
    "_has_small_avict_lvd_power_signal",
    "_has_wireless_fact_signal",
    "_infer_forced_directives",
    "_keep_preferred_62368_review_in_appliance_scope",
    "_legislation_applicability_state",
    "_legislation_sections_from_items",
    "_match_standard",
    "_normalized_standard_codes",
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
