from __future__ import annotations

import re
from typing import Callable

from app.domain.models import ProductMatchStage

from .facts_details import (
    _has_access_model_detail,
    _has_battery_capacity_detail,
    _has_battery_chemistry_detail,
    _has_battery_pack_format_detail,
    _has_body_contact_material_detail,
    _has_cloud_dependency_detail,
    _has_data_category_detail,
    _has_data_storage_detail,
    _has_installation_detail,
    _has_medical_boundary_resolution,
    _has_pressure_detail,
    _has_radio_band_detail,
    _has_radio_power_detail,
    _has_update_route_detail,
)
from .routing import APPLIANCE_PRIMARY_TRAITS, PERSONAL_CARE_PRODUCT_HINTS, POWER_EXTERNAL_NEGATION_PATTERNS, _has_any


MissingInformationAdd = Callable[..., None]


def _smart_lock_questions(product_type: str | None, traits: set[str], text: str, add: MissingInformationAdd) -> None:
    if product_type != "smart_lock":
        return

    def sa(patterns: list[str]) -> bool:
        return any(bool(re.search(p, text)) for p in patterns)

    if not sa([r"\bindoor\b", r"\boutdoor\b", r"\bweather(?:proof|resistant)\b", r"\bexternal door\b"]):
        add("smart_lock_installation", "Confirm whether the lock is indoor-only or intended for exposed outdoor use.", "medium", ["indoor apartment door", "outdoor gate or exterior door"], ["fixed_installation"], ["LVD", "GPSR"])
    if "biometric" in traits and not sa([r"\blocal only\b", r"\bon device\b", r"\bcloud\b", r"\bremote unlock history\b"]):
        add("smart_lock_biometric_storage", "Confirm whether biometric data is processed locally only or backed up to the cloud.", "high", ["fingerprint templates stored locally only", "biometric data synced to cloud account"], ["biometric", "cloud", "personal_data_likely"], ["GDPR", "RED_CYBER"])
    if not sa([r"\bpanic\b", r"\bemergency exit\b", r"\bescape route\b", r"\bfire exit\b"]):
        add("smart_lock_escape_route", "Confirm whether the lock is used on an emergency-exit, panic, or escape-route door.", "medium", ["standard residential entry door", "panic-exit application"], ["safety_function"], ["GPSR"])
    if ("app_control" in traits or "voice_assistant" in traits) and "radio" not in traits:
        add("smart_lock_actual_radio", "Confirm the actual radio modules present, if any.", "high", ["Wi-Fi", "Bluetooth", "Zigbee", "Z-Wave", "NFC", "no wireless communication"], ["radio", "wifi", "bluetooth", "zigbee", "nfc"], ["RED", "RED_CYBER"])


def _ev_charging_questions(route_family: str | None, product_type: str | None, traits: set[str], text: str, add: MissingInformationAdd) -> None:
    if route_family != "ev_charging" and product_type not in {"ev_charger_home", "portable_ev_charger"}:
        return

    def sa(patterns: list[str]) -> bool:
        return any(bool(re.search(p, text)) for p in patterns)

    if not sa([r"\bmode ?2\b", r"\bmode ?3\b", r"\bmode ?4\b"]):
        add("ev_mode", "Confirm whether the product is mode 2, mode 3, or mode 4 charging equipment.", "high", ["mode 2 portable EVSE", "mode 3 wallbox", "mode 4 DC charger"], ["ev_charging"], ["LVD", "EMC"])
    if not sa([r"\bac charging\b", r"\bdc charging\b", r"\bac\b", r"\bdc\b"]):
        add("ev_ac_dc", "Confirm whether the charging equipment is AC or DC.", "high", ["single-phase AC", "three-phase AC", "DC fast charging"], ["ev_charging"], ["LVD", "EMC"])
    if not sa([r"\bportable\b", r"\bfixed\b", r"\bwallbox\b", r"\bcharging station\b", r"\bwall mount\b"]):
        add("ev_installation_type", "Confirm whether it is a portable EVSE or a fixed charging station.", "high", ["portable mode 2 EVSE", "fixed wallbox charging station"], ["portable", "fixed_installation"], ["LVD", "EMC"])
    if not sa([r"\btype ?1\b", r"\btype ?2\b", r"\bccs\b", r"\bconnector\b", r"\binlet\b", r"\bcoupler\b", r"\bsocket\b"]):
        add("ev_connector_type", "Confirm whether the connector, coupler, or inlet type is relevant.", "medium", ["Type 2 vehicle connector", "CCS interface", "socket-outlet only"], ["vehicle_supply"], ["LVD"])
    if not sa([r"\baccessory\b", r"\bconnector only\b", r"\bcoupler only\b", r"\binlet only\b", r"\boff board\b", r"\boff-board\b"]):
        add("ev_equipment_boundary", "Confirm whether the product is off-board charging equipment or only a connector/accessory.", "high", ["off-board EV charging equipment", "connector-only accessory"], ["ev_charging", "vehicle_supply"], ["LVD", "EMC"])
    if ("app_control" in traits or "ota" in traits or "cloud" in traits) and "radio" not in traits:
        add("ev_actual_radio", "Confirm whether any actual radio modules are present.", "medium", ["Wi-Fi present", "Bluetooth present", "wired control only"], ["radio"], ["RED", "RED_CYBER"])


