from __future__ import annotations

import re
from collections.abc import Callable, Mapping
from typing import Any, TypedDict

from app.domain.catalog_types import StandardCatalogRow
from app.domain.models import KnownFactItem, RouteContext
from app.services.classifier import normalize
from app.services.standards_engine.contracts import SelectionContext

from .routing_models import RoutePlan


class StandardMatchMeta(TypedDict):
    matched_traits_all: list[str]
    matched_traits_any: list[str]
    missing_required_traits: list[str]
    excluded_by_traits: list[str]
    product_match_type: str | None


def _keep_preferred_62368_review_in_appliance_scope(
    item: StandardCatalogRow,
    product_genres: set[str] | None,
    preferred_standard_codes: set[str] | None,
    small_smart_62368_genres: set[str],
) -> bool:
    if item.code != "EN 62368-1":
        return False
    if str(item.get("item_type") or "standard") != "review":
        return False
    preferred_standard_codes = preferred_standard_codes or set()
    product_genres = product_genres or set()
    return "EN 62368-1" in preferred_standard_codes and bool(product_genres & small_smart_62368_genres)


def _has_small_avict_lvd_power_signal(
    traits: set[str],
    matched_products: set[str],
    product_type: str | None,
    av_ict_product_hints: set[str],
    wifi_5ghz_default_product_hints: set[str],
) -> bool:
    if "electrical" not in traits or "av_ict" not in traits:
        return False
    avict_product_hit = bool(matched_products & av_ict_product_hints) or (product_type in av_ict_product_hints if product_type else False)
    power_signal = bool({"usb_powered", "external_psu", "poe_powered", "mains_powered", "mains_power_likely"} & traits)
    compact_avict_signal = bool(
        {"wearable", "body_worn_or_applied", "camera", "display", "microphone", "data_storage", "fixed_installation"} & traits
    )
    return power_signal or avict_product_hit or compact_avict_signal or bool(matched_products & wifi_5ghz_default_product_hints)


def _infer_forced_directives(
    traits: set[str],
    matched_products: set[str],
    product_type: str | None,
    confirmed_traits: set[str],
    preferred_standard_codes: set[str] | None,
    *,
    scope_route: Callable[[set[str], set[str], str | None, set[str]], tuple[str, list[str]]],
    av_ict_product_hints: set[str],
    personal_care_product_hints: set[str],
    wifi_5ghz_default_product_hints: set[str],
) -> set[str]:
    if "radio" in traits:
        return set()

    preferred_standard_codes = preferred_standard_codes or set()
    normalized_codes = {
        str(code or "").upper().replace("IEC", "EN").replace("  ", " ").strip()
        for code in preferred_standard_codes
        if str(code or "").strip()
    }

    inferred: set[str] = set()
    scoped_route, _ = scope_route(traits, matched_products, product_type, confirmed_traits)
    has_household_safety_preference = any(code.startswith("EN 60335-") for code in normalized_codes)
    has_avict_safety_preference = any(code.startswith("EN 62368-1") for code in normalized_codes)
    has_lvd_voltage_signal = bool({"mains_powered", "mains_power_likely"} & traits)
    has_small_avict_lvd_signal = _has_small_avict_lvd_power_signal(
        traits,
        matched_products,
        product_type,
        av_ict_product_hints,
        wifi_5ghz_default_product_hints,
    )

    if "electrical" in traits and (has_lvd_voltage_signal or has_small_avict_lvd_signal) and (
        has_household_safety_preference
        or has_avict_safety_preference
        or scoped_route in {"appliance", "av_ict"}
        or bool(matched_products & (av_ict_product_hints | personal_care_product_hints | wifi_5ghz_default_product_hints))
    ):
        inferred.add("LVD")

    return inferred


