from __future__ import annotations

import re
from typing import Literal

from app.domain.models import KnownFactItem, MissingInformationItem, ProductMatchStage, QuickAddItem
from app.services.classifier import normalize

from .routing import (
    APPLIANCE_PRIMARY_TRAITS,
    PERSONAL_CARE_PRODUCT_HINTS,
    POWER_EXTERNAL_NEGATION_PATTERNS,
    RoutePlan,
    _has_any,
    _has_wireless_fact_signal,
)


MissingImportance = Literal["high", "medium", "low"]


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


__all__ = [
    "MissingImportance",
    "_build_known_facts",
    "_build_quick_adds",
    "_missing_information",
    "_top_actions_from_missing",
]