def _air_purifier_questions(product_type: str | None, text: str, add: MissingInformationAdd) -> None:
    if product_type != "air_purifier":
        return

    def sa(patterns: list[str]) -> bool:
        return any(bool(re.search(p, text)) for p in patterns)

    if not sa([r"\buv ?c\b", r"\bultraviolet\b", r"\bgermicidal\b", r"\bno uv\b"]):
        add("air_purifier_uvc", "Confirm whether the air purifier intentionally emits UV-C or other germicidal radiation.", "high", ["HEPA filter only", "UV-C disinfection lamp included"], ["air_treatment"], ["LVD", "GPSR"])
    if not sa([r"\bportable\b", r"\btabletop\b", r"\broom\b", r"\bhvac\b", r"\bintegrated\b", r"\bduct\b"]):
        add("air_purifier_installation", "Confirm whether it is a portable appliance or an integrated HVAC component.", "medium", ["portable room appliance", "ducted HVAC module"], ["air_treatment"], ["LVD", "GPSR"])


def _lighting_questions(route_family: str | None, product_type: str | None, text: str, add: MissingInformationAdd) -> None:
    if route_family != "lighting_device" and product_type not in {"smart_led_bulb", "smart_desk_lamp"}:
        return

    def sa(patterns: list[str]) -> bool:
        return any(bool(re.search(p, text)) for p in patterns)

    if not sa([r"\bbulb\b", r"\blamp\b", r"\blight source\b", r"\bluminaire\b", r"\bfixture\b", r"\bdesk lamp\b"]):
        add("lighting_form_factor", "Confirm whether the product is a lamp only or a luminaire / fixture.", "medium", ["E27 LED lamp only", "integrated desk-lamp luminaire"], ["lighting"], ["LVD", "ECO"])
    if not sa([r"\bmains\b", r"\bdriver\b", r"\bcontrol gear\b", r"\btransformer\b", r"\busb powered\b"]):
        add("lighting_power_architecture", "Confirm whether the light source is mains-direct or relies on external / integrated control gear.", "medium", ["mains-direct E27 lamp", "external driver or control gear"], ["mains_powered", "electrical"], ["LVD", "ECO"])
    if not sa([r"\bdimmable\b", r"\bnon dimmable\b"]):
        add("lighting_dimming", "Confirm whether the lamp is dimmable.", "low", ["phase-cut dimmable", "non-dimmable"], ["lighting"], ["ECO"])