def _derive_engine_traits(
    description: str,
    traits: set[str],
    matched_products: set[str],
    *,
    has_any: Callable[[str, list[str]], bool],
    power_external_negation_patterns: list[str],
    power_external_patterns: list[str],
    power_internal_patterns: list[str],
    wearable_patterns: list[str],
    handheld_patterns: list[str],
    close_proximity_patterns: list[str],
    wifi_5ghz_explicit_patterns: list[str],
    wifi_24_only_patterns: list[str],
    av_ict_product_hints: set[str],
    wifi_5ghz_default_product_hints: set[str],
    personal_care_product_hints: set[str],
) -> tuple[set[str], set[str], list[str]]:
    text = normalize(description)
    diagnostics: list[str] = []
    derived = set(traits)
    confirmed: set[str] = set()

    if has_any(text, power_external_negation_patterns):
        derived.discard("external_psu")
        derived.add("internal_power_supply")
        confirmed.add("internal_power_supply")
        diagnostics.append("engine_trait=internal_power_supply")
    elif has_any(text, power_external_patterns):
        derived.add("external_psu")
        confirmed.add("external_psu")
        diagnostics.append("engine_trait=external_psu")
    elif has_any(text, power_internal_patterns):
        derived.add("internal_power_supply")
        confirmed.add("internal_power_supply")
        diagnostics.append("engine_trait=internal_power_supply")

    if has_any(text, wearable_patterns):
        derived.update({"wearable", "body_worn_or_applied"})
        confirmed.update({"wearable", "body_worn_or_applied"})
        diagnostics.append("engine_trait=wearable/body_worn_or_applied")
    if has_any(text, handheld_patterns):
        derived.add("handheld")
        confirmed.add("handheld")
        diagnostics.append("engine_trait=handheld")
    if has_any(text, close_proximity_patterns):
        derived.add("body_worn_or_applied")
        confirmed.add("body_worn_or_applied")
        diagnostics.append("engine_trait=close_proximity")

    if matched_products & personal_care_product_hints:
        derived.add("handheld")
        diagnostics.append("engine_trait=handheld_from_product")

    if has_any(text, wifi_5ghz_explicit_patterns):
        derived.update({"wifi", "wifi_5ghz"})
        confirmed.add("wifi_5ghz")
        diagnostics.append("engine_trait=wifi_5ghz:explicit")
    elif "wifi" in derived and "wifi_5ghz" not in derived and not has_any(text, wifi_24_only_patterns):
        smart_wifi_default = bool(
            matched_products & (av_ict_product_hints | wifi_5ghz_default_product_hints)
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


def _scope_route(
    traits: set[str],
    matched_products: set[str],
    product_type: str | None,
    confirmed_traits: set[str] | None,
    route_family: str | None,
    *,
    route_product_row: Callable[[str | None, set[str] | None], Any],
    route_scope_from_family: Callable[[str | None], str | None],
    appliance_primary_traits: set[str],
    av_ict_product_hints: set[str],
    av_ict_supporting_traits: set[str],
) -> tuple[str, list[str]]:
    confirmed_traits = confirmed_traits or set()
    reasons: list[str] = []

    scoped_family = route_family
    if not scoped_family:
        route_row = route_product_row(product_type, matched_products)
        scoped_family = route_row.route_family if route_row else None
    family_scope = route_scope_from_family(scoped_family)
    if family_scope:
        reasons.append(f"primary_route_family={scoped_family}")
        return family_scope, reasons

    appliance_signals = set(appliance_primary_traits) & traits
    av_ict_signals = {"av_ict"} & traits

    if matched_products & av_ict_product_hints:
        reasons.append("matched_av_ict_product")
        av_ict_signals.add("av_ict")
    if product_type in av_ict_product_hints:
        reasons.append(f"primary_product={product_type}")
        av_ict_signals.add("av_ict")

    if not av_ict_signals and (av_ict_supporting_traits & confirmed_traits) and not appliance_signals:
        reasons.append("confirmed_av_ict_signals")
        av_ict_signals.add("av_ict")

    confirmed_appliance_signals = appliance_signals & confirmed_traits
    confirmed_av_ict_signals = av_ict_signals & confirmed_traits
    has_product_scope_anchor = bool(matched_products & av_ict_product_hints) or bool(product_type and product_type in av_ict_product_hints)

    if (appliance_signals or av_ict_signals) and not confirmed_appliance_signals and not confirmed_av_ict_signals and not has_product_scope_anchor:
        reasons.append("deferred_inferred_only_scope")
        return "generic", reasons

    if appliance_signals and not av_ict_signals:
        reasons.append("appliance_primary_traits=" + ",".join(sorted(appliance_signals)))
        return "appliance", reasons
    if av_ict_signals and not appliance_signals:
        reasons.append("av_ict_primary")
        return "av_ict", reasons
    if av_ict_signals and appliance_signals:
        reasons.append("convergent_product_boundary")
        if product_type in av_ict_product_hints:
            reasons.append("resolved_by_primary_product=av_ict")
            return "av_ict", reasons
        if product_type and product_type not in av_ict_product_hints:
            reasons.append("resolved_by_primary_product=appliance")
            return "appliance", reasons
        return "convergent", reasons
    return "generic", reasons


def _standard_primary_directive(row: StandardCatalogRow, traits: set[str]) -> str:
    code = row.code
    directive = row.legislation_key or (row.directives or ["OTHER"])[0]

    if code.startswith("EN 18031-"):
        return "RED_CYBER"
    if code == "EN 62311":
        return "RED" if "radio" in traits else "LVD"
    if directive == "RED" and code.startswith("EN 301 489-"):
        return "RED"
    if "radio" in traits and directive in {"LVD", "EMC"}:
        return "RED"
    return directive or "OTHER"


def _build_context_tags(
    scope_route: str,
    route_plan: RoutePlan,
    traits: set[str],
    has_external_psu: bool,
    has_portable_battery: bool,
    has_laser_source: bool,
    has_photobiological_source: bool,
    prefer_specific_red_emf: bool,
    prefer_62233: bool,
    has_body_contact: bool,
    has_skin_contact: bool,
    has_personal_or_health_data: bool,
    has_connected_radio: bool,
    has_medical_boundary: bool,
) -> set[str]:
    tags: set[str] = {f"scope:{scope_route}"}
    if route_plan.primary_route_family:
        tags.add("primary:" + route_plan.primary_route_family)
    if route_plan.primary_standard_code:
        tags.add("primary_standard:" + route_plan.primary_standard_code)
    if has_external_psu:
        tags.add("power:external_psu")
    if has_portable_battery:
        tags.add("power:portable_battery")
    if has_laser_source:
        tags.add("optical:laser")
    if has_photobiological_source:
        tags.add("optical:photobio")
    if prefer_specific_red_emf:
        tags.add("exposure:close_proximity")
    if prefer_62233:
        tags.add("exposure:household_emf")
    if has_body_contact:
        tags.add("contact:body")
    if has_skin_contact or has_body_contact:
        tags.add("contact:skin")
    if has_personal_or_health_data:
        tags.add("data:personal_or_health")
    if {"health_related", "biometric"} & traits:
        tags.add("data:health")
    if {"home_security", "surveillance", "access_control", "locking", "camera_surveillance"} & traits:
        tags.add("domain:security")
    if {"local_only", "offline_capable"} & traits:
        tags.add("service:local_only")
    if has_connected_radio:
        tags.add("cyber:connected_radio")
    if has_medical_boundary:
        tags.add("boundary:medical_wellness")
    if "energy_system_boundary" in traits:
        tags.add("boundary:energy_system")
    if "uv_irradiation_boundary" in traits:
        tags.add("boundary:uv_irradiation")
    if "body_treatment_boundary" in traits:
        tags.add("boundary:body_treatment")
    if "industrial_installation_boundary" in traits:
        tags.add("boundary:industrial_installation")
    if "machinery_boundary" in traits:
        tags.add("boundary:machinery")
    if "agricultural_special_use_boundary" in traits:
        tags.add("boundary:agricultural_special_use")
    return tags


def _standard_context(
    traits: set[str],
    matched_products: set[str],
    product_type: str | None,
    confirmed_traits: set[str] | None,
    description: str,
    route_plan: RoutePlan | None,
    *,
    scope_route: Callable[[set[str], set[str], str | None, set[str] | None, str | None], tuple[str, list[str]]],
    has_any: Callable[[str, list[str]], bool],
    laser_source_patterns: list[str],
    photobiological_source_patterns: list[str],
    personal_care_product_hints: set[str],
) -> SelectionContext:
    route_plan = route_plan or RoutePlan()
    scope_value, scope_reasons = scope_route(
        traits,
        matched_products,
        product_type,
        confirmed_traits,
        route_plan.primary_route_family,
    )
    if route_plan.reason:
        scope_reasons = [route_plan.reason, *scope_reasons]

    text = normalize(description)
    has_external_psu = "external_psu" in traits or bool(
        matched_products & {"battery_charger", "industrial_charger", "usb_wall_charger", "external_power_supply", "travel_adapter_charger"}
    )
    has_portable_battery = bool({"battery_powered", "backup_battery"} & traits)
    has_laser_source = "laser" in traits or has_any(text, laser_source_patterns)
    has_photobiological_source = (
        has_laser_source
        or bool(
            {"lighting", "luminaire", "optical_emission", "uv_emitting", "infrared_emitting", "photobiological_relevance"} & traits
        )
        or bool(matched_products & {"projector", "heating_lamp", "smart_led_bulb", "smart_desk_lamp", "smart_indoor_garden"})
        or (product_type in {"projector", "heating_lamp", "smart_led_bulb", "smart_desk_lamp", "smart_indoor_garden"} if product_type else False)
        or has_any(text, photobiological_source_patterns)
    )
    has_body_contact = bool({"wearable", "body_worn_or_applied", "personal_care", "body_contact", "oral_contact"} & traits) or bool(
        re.search(r"\b(?:body contact|skin contact|body worn|on body|on skin|chest strap|sensor patch|wearable patch|armband)\b", text)
    )
    has_skin_contact = bool(re.search(r"\b(?:skin contact|on skin|chest strap|sensor patch|wearable patch)\b", text))
    has_personal_or_health_data = bool(
        {"personal_data_likely", "health_related", "health_data", "biometric", "account", "camera", "microphone", "location"} & traits
    )
    has_connected_radio = bool(
        "radio" in traits and ({"wifi", "bluetooth", "cellular", "app_control", "cloud", "ota", "internet", "account", "authentication"} & traits)
    )
    has_medical_boundary = bool({"possible_medical_boundary", "medical_context", "medical_claims"} & traits)
    prefer_specific_red_emf = bool(
        "radio" in traits and ({"cellular", "wearable", "handheld", "body_worn_or_applied", "close_proximity_emf"} & traits)
    )
    prefer_62233 = bool(
        scope_value != "av_ict"
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
            scope_value == "av_ict"
            or "wearable" in traits
            or "handheld" in traits
            or "body_worn_or_applied" in traits
            or ("radio" in traits and "consumer" not in traits)
            or bool(matched_products & personal_care_product_hints)
        )
    )
    context_tags = _build_context_tags(
        scope_value,
        route_plan,
        traits,
        has_external_psu,
        has_portable_battery,
        has_laser_source,
        has_photobiological_source,
        prefer_specific_red_emf,
        prefer_62233,
        has_body_contact,
        has_skin_contact,
        has_personal_or_health_data,
        has_connected_radio,
        has_medical_boundary,
    )
    return SelectionContext(
        scope_route=scope_value,
        scope_reasons=scope_reasons,
        text=text,
        context_tags=context_tags,
        primary_route_family=route_plan.primary_route_family,
        primary_standard_code=route_plan.primary_standard_code,
        primary_route_reason=route_plan.reason,
        route_confidence=route_plan.confidence,
        has_external_psu=has_external_psu,
        has_portable_battery=has_portable_battery,
        has_laser_source=has_laser_source,
        has_photobiological_source=has_photobiological_source,
        has_body_contact=has_body_contact,
        has_personal_or_health_data=has_personal_or_health_data,
        has_connected_radio=has_connected_radio,
        has_medical_boundary=has_medical_boundary,
        prefer_specific_red_emf=prefer_specific_red_emf,
        prefer_62233=prefer_62233,
        prefer_62311=prefer_62311,
    )