def _refrigerator_questions(product_type: str | None, text: str, add: MissingInformationAdd) -> None:
    if product_type != "refrigerator_freezer":
        return

    def sa(patterns: list[str]) -> bool:
        return any(bool(re.search(p, text)) for p in patterns)

    if not sa([r"\bhousehold\b", r"\bdomestic\b", r"\bcommercial\b", r"\bprofessional\b"]):
        add("refrigerator_use_class", "Confirm whether the refrigerator is for household/domestic use or commercial use.", "high", ["household fridge-freezer", "commercial upright refrigerator"], ["household", "professional"], ["LVD", "GPSR"])
    if not sa([r"\brefrigerant\b", r"\bsealed system\b", r"\br600a\b", r"\br290\b", r"\bcompressor\b"]):
        add("refrigerator_cooling_system", "Confirm whether the sealed cooling system and refrigerant details are relevant.", "medium", ["sealed system with R600a", "thermoelectric cooler"], ["motorized"], ["LVD", "GPSR"])


def _robot_vacuum_questions(product_type: str | None, text: str, add: MissingInformationAdd) -> None:
    if product_type != "robot_vacuum":
        return

    def sa(patterns: list[str]) -> bool:
        return any(bool(re.search(p, text)) for p in patterns)

    if not sa([r"\bmop\b", r"\bvacuum only\b", r"\bsweep\b"]):
        add("robot_vacuum_function", "Confirm whether the robot performs vacuum-only cleaning or vacuum plus mopping.", "medium", ["vacuum only", "vacuum and mop"], ["cleaning"], ["LVD", "GPSR"])
    if not sa([r"\bdocking station\b", r"\bcharging dock\b", r"\bself empty\b", r"\bbase station\b"]):
        add("robot_vacuum_dock", "Confirm whether a docking station or charger is included.", "low", ["charging dock included", "robot only without dock"], ["battery_powered"], ["BATTERY", "ECO"])


def _life_safety_alarm_questions(route_family: str | None, product_type: str | None, text: str, add: MissingInformationAdd) -> None:
    if route_family != "life_safety_alarm" and product_type != "smart_smoke_co_alarm":
        return

    def sa(patterns: list[str]) -> bool:
        return any(bool(re.search(p, text)) for p in patterns)

    if not sa([r"\bsmoke\b", r"\bco\b", r"\bcarbon monoxide\b", r"\bcombined\b"]):
        add("alarm_detection_type", "Confirm whether the alarm is for smoke, carbon monoxide, or both.", "high", ["smoke alarm only", "CO alarm only", "combined smoke and CO alarm"], ["smoke_detection", "co_detection"], ["LVD", "GPSR"])
    if not sa([r"\bstandalone\b", r"\bdomestic\b", r"\bhousehold\b", r"\bsystem component\b", r"\bpanel\b"]):
        add("alarm_system_boundary", "Confirm whether it is a domestic standalone alarm or a system component.", "high", ["standalone residential alarm", "alarm-system component"], ["safety_function"], ["LVD", "GPSR"])


def _machinery_tool_questions(route_family: str | None, product_type: str | None, traits: set[str], text: str, add: MissingInformationAdd) -> None:
    if route_family != "machinery_power_tool" and product_type not in {"corded_power_drill", "cordless_power_drill", "industrial_power_tool"}:
        return

    def sa(patterns: list[str]) -> bool:
        return any(bool(re.search(p, text)) for p in patterns)

    if ("app_control" in traits or "ota" in traits) and "radio" not in traits:
        add("tool_actual_radio", "Confirm whether the tool has any actual radio functionality.", "high", ["Bluetooth module present", "no wireless communication"], ["radio"], ["RED", "RED_CYBER"])
    if not sa([r"\bhandheld\b", r"\bhand held\b", r"\btransportable\b", r"\bbench\b", r"\bstationary\b"]):
        add("tool_form_factor", "Confirm whether the tool is handheld or transportable/stationary.", "medium", ["handheld drill", "transportable bench tool"], ["handheld", "portable"], ["MD"])
    if not sa([r"\bconsumer\b", r"\bdomestic\b", r"\bprofessional\b", r"\bindustrial\b"]):
        add("tool_use_class", "Confirm whether the tool is a consumer tool or industrial/professional machinery.", "medium", ["consumer cordless drill", "industrial/professional power tool"], ["consumer", "professional", "industrial"], ["MD", "GPSR"])


def _toy_questions(traits: set[str], text: str, add: MissingInformationAdd) -> None:
    if "child_targeted" not in traits or "toy" in traits:
        return

    def sa(patterns: list[str]) -> bool:
        return any(bool(re.search(p, text)) for p in patterns)

    if not sa([r"\bnot intended for play\b", r"\bdesigned for play\b", r"\btoy\b", r"\bplay\b"]):
        add("toy_play_intent", "Confirm whether the product is designed or intended for play by children under 14.", "high", ["not intended for play", "marketed as a toy for children under 14"], ["toy", "child_targeted"], ["TOY", "GPSR"])
    if not sa([r"\bmain(?:ly)? for play\b", r"\bplay(?:ful)? function\b", r"\beducational aid\b", r"\bsafety product\b"]):
        add("toy_primary_function", "Confirm whether play is the main intended function.", "high", ["primary function is play", "primary function is monitoring or safety"], ["toy"], ["TOY", "GPSR"])


def _power_source_questions(traits: set[str], product_match_stage: ProductMatchStage, tool_signal: bool, text: str, add: MissingInformationAdd) -> None:
    passive_accessory_signal = bool(
        re.search(r"\b(?:passive|dongle|adapter cable|cable adapter|connector only|tethered cable|usb ?c to hdmi|no electronics)\b", text)
    )
    if product_match_stage != "subtype" and tool_signal:
        add("tool_type", "Specify the exact equipment type, such as drill, saw, grinder, sander, or compressor.", "high", ["corded drill", "circular saw", "portable air compressor"], ["motorized"], ["MD", "MACH_REG", "LVD", "BATTERY"], ["Confirm the exact equipment family before relying on machinery or tool routes."])
    if passive_accessory_signal:
        return
    if "mains_powered" not in traits and "mains_power_likely" not in traits and "battery_powered" not in traits:
        add("power_source", "Confirm whether the product is mains-powered, battery-powered, or both.", "high", ["230 V mains powered", "rechargeable lithium battery", "mains plus battery backup"], ["mains_powered", "battery_powered"], ["LVD", "BATTERY", "ECO"], ["Confirm the power architecture and whether the product is mains-powered, battery-powered, or both."])


def _radio_questions(traits: set[str], matched_products: set[str], text: str, radio_band_known: bool, radio_power_known: bool, add: MissingInformationAdd) -> None:
    if "radio" not in traits:
        return

    if not any(t in traits for t in ["wifi", "bluetooth", "cellular", "zigbee", "thread", "nfc"]):
        add("radio_technology", "Confirm the actual radio technology.", "high", ["Wi-Fi radio", "Bluetooth LE radio", "NFC radio"], ["radio"], ["RED", "RED_CYBER"], ["Confirm the actual radio technology used by the product."])
    if not radio_band_known or not radio_power_known:
        add("radio_rf_detail", "Confirm the radio bands and declared output power.", "medium", ["Bluetooth LE 2.4 GHz", "Wi-Fi 2.4/5 GHz", "maximum output power 10 dBm"], ["radio", "wifi", "bluetooth", "cellular", "nfc"], ["RED", "RED_CYBER"], ["Confirm radio bands, channel families, and declared output power / EIRP."])
    if "wifi" in traits and "wifi_5ghz" not in traits:
        add("wifi_band", "Confirm whether Wi-Fi is 2.4 GHz only or also 5 GHz.", "medium", ["2.4 GHz only", "dual-band 2.4/5 GHz"], ["wifi", "wifi_5ghz"], ["RED"], ["Confirm whether Wi-Fi is limited to 2.4 GHz or also uses 5 GHz / 6 GHz bands."])
    if not ({"wearable", "handheld", "body_worn_or_applied"} & traits) and bool(matched_products & PERSONAL_CARE_PRODUCT_HINTS):
        add("emf_use_position", "Confirm whether the radio function is used close to the body or only at separation distance.", "medium", ["body-worn use", "handheld close to face", "countertop use only"], ["wearable", "handheld", "body_worn_or_applied"], ["RED"], ["Confirm whether the radio is used on-body, handheld near the face, or only at separation distance."])
    if ({"portable", "battery_powered", "cellular"} & traits or bool(matched_products & PERSONAL_CARE_PRODUCT_HINTS)) and not ({"handheld", "wearable", "body_worn_or_applied"} & traits):
        add("rf_exposure_form_factor", "Confirm whether the radio product is handheld, body-worn, wearable, or used only with separation distance.", "medium", ["handheld use", "body-worn wearable use", "desktop use with separation distance"], ["handheld", "wearable", "body_worn_or_applied"], ["RED"], ["Confirm the RF exposure form factor used in normal operation."])