def _route_context_summary(context: SelectionContext, known_facts: list[KnownFactItem], overlay_routes: list[str] | None = None) -> RouteContext:
    return RouteContext(
        scope_route=context.scope_route,
        scope_reasons=list(context.scope_reasons),
        context_tags=sorted(context.context_tags),
        known_fact_keys=[item.key for item in known_facts],
        jurisdiction="EU",
        route_trigger_reasons=list(context.scope_reasons),
        primary_route_family=context.primary_route_family,
        primary_route_standard_code=context.primary_standard_code,
        primary_route_reason=context.primary_route_reason,
        overlay_routes=list(overlay_routes or []),
        route_confidence=context.route_confidence,
    )


def _text_evidenced_traits(
    state_map: Mapping[str, dict[str, list[str]]],
    text_evidence_states: tuple[str, str],
    radio_route_traits: set[str],
) -> set[str]:
    evidenced: set[str] = set()
    for state in text_evidence_states:
        evidenced.update(state_map.get(state, {}).keys())

    if evidenced & (radio_route_traits - {"radio"}):
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
    state_map: Mapping[str, dict[str, list[str]]],
    product_genres: set[str],
    *,
    default_connected_route_genres: set[str],
    sensitive_route_traits: set[str],
    text_evidence_states: tuple[str, str],
    radio_route_traits: set[str],
) -> tuple[set[str], list[str]]:
    if product_genres & default_connected_route_genres:
        return set(traits), []

    route_traits = set(traits)
    backed_traits = confirmed_traits | _text_evidenced_traits(state_map, text_evidence_states, radio_route_traits)

    suppressed = sorted((route_traits & sensitive_route_traits) - backed_traits)
    route_traits.difference_update(suppressed)

    if not (route_traits & (radio_route_traits - {"radio"})):
        route_traits.discard("radio")

    return route_traits, suppressed


def _match_standard(
    row: StandardCatalogRow,
    traits: set[str],
    matched_products: set[str],
    likely_standards: set[str],
) -> tuple[bool, int, StandardMatchMeta]:
    applies_products = set(row.applies_if_products)
    exclude_products = set(row.exclude_if_products)
    requires_all = set(row.applies_if_all)
    requires_any = set(row.applies_if_any)
    excludes = set(row.exclude_if)

    meta: StandardMatchMeta = {
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
    if row.code in likely_standards or row.standard_family in likely_standards:
        score += 28
        meta["product_match_type"] = meta["product_match_type"] or "preferred_product"
    if row.item_type == "review":
        score -= 8
    return True, score, meta


__all__ = [
    "_derive_engine_traits",
    "_has_small_avict_lvd_power_signal",
    "_infer_forced_directives",
    "_keep_preferred_62368_review_in_appliance_scope",
    "_match_standard",
    "_route_context_summary",
    "_route_selection_traits",
    "_scope_route",
    "_standard_context",
    "_standard_primary_directive",
    "_text_evidenced_traits",
]