def _external_psu_question(traits: set[str], text: str, add: MissingInformationAdd) -> None:
    if ({"usb_powered", "external_psu"} & traits or "adapter" in text) and "external_psu" not in traits and not _has_any(text, POWER_EXTERNAL_NEGATION_PATTERNS):
        add("external_psu", "Confirm whether an external adapter or charger is supplied with the product.", "high", ["external AC/DC adapter included", "USB-C PD power adapter included", "internal PSU only"], ["external_psu"], ["LVD", "ECO"], ["Confirm whether the shipped product includes an external PSU, adapter, dock, or charger."])


def _battery_questions(battery_signal: bool, text: str, battery_pack_detail_known: bool, add: MissingInformationAdd) -> None:
    if not battery_signal:
        return

    if not _has_battery_chemistry_detail(text):
        add("battery_chemistry", "Confirm the battery chemistry or cell type.", "high", ["lithium-ion pack", "LiFePO4 pack", "NiMH cells", "sealed lead-acid battery"], ["battery_powered"], ["BATTERY", "WEEE", "GPSR"], ["Confirm the battery chemistry or cell type used in the product."])
    if not _has_battery_capacity_detail(text):
        add("battery_capacity", "Confirm battery voltage and capacity or energy rating.", "medium", ["18 V 5 Ah pack", "36 V 4 Ah battery", "54 Wh integrated battery"], ["battery_powered"], ["BATTERY", "RED"], ["Confirm nominal voltage and capacity / energy rating for the battery pack."])
    if not battery_pack_detail_known:
        add("battery_pack_format", "Confirm whether the battery is integrated, removable, or supplied as a separate pack.", "medium", ["integrated battery", "removable battery pack", "tool sold without battery pack"], ["battery_powered"], ["BATTERY", "WEEE"], ["Confirm battery chemistry and removability, including whether the pack is integrated or user-removable."])


def _smart_connectivity_questions(
    smart_signal: bool,
    traits: set[str],
    text: str,
    cloud_detail_known: bool,
    medical_boundary_signal: bool,
    access_detail_known: bool,
    update_detail_known: bool,
    health_data_signal: bool,
    data_category_known: bool,
    add: MissingInformationAdd,
) -> None:
    data_handling_signal = bool(smart_signal or health_data_signal or {"personal_data_likely", "location", "camera", "microphone"} & traits)
    if smart_signal and not cloud_detail_known:
        add("cloud_dependency", "Confirm whether the smart features require cloud dependency or can operate locally.", "high", ["cloud account required", "local LAN control without cloud dependency", "OTA firmware updates"], ["cloud", "app_control", "ota"], ["RED_CYBER", "CRA", "GDPR"], ["Confirm cloud dependency, account requirement, and whether core functions still work without cloud access."])
    if medical_boundary_signal and not _has_medical_boundary_resolution(text):
        add("medical_wellness_boundary", "Confirm whether the intended purpose stays in wellness scope or crosses into medical diagnosis, treatment, disease monitoring, or patient use.", "high", ["wellness-only activity tracking", "patient monitoring / clinical use", "diagnosis or treatment claim"], ["possible_medical_boundary", "medical_claims", "medical_context"], ["MDR", "GDPR", "GPSR"], ["Confirm the medical / wellness claim boundary and intended-use statement."])
    if data_handling_signal and not _has_data_storage_detail(text):
        add(
            "data_storage_scope",
            "Confirm where the stated personal or health-related data are stored, retained, and sent, including any cloud or app transfer."
            if health_data_signal and data_category_known
            else "Confirm which personal or health-related data categories are processed and whether they are stored locally, in the app, in the cloud, or not retained."
            if health_data_signal
            else "Confirm whether the product stores user, event, diagnostic, or media data locally, in the cloud, or not at all.",
            "high",
            ["heart rate data stored only in mobile app", "cloud account retains activity history", "no personal or health data retained"]
            if health_data_signal and data_category_known
            else ["heart rate and activity data in app account", "cloud video history", "no personal or health data retained"]
            if health_data_signal
            else ["local event log only", "cloud video history", "no user or event data retained"],
            ["data_storage", "personal_data_likely", "health_related"],
            ["GDPR", "CRA", "RED_CYBER"],
            ["Confirm personal / health data categories, storage locations, retention, and cloud transfer scope."],
        )
    if smart_signal and not update_detail_known:
        add("software_update_route", "Confirm whether firmware or software updates are supported, and whether they are OTA, app-driven, local-only, or unavailable.", "high", ["OTA firmware updates", "USB-only local update", "no field updates supported"], ["ota"], ["CRA", "RED_CYBER"], ["Confirm whether updates are OTA, app-driven, local-only, or unavailable in the field."])
    if smart_signal and not access_detail_known:
        add("smart_access_model", "Confirm whether the smart features require an account, pairing flow, local-only control, or permanent cloud access.", "medium", ["local pairing without account", "vendor account required", "LAN-only operation"], ["account", "authentication", "local_only", "cloud"], ["GDPR", "CRA", "RED_CYBER"], ["Confirm whether an account, login, pairing flow, or permanent cloud access is required."])


def _body_contact_questions(body_contact_signal: bool, text: str, add: MissingInformationAdd) -> None:
    if body_contact_signal and not _has_body_contact_material_detail(text):
        add("body_contact_materials", "Confirm the skin-contact surfaces, contact duration, and main body-contact materials.", "medium", ["silicone wrist strap with daily skin contact", "stainless-steel sensor surface", "brief grooming contact only"], ["wearable", "body_worn_or_applied", "personal_care"], ["GPSR", "MDR"], ["Confirm skin-contact materials, contact duration, and whether a biocompatibility review is needed."])


def _equipment_questions(tool_signal: bool, compressor_signal: bool, traits: set[str], text: str, add: MissingInformationAdd) -> None:
    def sa(patterns: list[str]) -> bool:
        return any(bool(re.search(p, text)) for p in patterns)

    if tool_signal and not _has_installation_detail(text):
        add("tool_form_factor", "Confirm whether the equipment is handheld / portable or stationary / fixed-installation.", "medium", ["handheld power tool", "portable workshop unit", "stationary bench machine"], ["handheld", "portable", "fixed_installation"], ["MD", "MACH_REG", "LVD"], ["Confirm whether the equipment is handheld, portable, bench-top, or fixed-installation."])
    if compressor_signal and not _has_pressure_detail(text):
        add("pressure_rating", "Confirm the compressor maximum working pressure and receiver volume.", "high", ["8 bar with 24 L receiver", "10 bar oil-free compressor", "16 bar line pressure"], ["pressure"], ["MD", "MACH_REG"], ["Confirm the maximum working pressure and receiver volume."])
    if compressor_signal and not re.search(r"\b(?:oil free|lubricated|duty cycle|continuous duty|intermittent duty)\b", text):
        add("compressor_duty", "Confirm whether the compressor is oil-free or lubricated, and whether it is continuous-duty or intermittent-duty.", "medium", ["oil-free portable compressor", "lubricated workshop compressor", "continuous-duty installation"], ["pressure", "motorized"], ["MD", "MACH_REG"], ["Confirm lubrication type and duty-cycle classification."])
    if "av_ict" in traits and (APPLIANCE_PRIMARY_TRAITS & traits):
        add("primary_function_boundary", "Confirm whether the primary function is household appliance operation or AV/ICT signal processing / communication equipment.", "high", ["primary function is heating, cleaning, cooking, pumping, or another appliance task", "primary function is audio, video, display, computing, or network communication"], ["av_ict"], ["LVD", "EMC", "RED"], ["Confirm the primary function so the correct appliance or AV/ICT route is retained."])


def _boundary_review_questions(traits: set[str], add: MissingInformationAdd) -> None:
    if {"energy_system_boundary", "battery_storage_system", "inverter_system", "ups_function"} & traits:
        add(
            "energy_system_scope",
            "Confirm whether the product is a standalone consumer device or part of a wider inverter, storage, metering, or fixed-installation energy system.",
            "high",
            ["standalone UPS for office electronics", "hybrid inverter in a residential battery-storage system", "DIN-rail smart-meter gateway in a distribution board"],
            ["energy_system_boundary", "battery_storage_system", "inverter_system", "ups_function"],
            ["LVD", "BATTERY", "CRA"],
            ["Confirm the system architecture, installation context, and whether the product is a standalone device or an energy-system component."],
        )
    if "uv_irradiation_boundary" in traits:
        add(
            "uv_irradiation_intent",
            "Confirm whether the optical output is ordinary illumination only or is intended for UV/IR exposure, sanitizing, disinfection, or treatment.",
            "high",
            ["ordinary visible-light illumination only", "UV-C sanitizing output", "infrared illuminator for night vision", "cosmetic light-treatment output"],
            ["uv_irradiation_boundary", "uv_emitting", "infrared_emitting", "germicidal_emission"],
            ["LVD", "GPSR"],
            ["Confirm the emitted spectrum, intended optical function, and whether sanitizing or treatment claims are marketed."],
        )
    if "body_treatment_boundary" in traits:
        add(
            "body_treatment_scope",
            "Confirm whether the product remains in cosmetic or wellness scope, or whether it is marketed for therapy, treatment, stimulation, or other medical-adjacent outcomes.",
            "high",
            ["cosmetic nail-curing or grooming use only", "wellness-only massage use", "therapy or treatment claims", "clinical or patient use"],
            ["body_treatment_boundary", "possible_medical_boundary", "medical_claims"],
            ["GPSR", "MDR"],
            ["Confirm the intended-use statement and whether the marketed outcome is cosmetic, wellness-only, therapy, or medical."],
        )
    if "industrial_installation_boundary" in traits:
        add(
            "installation_boundary",
            "Confirm whether the product is sold as a consumer end product or as a fixed-installation, panel, cabinet, or professional building-system component.",
            "high",
            ["consumer plug-in device", "DIN-rail installation module", "panel-mounted building-system component"],
            ["industrial_installation_boundary", "fixed_installation", "smart_building"],
            ["LVD", "GPSR", "CRA"],
            ["Confirm whether installation is plug-in, wall-mounted consumer use, or professional panel / cabinet installation."],
        )
    if "machinery_boundary" in traits:
        add(
            "machinery_boundary_scope",
            "Confirm whether the equipment is a handheld / portable tool or a stationary, transportable, or machine-like product needing broader machinery review.",
            "high",
            ["handheld rotary tool", "transportable bench saw", "stationary workshop machine"],
            ["machinery_boundary", "motorized", "cutting_hazard"],
            ["MD", "MACH_REG"],
            ["Confirm the exact form factor, moving-part architecture, and whether the product is handheld, transportable, or stationary machinery."],
        )
    if "agricultural_special_use_boundary" in traits:
        add(
            "agricultural_special_use_scope",
            "Confirm whether the product is an ordinary consumer end product or a livestock, fencing, agricultural, or other special-use electrical product.",
            "high",
            ["ordinary consumer product", "livestock appliance", "electric fence energizer", "aquaculture or agricultural equipment"],
            ["agricultural_special_use_boundary", "animal_use", "professional"],
            ["GPSR", "LVD"],
            ["Confirm whether the intended use is consumer, agricultural, livestock, fencing, or another special-use environment."],
        )


def populate_missing_information_questions(
    *,
    traits: set[str],
    matched_products: set[str],
    product_type: str | None,
    product_match_stage: ProductMatchStage,
    route_family: str | None,
    text: str,
    known_fact_keys: set[str],
    add: MissingInformationAdd,
) -> None:
    tool_signal = bool(
        matched_products & {"industrial_power_tool", "corded_power_drill", "cordless_power_drill", "portable_power_saw", "industrial_air_compressor"}
    ) or bool(re.search(r"\b(?:power tool|drill|saw|compressor)\b", text))
    smart_signal = bool({"cloud", "app_control", "ota", "internet", "account", "authentication"} & traits) or bool({"wifi", "cellular"} & traits) or bool(
        re.search(r"\bsmart\b", text)
        or re.search(r"\bconnected\b", text)
        or (re.search(r"\bapp(?: control(?:led)?| enabled| connected)?\b", text) and not re.search(r"\b(?:no|without) app\b", text))
        or (re.search(r"\bcloud\b", text) and not re.search(r"\b(?:no|without) cloud\b", text))
        or (re.search(r"\bota\b", text) and not re.search(r"\b(?:no|without) ota\b", text))
    )
    if not ({"cloud", "app_control", "ota", "internet", "account", "authentication"} & traits or {"wifi", "cellular"} & traits):
        negated_connectivity = bool({"connectivity.no_wifi", "connectivity.no_radio"} & known_fact_keys) or bool(
            re.search(r"\b(?:no|without) wireless (?:communication|connectivity)\b", text)
        )
        if negated_connectivity:
            smart_signal = False
    battery_signal = bool({"battery_powered", "backup_battery"} & traits) or (
        not bool(re.search(r"\b(?:no|without) battery\b", text))
        and bool(re.search(r"\b(?:battery|rechargeable|cordless|cell pack|battery pack)\b", text))
    )
    compressor_signal = bool(matched_products & {"industrial_air_compressor"}) or bool(
        re.search(r"\b(?:air compressor|compressed air|pneumatic compressor|workshop compressor)\b", text)
    )
    body_contact_signal = bool({"wearable", "body_worn_or_applied", "personal_care"} & traits) or bool(
        {"contact.wearable", "contact.body_contact"} & known_fact_keys
    )
    health_data_signal = bool({"health_related", "health_data", "biometric"} & traits) or "data.health_related" in known_fact_keys
    medical_boundary_signal = bool({"possible_medical_boundary", "medical_context", "medical_claims"} & traits) or ("boundary.possible_medical" in known_fact_keys)
    cloud_detail_known = _has_cloud_dependency_detail(text) or bool(
        {"service.cloud_dependency", "service.cloud_account_required", "service.local_only"} & known_fact_keys
    )
    access_detail_known = _has_access_model_detail(text) or "service.cloud_account_required" in known_fact_keys
    update_detail_known = _has_update_route_detail(text) or "software.ota_updates" in known_fact_keys
    battery_pack_detail_known = _has_battery_pack_format_detail(text)
    radio_band_known = _has_radio_band_detail(text)
    radio_power_known = _has_radio_power_detail(text)
    data_category_known = _has_data_category_detail(text) or "data.health_related" in known_fact_keys

    _smart_lock_questions(product_type, traits, text, add)
    _ev_charging_questions(route_family, product_type, traits, text, add)
    _air_purifier_questions(product_type, text, add)
    _lighting_questions(route_family, product_type, text, add)
    _refrigerator_questions(product_type, text, add)
    _robot_vacuum_questions(product_type, text, add)
    _life_safety_alarm_questions(route_family, product_type, text, add)
    _machinery_tool_questions(route_family, product_type, traits, text, add)
    _toy_questions(traits, text, add)
    _power_source_questions(traits, product_match_stage, tool_signal, text, add)
    _external_psu_question(traits, text, add)
    _radio_questions(traits, matched_products, text, radio_band_known, radio_power_known, add)
    _smart_connectivity_questions(
        smart_signal,
        traits,
        text,
        cloud_detail_known,
        medical_boundary_signal,
        access_detail_known,
        update_detail_known,
        health_data_signal,
        data_category_known,
        add,
    )
    _battery_questions(battery_signal, text, battery_pack_detail_known, add)
    _body_contact_questions(body_contact_signal, text, add)
    _equipment_questions(tool_signal, compressor_signal, traits, text, add)
    _boundary_review_questions(traits, add)


__all__ = ["populate_missing_information_questions"]
