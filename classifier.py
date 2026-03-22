from __future__ import annotations

import re
from typing import Any

from knowledge_base import load_products, load_traits

TRAIT_IDS_CACHE: set[str] | None = None

GENERIC_ALIASES = {
    "air",
    "boiler",
    "clock",
    "cooler",
    "dryer",
    "fan",
    "fryer",
    "grill",
    "heater",
    "hood",
    "iron",
    "kettle",
    "lamp",
    "microwave",
    "oven",
    "pump",
    "shaver",
    "toaster",
    "vacuum",
    "washer",
}

POWER_TRAITS = {"battery_powered", "mains_powered", "mains_power_likely", "usb_powered", "external_psu"}
RADIO_TRAITS = {
    "bluetooth",
    "wifi",
    "wifi_5ghz",
    "wifi_6",
    "wifi_7",
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
CONNECTED_TRAITS = {"app_control", "cloud", "internet", "internet_connected", "ota", "account", "authentication"}
SERVICE_DEPENDENT_TRAITS = CONNECTED_TRAITS | {"personal_data_likely", "monetary_transaction"}
ENGINE_VERSION = "2.0"
ELECTRONIC_SIGNAL_TRAITS = RADIO_TRAITS | CONNECTED_TRAITS | {
    "av_ict",
    "camera",
    "display",
    "location",
    "microphone",
    "personal_data_likely",
    "speaker",
}

NORMALIZATION_REPLACEMENTS: list[tuple[str, str]] = [
    (r"\bwi[ -]?fi\b", "wifi"),
    (r"\bwlan\b", "wifi"),
    (r"\bbluetooth low energy\b", "bluetooth"),
    (r"\bble\b", "bluetooth"),
    (r"\bover[ -]?the[ -]?air\b", "ota"),
    (r"\bsign[ -]?in\b", "sign in"),
    (r"\blog[ -]?in\b", "log in"),
    (r"\b5[ -]?ghz\b", "5ghz"),
    (r"\bmulti[ -]?cooker\b", "multicooker"),
    (r"\bbean[ -]?to[ -]?cup\b", "bean to cup"),
    (r"\bair[ -]?conditioning\b", "air conditioner"),
    (r"\bsmart home\b", "smart_home"),
    (r"\be[ -]?ink\b", "eink"),
    (r"\be[ -]?paper\b", "epaper"),
    (r"\bpower over ethernet\b", "poe"),
]

NEGATIONS: dict[str, list[str]] = {
    "radio": [r"\bno radio\b", r"\bwithout radio\b"],
    "wifi": [r"\bno wifi\b", r"\bwithout wifi\b", r"\bnon wifi\b"],
    "bluetooth": [r"\bno bluetooth\b", r"\bwithout bluetooth\b"],
    "cloud": [r"\bno cloud\b", r"\bwithout cloud\b", r"\bcloud free\b", r"\blocal only\b"],
    "internet": [r"\bno internet\b", r"\bwithout internet\b", r"\boffline only\b", r"\blocal only\b"],
    "app_control": [r"\bno app\b", r"\bwithout app\b"],
    "ota": [r"\bno ota\b", r"\bwithout ota\b", r"\bmanual update only\b"],
    "account": [r"\bno account\b", r"\bwithout account\b", r"\bguest only\b"],
    "authentication": [r"\bno password\b", r"\bwithout login\b", r"\bwithout authentication\b"],
    "monetary_transaction": [
        r"\bno payment\b",
        r"\bwithout payment\b",
        r"\bno purchase\b",
        r"\bwithout subscription\b",
        r"\bno wallet\b",
    ],
}

TRAIT_PATTERNS: dict[str, list[str]] = {
    "radio": [r"\bradio\b"],
    "bluetooth": [r"\bbluetooth\b"],
    "wifi": [r"\bwifi\b", r"\b802 11\b"],
    "wifi_5ghz": [
        r"\b5ghz\b",
        r"\bdual band\b",
        r"\b802 11a\b",
        r"\b802 11ac\b",
        r"\b802 11ax\b",
        r"\bwifi 6\b",
        r"\bwifi 6e\b",
    ],
    "wifi_6": [r"\bwifi 6\b", r"\bwifi 6e\b", r"\b802 11ax\b"],
    "wifi_7": [r"\bwifi 7\b", r"\b802 11be\b"],
    "zigbee": [r"\bzigbee\b"],
    "thread": [r"\bthread\b"],
    "matter": [r"\bmatter\b"],
    "matter_bridge": [r"\bmatter bridge\b"],
    "nfc": [r"\bnfc\b", r"\brfid\b"],
    "cellular": [r"\bcellular\b", r"\blte\b", r"\b4g\b", r"\b5g\b", r"\bgsm\b", r"\bsim\b"],
    "dect": [r"\bdect\b"],
    "gsm": [r"\bgsm\b"],
    "sigfox": [r"\bsigfox\b"],
    "lte_m": [r"\blte m\b", r"\blte-m\b", r"\bnb iot\b", r"\bnb-iot\b"],
    "5g_nr": [r"\b5g nr\b", r"\bstandalone 5g\b"],
    "satellite_connectivity": [r"\bsatellite internet\b", r"\bsatellite connectivity\b", r"\bstarlink\b", r"\bvsat\b"],
    "lora": [r"\blora\b"],
    "lorawan": [r"\blorawan\b"],
    "uwb": [r"\buwb\b", r"\bultra wideband\b"],
    "wpa3": [r"\bwpa3\b"],
    "mesh_network_node": [r"\bmesh wifi\b", r"\bmesh node\b", r"\bwhole home wifi\b", r"\bmesh router\b", r"\bmesh network router\b"],
    "tri_band_wifi": [r"\btri band\b", r"\btri band wifi\b"],
    "app_control": [
        r"\bmobile app\b",
        r"\bcompanion app\b",
        r"\bsmartphone app\b",
        r"\bapp control\b",
        r"\bapp controlled\b",
        r"\bcontrol(?:led)? via app\b",
        r"\bworks with app\b",
    ],
    "cloud": [
        r"\bcloud\b",
        r"\bcloud account\b",
        r"\bcloud service\b",
        r"\bremote server\b",
        r"\bbackend api\b",
        r"\bweb service\b",
    ],
    "internet": [
        r"\binternet\b",
        r"\binternet connected\b",
        r"\bonline service\b",
        r"\bremote access\b",
        r"\bweb portal\b",
    ],
    "local_only": [r"\boffline\b", r"\bno cloud\b", r"\bno internet\b", r"\blocal only\b", r"\blan only\b"],
    "ota": [
        r"\bota\b",
        r"\bfirmware update\b",
        r"\bover the air\b",
        r"\bremote firmware update\b",
        r"\bsecurity patch\b",
        r"\bsoftware update over\b",
    ],
    "account": [r"\baccount\b", r"\blogin\b", r"\blog in\b", r"\bsign in\b", r"\buser account\b", r"\buser profile\b"],
    "authentication": [
        r"\bauthentication\b",
        r"\bpassword\b",
        r"\bpasscode\b",
        r"\bcredential\b",
        r"\bpin\b",
        r"\bpin code\b",
        r"\bpairing code\b",
        r"\btwo factor\b",
        r"\bmfa\b",
    ],
    "av_ict": [
        r"\brouter\b",
        r"\bmodem\b",
        r"\bgateway\b",
        r"\bnetwork switch\b",
        r"\bethernet switch\b",
        r"\baccess point\b",
        r"\bwireless access point\b",
        r"\blaptop\b",
        r"\bnotebook\b",
        r"\bdesktop pc\b",
        r"\bpersonal computer\b",
        r"\bserver\b",
        r"\bmonitor\b",
        r"\btelevision\b",
        r"\bsmart tv\b",
        r"\btv\b",
        r"\bsmart display\b",
        r"\bdisplay hub\b",
        r"\bset top box\b",
        r"\bset-top box\b",
        r"\bstreaming device\b",
        r"\bmedia player\b",
        r"\bprojector\b",
        r"\bsmart speaker\b",
        r"\bvoice assistant\b",
        r"\bict equipment\b",
        r"\baudio video equipment\b",
    ],
    "monetary_transaction": [
        r"\bpayment\b",
        r"\bpayments\b",
        r"\bpurchase\b",
        r"\bpurchases\b",
        r"\bcheckout\b",
        r"\bsubscription\b",
        r"\bwallet\b",
        r"\bmoney transfer\b",
        r"\bmonetary value\b",
        r"\bvirtual currency\b",
        r"\bin app purchase\b",
        r"\bplace order\b",
    ],
    "camera": [r"\bcamera\b"],
    "microphone": [r"\bmicrophone\b", r"\bmic\b", r"\bvoice assistant\b", r"\bvoice control\b", r"\bvoice command\b"],
    "speaker": [r"\bspeaker\b", r"\baudio playback\b", r"\bsound output\b"],
    "display": [r"\bdisplay\b", r"\bscreen\b", r"\btouchscreen\b", r"\btouch screen\b", r"\bmonitor\b"],
    "display_touchscreen": [r"\btouchscreen\b", r"\btouch screen\b"],
    "e_ink_display": [r"\beink\b", r"\bepaper\b", r"\be reader\b"],
    "hdr_display": [r"\bhdr10\b", r"\bhdr10\+\b", r"\bdolby vision\b", r"\bhlg\b"],
    "high_refresh_display": [r"\b90hz\b", r"\b120hz\b", r"\b144hz\b", r"\bhigh refresh\b"],
    "screen_mirroring": [r"\bscreen mirroring\b", r"\bchromecast\b", r"\bairplay\b", r"\bmiracast\b"],
    "multi_room_audio": [r"\bmulti room audio\b", r"\bmultiroom audio\b"],
    "spatial_audio": [r"\bspatial audio\b", r"\bdolby atmos\b", r"\bdts x\b", r"\b3d audio\b"],
    "voice_assistant": [r"\bvoice assistant\b", r"\balexa\b", r"\bgoogle assistant\b", r"\bsiri\b", r"\bbixby\b"],
    "privacy_switch": [r"\bprivacy switch\b", r"\bmic mute switch\b", r"\bcamera kill switch\b"],
    "parental_controls": [r"\bparental control\b", r"\bfamily safety\b", r"\bcontent filter\b"],
    "subscription_dependency": [r"\bsubscription required\b", r"\brequires subscription\b", r"\bpaid subscription\b"],
    "laser": [r"\blaser\b", r"\blidar\b", r"\blaser scanner\b", r"\brangefinder\b"],
    "location": [r"\bgps\b", r"\bgnss\b", r"\bgeolocation\b", r"\blocation tracking\b"],
    "battery_powered": [
        r"\bbattery powered\b",
        r"\bbattery operated\b",
        r"\brechargeable\b",
        r"\bcordless\b",
        r"\bli ion\b",
        r"\blithium\b",
        r"\bbattery\b",
    ],
    "external_psu": [
        r"\bexternal psu\b",
        r"\bexternal power supply\b",
        r"\bpower adapter\b",
        r"\bac adapter\b",
        r"\bdc adapter\b",
        r"\bpower brick\b",
        r"\bwall wart\b",
        r"\bplug pack\b",
        r"\bmains adapter\b",
    ],
    "usb_powered": [r"\busb powered\b", r"\busb c powered\b", r"\bpowered by usb\b", r"\btype c powered\b"],
    "usb_pd": [r"\busb pd\b", r"\bpower delivery\b", r"\busb power delivery\b"],
    "poe_powered": [r"\bpoe powered\b", r"\bpoe\b", r"\b802 3af\b", r"\b802 3at\b", r"\b802 3bt\b"],
    "poe_supply": [r"\bpoe injector\b", r"\bpoe switch\b", r"\bpower sourcing equipment\b"],
    "wireless_charging_tx": [r"\bwireless charger\b", r"\bcharging pad\b", r"\bcharging stand\b"],
    "wireless_charging_rx": [r"\bsupports wireless charging\b", r"\bwireless charging receiver\b"],
    "backup_battery": [r"\bbackup battery\b", r"\bbattery backup\b"],
    "energy_monitoring": [r"\benergy monitoring\b", r"\bpower monitoring\b", r"\benergy meter\b", r"\bpower consumption\b"],
    "smart_grid_ready": [r"\bsmart grid\b", r"\bdemand response\b", r"\bdynamic load management\b"],
    "mains_powered": [r"\bmains\b", r"\b230v\b", r"\b220v\b", r"\b240v\b", r"\bac power\b", r"\bplug in\b", r"\bplugged in\b"],
    "professional": [r"\bprofessional\b", r"\bcommercial\b", r"\bindustrial\b", r"\bcatering\b", r"\bhoreca\b"],
    "consumer": [r"\bconsumer\b", r"\bdomestic\b", r"\bhousehold\b", r"\bhome use\b"],
    "household": [r"\bhousehold\b", r"\bdomestic\b", r"\bhome use\b"],
    "outdoor_use": [r"\boutdoor\b", r"\bgarden\b", r"\blawn\b"],
    "fixed_installation": [r"\bbuilt in\b", r"\bfixed\b", r"\bwall mounted\b", r"\bceiling mounted\b", r"\bpermanently installed\b"],
    "wall_mount": [r"\bwall mounted\b", r"\bwall mount\b"],
    "ceiling_mount": [r"\bceiling mounted\b", r"\bceiling mount\b"],
    "rack_mount": [r"\brack mount\b", r"\b19 inch rack\b"],
    "din_rail_mount": [r"\bdin rail\b"],
    "portable": [r"\bportable\b", r"\btravel\b", r"\bhandheld\b"],
    "water_contact": [
        r"\bwater tank\b",
        r"\bwater reservoir\b",
        r"\bwater path\b",
        r"\bliquid handling\b",
        r"\bsteam\b",
        r"\brinse\b",
        r"\bwet use\b",
        r"\bimmersion\b",
    ],
    "heating": [r"\bheating\b", r"\bheater\b", r"\bhot\b", r"\bboil\b", r"\bbrew\b", r"\bsteam\b"],
    "cooling": [r"\bcooling\b", r"\brefrigerat\b", r"\bfreezer\b", r"\bice\b", r"\bchill\b"],
    "motorized": [r"\bmotor\b", r"\bfan\b", r"\bpump\b", r"\bcompressor\b", r"\bdrive\b"],
    "remote_control": [r"\bremote control\b", r"\bremote start\b", r"\bremote operation\b"],
    "remote_management": [r"\bremote management\b", r"\bdevice management\b", r"\bremote provisioning\b"],
    "secure_boot": [r"\bsecure boot\b"],
    "hardware_security_element": [r"\bsecurity element\b", r"\btpm\b", r"\bhsm\b", r"\bsecure enclave\b"],
    "ai_related": [r"\bai\b", r"\bmachine learning\b", r"\bneural\b", r"\bllm\b"],
    "personal_data_likely": [
        r"\bpersonal data\b",
        r"\buser data\b",
        r"\bprofile\b",
        r"\bprivacy\b",
    ],
    "food_contact": [
        r"\bfood contact\b",
        r"\bfood\b",
        r"\bdrink\b",
        r"\bbrew path\b",
        r"\bcook\b",
        r"\bwater tank\b",
    ],
    "wet_environment": [r"\bwet environment\b", r"\bbathroom\b", r"\bshower\b", r"\bsplash\b"],
    "body_worn_or_applied": [r"\bbody worn\b", r"\bbody worn use\b", r"\bon body\b", r"\bon skin\b"],
    "child_targeted": [r"\bchild targeted\b", r"\bfor children\b", r"\bkids mode\b"],
    "ambient_light_sensor": [r"\bambient light sensor\b", r"\blight sensor\b", r"\bauto brightness\b"],
    "occupancy_detection": [r"\boccupancy detection\b", r"\boccupancy sensor\b", r"\bpresence detection\b"],
    "gas_detection": [r"\bgas detection\b", r"\bgas detector\b", r"\blpg detector\b", r"\bnatural gas detector\b"],
    "flood_detection": [r"\bflood detection\b", r"\bwater leak\b", r"\bleak sensor\b"],
    "door_window_sensor": [r"\bdoor sensor\b", r"\bwindow sensor\b", r"\bcontact sensor\b"],
    "strobe_output": [r"\bstrobe\b", r"\bvisual alarm\b", r"\bflashing alarm\b"],
}


def normalize(text: str) -> str:
    text = (text or "").lower()
    for pattern, replacement in NORMALIZATION_REPLACEMENTS:
        text = re.sub(pattern, replacement, text)
    text = re.sub(r"[^a-z0-9_]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _known_trait_ids() -> set[str]:
    global TRAIT_IDS_CACHE
    if TRAIT_IDS_CACHE is None:
        TRAIT_IDS_CACHE = {row["id"] for row in load_traits()}
    return TRAIT_IDS_CACHE


def reset_classifier_cache() -> None:
    global TRAIT_IDS_CACHE
    TRAIT_IDS_CACHE = None


def _has_any_regex(text: str, patterns: list[str]) -> bool:
    return any(re.search(pattern, text) for pattern in patterns)


def _trait_is_negated(text: str, trait: str) -> bool:
    return _has_any_regex(text, NEGATIONS.get(trait, []))


def _add_regex_trait(text: str, explicit_traits: set[str]) -> None:
    for trait, regexes in TRAIT_PATTERNS.items():
        if _trait_is_negated(text, trait):
            continue
        if _has_any_regex(text, regexes):
            explicit_traits.add(trait)

    if RADIO_TRAITS & explicit_traits:
        explicit_traits.add("radio")
    if "wifi_5ghz" in explicit_traits:
        explicit_traits.add("wifi")

    if "cloud" in explicit_traits and "local_only" not in explicit_traits:
        explicit_traits.add("internet")
    if "ota" in explicit_traits and not _trait_is_negated(text, "internet"):
        explicit_traits.add("internet")
    if ("account" in explicit_traits or "authentication" in explicit_traits) and (
        {"cloud", "ota", "app_control", "wifi", "cellular", "internet"} & explicit_traits
    ):
        explicit_traits.add("internet")
    if {"account", "authentication", "camera", "microphone", "location"} & explicit_traits:
        explicit_traits.add("personal_data_likely")


def _infer_baseline_traits(text: str, explicit_traits: set[str]) -> set[str]:
    inferred: set[str] = set()

    electrical_signals = POWER_TRAITS | {
        "av_ict",
        "heating",
        "motorized",
        "radio",
        "camera",
        "display",
        "microphone",
        "speaker",
    }
    electronic_signals = ELECTRONIC_SIGNAL_TRAITS | {"radio", "electronic"}

    electrical_cues = [
        r"\belectric(?:al)?\b",
        r"\belectronic\b",
        r"\bpowered\b",
        r"\bvoltage\b",
        r"\bcharger\b",
        r"\badapter\b",
        r"\bplug\b",
        r"\bsocket\b",
        r"\bdevice\b",
        r"\bequipment\b",
        r"\bappliance\b",
    ]
    electronic_cues = [
        r"\belectronic\b",
        r"\bdigital\b",
        r"\bfirmware\b",
        r"\bsoftware\b",
        r"\bpcb\b",
        r"\bcircuit\b",
        r"\bsensor\b",
        r"\bsmart\b",
        r"\bconnected\b",
    ]

    if (electrical_signals & explicit_traits) or _has_any_regex(text, electrical_cues):
        inferred.add("electrical")
    if (electronic_signals & explicit_traits) or _has_any_regex(text, electronic_cues):
        inferred.add("electronic")
    if "electronic" in inferred and not ({"electrical"} & (explicit_traits | inferred)):
        inferred.add("electrical")

    if "wifi" in explicit_traits and ({"cloud", "ota", "account", "authentication", "app_control"} & explicit_traits):
        inferred.add("internet")
    if "cellular" in explicit_traits:
        inferred.add("internet")
    if "battery_powered" in explicit_traits and "portable" not in explicit_traits:
        inferred.add("portable")
    if "food_contact" in explicit_traits and "consumer" not in explicit_traits:
        inferred.add("consumer")

    return inferred


def _expand_related_traits(traits: set[str]) -> set[str]:
    expanded = set(traits)

    if expanded & RADIO_TRAITS:
        expanded.add("radio")
    if expanded & {"wifi_5ghz", "wifi_6", "wifi_7", "tri_band_wifi", "mesh_network_node", "wpa3"}:
        expanded.add("wifi")
    if expanded & {"gsm", "lte_m", "5g_nr"}:
        expanded.add("cellular")
    if "lorawan" in expanded:
        expanded.add("lora")
    if expanded & {"display_touchscreen", "e_ink_display", "hdr_display", "high_refresh_display"}:
        expanded.add("display")
    if expanded & {"voice_assistant", "privacy_switch"}:
        expanded.update({"microphone", "speaker", "personal_data_likely"})
    if expanded & {"parental_controls", "subscription_dependency"}:
        expanded.add("account")
    if "subscription_dependency" in expanded:
        expanded.add("monetary_transaction")
    if "matter_bridge" in expanded:
        expanded.add("matter")
    if expanded & {"internet", "internet_connected"}:
        expanded.update({"internet", "internet_connected"})
    if expanded & {"wireless_charging_rx", "wireless_charging_tx", "usb_pd", "poe_powered", "poe_supply", "backup_battery", "energy_monitoring", "smart_grid_ready", "vehicle_supply", "ev_charging", "solar_powered"}:
        expanded.add("electrical")
    if expanded & {
        "camera",
        "display",
        "microphone",
        "speaker",
        "data_storage",
        "screen_mirroring",
        "multi_room_audio",
        "spatial_audio",
        "voice_assistant",
        "parental_controls",
        "subscription_dependency",
        "secure_boot",
        "hardware_security_element",
        "remote_management",
        "matter_bridge",
        "e_ink_display",
        "hdr_display",
        "high_refresh_display",
        "display_touchscreen",
    }:
        expanded.add("av_ict")
    if expanded & {
        "camera",
        "display",
        "microphone",
        "speaker",
        "data_storage",
        "screen_mirroring",
        "multi_room_audio",
        "spatial_audio",
        "voice_assistant",
        "privacy_switch",
        "parental_controls",
        "subscription_dependency",
        "secure_boot",
        "hardware_security_element",
        "remote_management",
        "matter_bridge",
        "poe_powered",
        "poe_supply",
        "wireless_charging_rx",
        "wireless_charging_tx",
        "usb_pd",
        "energy_monitoring",
        "smart_grid_ready",
        "backup_battery",
        "ambient_light_sensor",
        "occupancy_detection",
        "gas_detection",
        "flood_detection",
        "door_window_sensor",
        "strobe_output",
    }:
        expanded.add("electronic")

    return expanded


def _alias_score(text: str, alias: str) -> int:
    alias_norm = normalize(alias)
    if not alias_norm:
        return 0

    exact_pattern = rf"(?<!\w){re.escape(alias_norm)}(?!\w)"
    if re.search(exact_pattern, text):
        score = 100 + len(alias_norm) * 3 + len(alias_norm.split()) * 22
        if alias_norm == text:
            score += 80
        return score

    tokens = alias_norm.split()
    if len(tokens) >= 2:
        gap_pattern = r"\b" + r"\b(?:\s+\w+){0,2}\s+\b".join(re.escape(t) for t in tokens) + r"\b"
        if re.search(gap_pattern, text):
            return 42 + len(tokens) * 12

    return 0


def _alias_specificity_bonus(alias: str) -> int:
    alias_norm = normalize(alias)
    if not alias_norm:
        return 0

    tokens = alias_norm.split()
    if len(tokens) >= 3:
        return 18
    if len(tokens) == 2:
        return 8
    if alias_norm in GENERIC_ALIASES:
        return -10
    return 0


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, str) and item]


def _product_family(product: dict[str, Any]) -> str:
    return str(product.get("product_family") or product["id"])


def _product_subfamily(product: dict[str, Any]) -> str:
    return str(product.get("product_subfamily") or product["id"])


def _phrase_present(text: str, phrase: str) -> bool:
    norm = normalize(phrase)
    if not norm:
        return False
    return re.search(rf"(?<!\w){re.escape(norm)}(?!\w)", text) is not None


def _matching_clues(text: str, clues: list[str]) -> list[str]:
    return [clue for clue in clues if _phrase_present(text, clue)]


def _trait_overlap_score(explicit_traits: set[str], product_traits: set[str], weight: int = 7) -> int:
    return len(explicit_traits & product_traits) * weight


def _context_bonus(text: str, product: dict[str, Any], explicit_traits: set[str]) -> tuple[int, list[str]]:
    score = 0
    reasons: list[str] = []
    pid = product["id"]
    traits = set(_string_list(product.get("subtype_traits")) or _string_list(product.get("implied_traits")))

    if any(term in text for term in ["commercial", "professional", "industrial", "horeca"]):
        if "professional" in traits or "commercial_food_service" in traits:
            score += 20
            reasons.append("commercial/professional context fits")
        elif "consumer" in traits or "household" in traits:
            score -= 16
            reasons.append("consumer product conflicts with commercial wording")

    if any(term in text for term in ["household", "domestic", "home use", "consumer"]):
        if "consumer" in traits or "household" in traits:
            score += 16
            reasons.append("household context fits")
        elif "professional" in traits:
            score -= 12
            reasons.append("professional product conflicts with household wording")

    if "battery" in text and "battery_powered" in traits:
        score += 8
        reasons.append("battery wording fits")
    if "wifi" in text and "wifi" in traits:
        score += 8
        reasons.append("wifi wording fits")
    if "bluetooth" in text and "bluetooth" in traits:
        score += 8
        reasons.append("bluetooth wording fits")
    if "built in" in text and ({"fixed_installation", "built_in"} & traits):
        score += 8
        reasons.append("built-in wording fits")
    if "portable" in text and "portable" in traits:
        score += 6
        reasons.append("portable wording fits")
    if "robot" in text and "robot" in pid:
        score += 10
        reasons.append("robot wording fits")
    if ({"cloud", "app_control", "ota"} & explicit_traits) and ({"wifi", "bluetooth", "thread", "zigbee", "matter", "radio"} & traits):
        score += 10
        reasons.append("connected context fits")

    return score, reasons


def _best_alias_match(text: str, product: dict[str, Any]) -> tuple[str | None, int, list[str]]:
    best_alias = None
    best_score = 0
    best_reasons: list[str] = []

    for alias in product.get("aliases", []):
        score = _alias_score(text, alias)
        if score <= 0:
            continue

        reasons = [f"matched alias '{alias}'"]
        alias_bonus = _alias_specificity_bonus(alias)
        if alias_bonus:
            score += alias_bonus
            reasons.append(f"alias specificity {alias_bonus:+d}")

        if best_alias is None or score > best_score:
            best_alias = alias
            best_score = score
            best_reasons = reasons

    return best_alias, best_score, best_reasons


def _family_seed_candidates(text: str, explicit_traits: set[str]) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    for product in load_products():
        best_alias, alias_score, alias_reasons = _best_alias_match(text, product)
        if best_alias is None:
            continue

        family_traits = set(_string_list(product.get("family_traits")) or _string_list(product.get("implied_traits")))
        score = alias_score
        reasons = list(alias_reasons)

        overlap = _trait_overlap_score(explicit_traits, family_traits, weight=5)
        if overlap:
            score += overlap
            reasons.append(f"family trait overlap +{overlap}")

        bonus, bonus_reasons = _context_bonus(text, product, explicit_traits)
        score += bonus
        reasons.extend(bonus_reasons)

        candidates.append(
            {
                "id": product["id"],
                "family": _product_family(product),
                "subtype": _product_subfamily(product),
                "label": product.get("label", product["id"]),
                "product": product,
                "matched_alias": best_alias,
                "score": score,
                "reasons": reasons,
            }
        )

    candidates.sort(key=lambda row: (-row["score"], row["id"]))
    return candidates


def _family_confidence(candidate: dict[str, Any], next_candidate: dict[str, Any] | None) -> str:
    score = candidate["score"]
    gap = score - next_candidate["score"] if next_candidate else score

    if score >= 160 and gap >= 20:
        return "high"
    if score >= 115 and gap >= 8:
        return "medium"
    if score >= 95:
        return "medium"
    return "low"


def _clue_score(text: str, product: dict[str, Any]) -> tuple[int, list[str], list[str], list[str], bool]:
    required_hits = _matching_clues(text, _string_list(product.get("required_clues")))
    preferred_hits = _matching_clues(text, _string_list(product.get("preferred_clues")))
    exclude_hits = _matching_clues(text, _string_list(product.get("exclude_clues")))

    score = len(required_hits) * 26 + len(preferred_hits) * 14 - len(exclude_hits) * 34
    reasons = [f"required clue '{clue}'" for clue in required_hits]
    reasons.extend(f"preferred clue '{clue}'" for clue in preferred_hits)
    reasons.extend(f"exclude clue '{clue}'" for clue in exclude_hits)

    required_clues = _string_list(product.get("required_clues"))
    if required_clues and not required_hits:
        score -= 18
        reasons.append("missing required subtype clues")

    decisive = bool(required_hits or len(preferred_hits) >= 2)
    positive_clues = required_hits + preferred_hits
    negative_clues = exclude_hits
    return score, reasons, positive_clues, negative_clues, decisive


def _family_members(products: list[dict[str, Any]], family: str) -> list[dict[str, Any]]:
    return [product for product in products if _product_family(product) == family]


def _subtype_candidates(
    text: str,
    explicit_traits: set[str],
    family_score: int,
    family_products: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    for product in family_products:
        best_alias, alias_score, alias_reasons = _best_alias_match(text, product)
        clue_score, clue_reasons, positive_clues, negative_clues, decisive = _clue_score(text, product)
        family_overlap = _trait_overlap_score(explicit_traits, set(_string_list(product.get("family_traits"))), weight=4)
        subtype_overlap = _trait_overlap_score(
            explicit_traits,
            set(_string_list(product.get("subtype_traits")) or _string_list(product.get("implied_traits"))),
            weight=7,
        )
        bonus, bonus_reasons = _context_bonus(text, product, explicit_traits)

        if best_alias is None and not positive_clues and subtype_overlap == 0 and family_overlap == 0:
            continue

        score = alias_score + clue_score + family_overlap + subtype_overlap + bonus
        reasons = list(alias_reasons)
        if family_overlap:
            reasons.append(f"family trait overlap +{family_overlap}")
        if subtype_overlap:
            reasons.append(f"subtype trait overlap +{subtype_overlap}")
        reasons.extend(clue_reasons)
        reasons.extend(bonus_reasons)

        candidates.append(
            {
                "id": product["id"],
                "label": product.get("label", product["id"]),
                "family": _product_family(product),
                "subtype": _product_subfamily(product),
                "matched_alias": best_alias,
                "family_score": family_score,
                "subtype_score": score,
                "score": score,
                "reasons": reasons,
                "positive_clues": positive_clues,
                "negative_clues": negative_clues,
                "decisive": decisive,
                "implied_traits": _string_list(product.get("implied_traits")),
                "family_traits": _string_list(product.get("family_traits")),
                "subtype_traits": _string_list(product.get("subtype_traits")) or _string_list(product.get("implied_traits")),
                "functional_classes": _string_list(product.get("functional_classes")),
                "likely_standards": _string_list(product.get("likely_standards")),
                "confusable_with": _string_list(product.get("confusable_with")),
            }
        )

    candidates.sort(key=lambda row: (-row["score"], row["id"]))
    return candidates


def _candidate_confidence(index: int, candidate: dict[str, Any], next_candidate: dict[str, Any] | None) -> str:
    score = candidate["score"]
    gap = score - next_candidate["score"] if next_candidate else score

    if index == 0 and score >= 155 and gap >= 22:
        return "high"
    if index == 0 and score >= 120 and gap >= 10:
        return "medium"
    if score >= 105:
        return "medium"
    return "low"


def _common_strings(rows: list[dict[str, Any]], field: str) -> list[str]:
    if not rows:
        return []

    common = set(_string_list(rows[0].get(field)))
    for row in rows[1:]:
        common &= set(_string_list(row.get(field)))
    return sorted(common)


def _hierarchical_product_match(text: str, explicit_traits: set[str]) -> dict[str, Any]:
    products = load_products()
    seed_candidates = _family_seed_candidates(text, explicit_traits)
    if not seed_candidates:
        return {
            "product_family": None,
            "product_family_confidence": "low",
            "product_subtype": None,
            "product_subtype_confidence": "low",
            "product_match_stage": "ambiguous",
            "product_type": None,
            "product_match_confidence": "low",
            "product_candidates": [],
            "matched_products": [],
            "routing_matched_products": [],
            "confirmed_products": [],
            "family_traits": set(),
            "subtype_traits": set(),
            "preferred_standard_codes": [],
            "functional_classes": set(),
            "confirmed_functional_classes": set(),
            "diagnostics": ["product_winner=none"],
            "contradictions": [],
        }

    by_family: dict[str, dict[str, Any]] = {}
    for row in seed_candidates:
        family = row["family"]
        existing = by_family.get(family)
        if existing is None or row["score"] > existing["score"]:
            by_family[family] = {
                "family": family,
                "score": row["score"],
                "representative": row,
            }

    family_candidates = sorted(by_family.values(), key=lambda row: (-row["score"], row["family"]))
    top_family = family_candidates[0]
    next_family = family_candidates[1] if len(family_candidates) > 1 else None
    family_confidence = _family_confidence(top_family, next_family)
    family_products = _family_members(products, top_family["family"])
    subtype_candidates = _subtype_candidates(text, explicit_traits, top_family["score"], family_products)
    if not subtype_candidates:
        subtype_candidates = [
            {
                **top_family["representative"],
                "family_score": top_family["score"],
                "subtype_score": top_family["score"],
                "positive_clues": [],
                "negative_clues": [],
                "decisive": False,
                "implied_traits": _string_list(top_family["representative"]["product"].get("implied_traits")),
                "family_traits": _string_list(top_family["representative"]["product"].get("family_traits")),
                "subtype_traits": _string_list(top_family["representative"]["product"].get("subtype_traits")),
                "functional_classes": _string_list(top_family["representative"]["product"].get("functional_classes")),
                "likely_standards": _string_list(top_family["representative"]["product"].get("likely_standards")),
                "confusable_with": _string_list(top_family["representative"]["product"].get("confusable_with")),
            }
        ]

    next_subtype = subtype_candidates[1] if len(subtype_candidates) > 1 else None
    subtype_confidence = _candidate_confidence(0, subtype_candidates[0], next_subtype)
    same_family_gap = subtype_candidates[0]["score"] - next_subtype["score"] if next_subtype else subtype_candidates[0]["score"]
    subtype_band = [row for row in subtype_candidates if subtype_candidates[0]["score"] - row["score"] <= 12][:3]
    top_row = subtype_candidates[0]
    decisive_medium = subtype_confidence == "medium" and (top_row["decisive"] or bool(top_row["matched_alias"]))
    family_stage = "subtype"
    contradictions: list[str] = []

    cross_family_ambiguous = bool(
        next_family and top_family["score"] - next_family["score"] < 8 and next_family["family"] != top_family["family"]
    )
    if cross_family_ambiguous and next_family is not None:
        family_stage = "ambiguous"
        contradictions.append(
            "Product identification is ambiguous between "
            f"{top_family['representative']['id'].replace('_', ' ')} and "
            f"{next_family['representative']['id'].replace('_', ' ')}."
        )
    elif next_subtype and top_row["negative_clues"] and next_subtype.get("positive_clues"):
        family_stage = "family"
    elif len(subtype_band) > 1 and same_family_gap < 12:
        family_stage = "family"
    elif subtype_confidence == "high" or decisive_medium or len(family_products) == 1:
        family_stage = "subtype"
    else:
        family_stage = "family"

    if family_stage == "family" and next_subtype and next_subtype["id"] not in {row["id"] for row in subtype_band}:
        subtype_band = [top_row, next_subtype]
    common_classes = _common_strings(subtype_band, "functional_classes")
    common_standards = _common_strings(subtype_band, "likely_standards")

    family_traits = set(_string_list(family_products[0].get("family_traits")) if family_products else [])
    subtype_traits = set(_string_list(top_row.get("subtype_traits")))
    functional_classes = set(_string_list(top_row.get("functional_classes")))
    confirmed_functional_classes: set[str] = set()
    preferred_standard_codes: list[str] = []
    confirmed_products: list[str] = []
    matched_products = [row["id"] for row in subtype_band]
    routing_matched_products: list[str] = []
    product_subtype = top_row["id"] if family_stage == "subtype" else None
    product_type = top_row["id"]
    product_match_confidence = subtype_confidence

    if family_stage == "ambiguous" and next_family is not None:
        matched_products = [top_family["representative"]["id"], next_family["representative"]["id"]]
        functional_classes = set()
        product_match_confidence = "low"
    elif family_stage == "family":
        functional_classes = set(common_classes)
        if family_confidence == "high":
            confirmed_functional_classes.update(common_classes)
        preferred_standard_codes = common_standards
        product_match_confidence = "medium" if family_confidence == "high" else family_confidence
    else:
        routing_matched_products = [top_row["id"]]
        preferred_standard_codes = _string_list(top_row.get("likely_standards"))
        if subtype_confidence == "high":
            confirmed_products = [top_row["id"]]
            confirmed_functional_classes.update(_string_list(top_row.get("functional_classes")))
        elif common_classes:
            confirmed_functional_classes.update(common_classes)

    product_candidates = []
    public_candidates = subtype_candidates[:5]
    if cross_family_ambiguous and next_family is not None:
        representative = next_family["representative"]
        public_candidates = public_candidates + [
            {
                "id": representative["id"],
                "label": representative["label"],
                "family": representative["family"],
                "subtype": representative["subtype"],
                "matched_alias": representative["matched_alias"],
                "family_score": next_family["score"],
                "subtype_score": representative["score"],
                "score": representative["score"],
                "reasons": representative["reasons"],
                "positive_clues": [],
                "negative_clues": [],
                "likely_standards": _string_list(representative["product"].get("likely_standards")),
            }
        ]

    for idx, candidate in enumerate(public_candidates[:5]):
        confidence = _candidate_confidence(
            idx,
            candidate,
            public_candidates[idx + 1] if idx + 1 < len(public_candidates) else None,
        )
        product_candidates.append(
            {
                "id": candidate["id"],
                "label": candidate["label"],
                "family": candidate.get("family"),
                "subtype": candidate.get("subtype"),
                "matched_alias": candidate.get("matched_alias"),
                "family_score": int(candidate.get("family_score", candidate.get("score", 0))),
                "subtype_score": int(candidate.get("subtype_score", candidate.get("score", 0))),
                "score": int(candidate.get("score", 0)),
                "confidence": confidence,
                "reasons": candidate.get("reasons", []),
                "positive_clues": candidate.get("positive_clues", []),
                "negative_clues": candidate.get("negative_clues", []),
                "likely_standards": candidate.get("likely_standards", []),
            }
        )

    diagnostics = [
        f"product_family={top_family['family']}",
        f"product_family_confidence={family_confidence}",
        f"product_subtype_candidate={top_row['id']}",
        f"product_subtype_confidence={subtype_confidence}",
        f"product_match_stage={family_stage}",
    ]

    return {
        "product_family": top_family["family"],
        "product_family_confidence": family_confidence,
        "product_subtype": product_subtype,
        "product_subtype_confidence": subtype_confidence,
        "product_match_stage": family_stage,
        "product_type": product_type,
        "product_match_confidence": product_match_confidence,
        "product_candidates": product_candidates,
        "matched_products": matched_products,
        "routing_matched_products": routing_matched_products,
        "confirmed_products": confirmed_products,
        "family_traits": family_traits,
        "subtype_traits": subtype_traits if family_stage == "subtype" else set(),
        "preferred_standard_codes": preferred_standard_codes,
        "functional_classes": functional_classes,
        "confirmed_functional_classes": confirmed_functional_classes,
        "diagnostics": diagnostics,
        "contradictions": contradictions,
    }


def _select_matched_products(product_candidates: list[dict[str, Any]]) -> list[str]:
    if not product_candidates:
        return []

    top_score = product_candidates[0]["score"]
    selected: list[str] = []

    for idx, candidate in enumerate(product_candidates[:4]):
        within_primary_band = top_score - candidate["score"] <= 18
        close_medium_alternative = idx > 0 and candidate["confidence"] != "low" and top_score - candidate["score"] <= 12
        if idx == 0 or within_primary_band or close_medium_alternative:
            selected.append(candidate["id"])

    return selected[:3] or [product_candidates[0]["id"]]


def _contradiction_severity(contradictions: list[str]) -> str:
    if not contradictions:
        return "none"
    if any("ambiguous" in item.lower() for item in contradictions):
        return "high"
    if len(contradictions) >= 2:
        return "high"
    return "medium"


def _empty_trait_state_map() -> dict[str, dict[str, list[str]]]:
    return {
        "text_explicit": {},
        "text_inferred": {},
        "product_core": {},
        "product_default": {},
        "engine_derived": {},
    }


def _record_trait_state(
    state_map: dict[str, dict[str, list[str]]],
    state: str,
    traits: set[str] | list[str],
    evidence: str,
) -> None:
    for trait in traits:
        state_map.setdefault(state, {}).setdefault(trait, [])
        if evidence not in state_map[state][trait]:
            state_map[state][trait].append(evidence)


def _trait_evidence_items(
    state_map: dict[str, dict[str, list[str]]],
    confirmed_traits: set[str],
) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    fact_basis_by_state = {
        "text_explicit": "confirmed",
        "product_core": "confirmed",
        "text_inferred": "inferred",
        "product_default": "inferred",
        "engine_derived": "inferred",
    }
    for state in ("text_explicit", "text_inferred", "product_core", "product_default", "engine_derived"):
        for trait in sorted(state_map.get(state, {})):
            items.append(
                {
                    "trait": trait,
                    "state": state,
                    "fact_basis": fact_basis_by_state[state],
                    "confirmed": trait in confirmed_traits,
                    "evidence": list(state_map[state][trait]),
                }
            )
    return items


def _collect_text_trait_signals(text: str) -> tuple[set[str], set[str], dict[str, dict[str, list[str]]], list[str]]:
    explicit_direct: set[str] = set()
    negations = sorted(trait for trait in TRAIT_PATTERNS if _trait_is_negated(text, trait))
    state_map = _empty_trait_state_map()

    for trait, regexes in TRAIT_PATTERNS.items():
        if trait in negations:
            continue
        if _has_any_regex(text, regexes):
            explicit_direct.add(trait)
            _record_trait_state(state_map, "text_explicit", {trait}, f"text:{trait}")

    explicit_traits = _expand_related_traits(explicit_direct)
    derived_explicit = explicit_traits - explicit_direct
    if derived_explicit:
        _record_trait_state(state_map, "text_explicit", derived_explicit, "text:derived")

    inferred_traits = _expand_related_traits(_infer_baseline_traits(text, explicit_traits))
    if inferred_traits:
        _record_trait_state(state_map, "text_inferred", inferred_traits, "text:baseline_inference")

    return explicit_traits, inferred_traits, state_map, negations


def _product_family_keywords(product: dict[str, Any]) -> list[str]:
    keywords = _string_list(product.get("family_keywords"))
    family_phrase = _product_family(product).replace("_", " ")
    if family_phrase and family_phrase != product["id"] and family_phrase not in keywords:
        keywords.append(family_phrase)
    return keywords


def _product_trait_buckets(product: dict[str, Any]) -> tuple[set[str], set[str]]:
    implied_traits = set(_string_list(product.get("implied_traits")))
    family_traits = set(_string_list(product.get("family_traits")))
    subtype_traits = set(_string_list(product.get("subtype_traits")) or _string_list(product.get("implied_traits")))
    raw_core = set(_string_list(product.get("core_traits")))
    raw_default = set(_string_list(product.get("default_traits")))

    if not raw_core:
        raw_core = set(family_traits | subtype_traits or implied_traits)
    if not raw_default:
        raw_default = implied_traits - raw_core

    raw_default |= raw_core & SERVICE_DEPENDENT_TRAITS
    raw_core -= SERVICE_DEPENDENT_TRAITS
    raw_default |= implied_traits - raw_core

    core_traits = _expand_related_traits(raw_core)
    default_traits = _expand_related_traits(raw_default) - core_traits
    return core_traits, default_traits


def _candidate_confidence_v2(candidate: dict[str, Any], next_candidate: dict[str, Any] | None = None) -> str:
    score = int(candidate.get("score", 0))
    gap = score - int(next_candidate.get("score", 0)) if next_candidate else score
    direct_signals = int(candidate.get("direct_signal_count", 0))
    if score >= 150 and gap >= 16 and direct_signals >= 2:
        return "high"
    if score >= 110 and gap >= 8 and direct_signals >= 1:
        return "medium"
    if score >= 85 and direct_signals >= 2:
        return "medium"
    return "low"


def _build_product_candidate_v2(text: str, signal_traits: set[str], product: dict[str, Any]) -> dict[str, Any] | None:
    best_alias, alias_score, alias_reasons = _best_alias_match(text, product)
    family_keyword_hits = _matching_clues(text, _product_family_keywords(product))
    clue_score, clue_reasons, positive_clues, negative_clues, decisive = _clue_score(text, product)
    core_traits, default_traits = _product_trait_buckets(product)
    family_overlap = _trait_overlap_score(signal_traits, set(_string_list(product.get("family_traits"))) or core_traits, weight=4)
    core_overlap = _trait_overlap_score(signal_traits, core_traits, weight=6)
    default_overlap = _trait_overlap_score(signal_traits, default_traits, weight=3)
    bonus, bonus_reasons = _context_bonus(text, product, signal_traits)

    score = alias_score + clue_score + family_overlap + core_overlap + default_overlap + bonus
    score += len(family_keyword_hits) * 24

    direct_signal_count = int(bool(best_alias)) + len(positive_clues) + len(family_keyword_hits)
    if not direct_signal_count and score < 28:
        return None

    reasons = list(alias_reasons)
    reasons.extend(f"family keyword '{hit}'" for hit in family_keyword_hits)
    reasons.extend(clue_reasons)
    if family_overlap:
        reasons.append(f"family trait overlap +{family_overlap}")
    if core_overlap:
        reasons.append(f"product core overlap +{core_overlap}")
    if default_overlap:
        reasons.append(f"product default overlap +{default_overlap}")
    reasons.extend(bonus_reasons)

    return {
        "id": product["id"],
        "label": product.get("label", product["id"]),
        "family": _product_family(product),
        "subtype": _product_subfamily(product),
        "genres": _string_list(product.get("genres")),
        "product": product,
        "matched_alias": best_alias,
        "alias_hits": [best_alias] if best_alias else [],
        "family_keyword_hits": family_keyword_hits,
        "positive_clues": positive_clues,
        "negative_clues": negative_clues,
        "decisive": decisive or bool(best_alias) or bool(family_keyword_hits),
        "score": score,
        "direct_signal_count": direct_signal_count,
        "reasons": reasons,
        "core_traits": sorted(core_traits),
        "default_traits": sorted(default_traits),
        "family_traits": _string_list(product.get("family_traits")),
        "subtype_traits": _string_list(product.get("subtype_traits")) or _string_list(product.get("implied_traits")),
        "functional_classes": _string_list(product.get("functional_classes")),
        "likely_standards": _string_list(product.get("likely_standards")),
        "confusable_with": _string_list(product.get("confusable_with")),
    }


def _common_sets(rows: list[dict[str, Any]], field: str) -> set[str]:
    if not rows:
        return set()
    common = set(_string_list(rows[0].get(field)))
    for row in rows[1:]:
        common &= set(_string_list(row.get(field)))
    return common


def _hierarchical_product_match_v2(text: str, signal_traits: set[str]) -> dict[str, Any]:
    candidates = [
        candidate
        for product in load_products()
        if (candidate := _build_product_candidate_v2(text, signal_traits, product)) is not None
    ]
    candidates.sort(key=lambda row: (-int(row["score"]), row["id"]))

    if not candidates:
        return {
            "product_family": None,
            "product_family_confidence": "low",
            "product_subtype": None,
            "product_subtype_confidence": "low",
            "product_match_stage": "ambiguous",
            "product_type": None,
            "product_match_confidence": "low",
            "product_candidates": [],
            "matched_products": [],
            "routing_matched_products": [],
            "confirmed_products": [],
            "product_core_traits": set(),
            "product_default_traits": set(),
            "product_genres": set(),
            "preferred_standard_codes": [],
            "functional_classes": set(),
            "confirmed_functional_classes": set(),
            "diagnostics": ["product_winner=none"],
            "contradictions": [],
            "audit": {
                "engine_version": ENGINE_VERSION,
                "normalized_text": text,
                "retrieval_basis": [],
                "alias_hits": [],
                "family_keyword_hits": [],
                "clue_hits": [],
                "negations": [],
                "ambiguity_reason": None,
            },
        }

    families: dict[str, dict[str, Any]] = {}
    for row in candidates:
        family = row["family"]
        existing = families.get(family)
        if existing is None or int(row["score"]) > int(existing["score"]):
            families[family] = row

    family_candidates = sorted(families.values(), key=lambda row: (-int(row["score"]), row["family"]))
    top_family = family_candidates[0]
    next_family = family_candidates[1] if len(family_candidates) > 1 else None
    family_confidence = _candidate_confidence_v2(top_family, next_family)

    family_rows = [row for row in candidates if row["family"] == top_family["family"]]
    top_row = family_rows[0]
    next_subtype = family_rows[1] if len(family_rows) > 1 else None
    subtype_confidence = _candidate_confidence_v2(top_row, next_subtype)
    contradictions: list[str] = []
    ambiguity_reason: str | None = None

    family_gap = int(top_family["score"]) - int(next_family["score"]) if next_family else int(top_family["score"])
    subtype_gap = int(top_row["score"]) - int(next_subtype["score"]) if next_subtype else int(top_row["score"])
    close_family_competition = bool(next_family and family_gap < 8 and next_family["family"] != top_family["family"])
    close_subtype_competition = bool(next_subtype and subtype_gap < 10)

    if close_family_competition:
        assert next_family is not None
        family_stage = "ambiguous"
        ambiguity_reason = (
            f"Product identification remains ambiguous between {top_family['id'].replace('_', ' ')} "
            f"and {next_family['id'].replace('_', ' ')}."
        )
        contradictions.append(ambiguity_reason)
    elif next_subtype and top_row.get("negative_clues") and next_subtype.get("positive_clues"):
        family_stage = "family"
        ambiguity_reason = f"Confusable subtype clues remain unresolved within family {top_family['family'].replace('_', ' ')}."
    elif close_subtype_competition:
        family_stage = "family"
        ambiguity_reason = f"Subtype evidence is too close within family {top_family['family'].replace('_', ' ')}."
    elif subtype_confidence == "high" or (subtype_confidence == "medium" and top_row["decisive"]):
        family_stage = "subtype"
    elif family_confidence in {"high", "medium"}:
        family_stage = "family"
    else:
        family_stage = "ambiguous"
        ambiguity_reason = f"Product evidence for {top_family['label']} is too weak to confirm a subtype."

    subtype_band = [row for row in family_rows if int(top_row["score"]) - int(row["score"]) <= 10][:3]
    if family_stage == "family" and next_subtype and next_subtype["id"] not in {row["id"] for row in subtype_band}:
        subtype_band = [top_row, next_subtype]

    common_classes = _common_strings(subtype_band, "functional_classes")
    common_standards = _common_strings(subtype_band, "likely_standards")
    common_core_traits = _common_sets(subtype_band, "core_traits")
    common_default_traits = _common_sets(subtype_band, "default_traits")
    common_genres = _common_sets(subtype_band, "genres")

    product_core_traits = set(_string_list(top_row.get("core_traits")))
    product_default_traits = set(_string_list(top_row.get("default_traits")))
    product_genres = set(_string_list(top_row.get("genres")))
    functional_classes = set(_string_list(top_row.get("functional_classes")))
    confirmed_functional_classes: set[str] = set()
    preferred_standard_codes: list[str] = []
    confirmed_products: list[str] = []
    matched_products = [row["id"] for row in subtype_band]
    routing_matched_products: list[str] = []
    product_subtype = top_row["id"] if family_stage == "subtype" else None
    product_type = top_row["id"]
    product_match_confidence = subtype_confidence

    if family_stage == "ambiguous" and next_family is not None:
        matched_products = [top_family["id"], next_family["id"]]
        functional_classes = set()
        product_core_traits = set()
        product_default_traits = set()
        product_genres = set()
        product_match_confidence = "low"
    elif family_stage == "family":
        functional_classes = set(common_classes)
        product_core_traits = set(common_core_traits)
        product_default_traits = set(common_default_traits)
        product_genres = set(common_genres)
        preferred_standard_codes = common_standards
        product_match_confidence = "medium" if family_confidence == "high" else family_confidence
        if family_confidence == "high":
            confirmed_functional_classes.update(common_classes)
    else:
        routing_matched_products = [top_row["id"]]
        preferred_standard_codes = _string_list(top_row.get("likely_standards"))
        if subtype_confidence == "high":
            confirmed_products = [top_row["id"]]
            confirmed_functional_classes.update(_string_list(top_row.get("functional_classes")))
        elif common_classes:
            confirmed_functional_classes.update(common_classes)

    public_candidates = family_rows[:5]
    if close_family_competition and next_family is not None and next_family not in public_candidates:
        public_candidates = public_candidates + [next_family]

    product_candidates: list[dict[str, Any]] = []
    for idx, candidate in enumerate(public_candidates[:5]):
        confidence = _candidate_confidence_v2(
            candidate,
            public_candidates[idx + 1] if idx + 1 < len(public_candidates) else None,
        )
        product_candidates.append(
            {
                "id": candidate["id"],
                "label": candidate["label"],
                "family": candidate.get("family"),
                "subtype": candidate.get("subtype"),
                "matched_alias": candidate.get("matched_alias"),
                "family_score": int(families[candidate["family"]]["score"]) if candidate["family"] in families else int(candidate["score"]),
                "subtype_score": int(candidate.get("score", 0)),
                "score": int(candidate.get("score", 0)),
                "confidence": confidence,
                "reasons": candidate.get("reasons", []),
                "positive_clues": candidate.get("positive_clues", []),
                "negative_clues": candidate.get("negative_clues", []),
                "likely_standards": candidate.get("likely_standards", []),
            }
        )

    audit_rows = subtype_band if family_stage == "family" else [top_row]
    alias_hits = sorted({hit for row in audit_rows for hit in row.get("alias_hits", []) if hit})
    family_keyword_hits = sorted({hit for row in audit_rows for hit in row.get("family_keyword_hits", []) if hit})
    clue_hits = sorted({hit for row in audit_rows for hit in row.get("positive_clues", []) if hit})

    diagnostics = [
        f"product_family={top_family['family']}",
        f"product_family_confidence={family_confidence}",
        f"product_subtype_candidate={top_row['id']}",
        f"product_subtype_confidence={subtype_confidence}",
        f"product_match_stage={family_stage}",
    ]

    return {
        "product_family": top_family["family"],
        "product_family_confidence": family_confidence,
        "product_subtype": product_subtype,
        "product_subtype_confidence": subtype_confidence,
        "product_match_stage": family_stage,
        "product_type": product_type,
        "product_match_confidence": product_match_confidence,
        "product_candidates": product_candidates,
        "matched_products": matched_products,
        "routing_matched_products": routing_matched_products,
        "confirmed_products": confirmed_products,
        "product_core_traits": product_core_traits,
        "product_default_traits": product_default_traits,
        "product_genres": product_genres,
        "preferred_standard_codes": preferred_standard_codes,
        "functional_classes": functional_classes,
        "confirmed_functional_classes": confirmed_functional_classes,
        "diagnostics": diagnostics,
        "contradictions": contradictions,
        "audit": {
            "engine_version": ENGINE_VERSION,
            "normalized_text": text,
            "retrieval_basis": top_row.get("reasons", []),
            "alias_hits": alias_hits,
            "family_keyword_hits": family_keyword_hits,
            "clue_hits": clue_hits,
            "negations": [],
            "ambiguity_reason": ambiguity_reason,
        },
    }


def extract_traits_v2(description: str, category: str = "") -> dict:
    text = normalize(f"{category} {description}")
    explicit_traits, inferred_traits, state_map, negations = _collect_text_trait_signals(text)
    functional_classes: set[str] = set()
    confirmed_functional_classes: set[str] = set()
    contradictions: list[str] = []
    diagnostics: list[str] = [f"normalized_text={text}"]

    match = _hierarchical_product_match_v2(text, explicit_traits | inferred_traits)
    product_candidates = match["product_candidates"]
    matched_products = match["matched_products"]
    routing_matched_products = match["routing_matched_products"]
    confirmed_products = match["confirmed_products"]
    preferred_standard_codes = match["preferred_standard_codes"]
    product_family_confidence = match["product_family_confidence"]
    product_subtype_confidence = match["product_subtype_confidence"]
    product_match_stage = match["product_match_stage"]
    product_core_traits = _expand_related_traits(set(match.get("product_core_traits") or set()))
    product_default_traits = _expand_related_traits(set(match.get("product_default_traits") or set()))
    product_genres = {item for item in (match.get("product_genres") or set()) if isinstance(item, str) and item}

    functional_classes.update(match["functional_classes"])
    confirmed_functional_classes.update(match["confirmed_functional_classes"])
    if product_core_traits:
        product_evidence = (
            f"product:{match['product_subtype']}" if product_match_stage == "subtype" and match.get("product_subtype") else f"family:{match['product_family']}"
        )
        _record_trait_state(state_map, "product_core", product_core_traits, product_evidence)
    if product_default_traits:
        product_evidence = (
            f"product_default:{match['product_subtype']}"
            if product_match_stage == "subtype" and match.get("product_subtype")
            else f"family_default:{match['product_family']}"
        )
        _record_trait_state(state_map, "product_default", product_default_traits, product_evidence)

    confirmed_traits = set(explicit_traits)
    top_candidate = product_candidates[0] if product_candidates else {}
    decisive_medium = (
        product_match_stage == "subtype"
        and product_subtype_confidence == "medium"
        and bool(top_candidate.get("matched_alias") or top_candidate.get("positive_clues"))
    )
    decisive_subtype = (
        product_match_stage == "subtype"
        and bool(
            top_candidate.get("matched_alias")
            or top_candidate.get("positive_clues")
            or top_candidate.get("family_keyword_hits")
        )
    )
    if product_family_confidence == "high":
        confirmed_traits.update(product_core_traits - SERVICE_DEPENDENT_TRAITS)
    if product_match_stage == "subtype" and (product_subtype_confidence == "high" or decisive_medium or decisive_subtype):
        confirmed_traits.update(product_core_traits - SERVICE_DEPENDENT_TRAITS)

    corroborated_default = {trait for trait in product_default_traits if trait in explicit_traits}
    confirmed_traits.update(corroborated_default - SERVICE_DEPENDENT_TRAITS)

    diagnostics.extend(match["diagnostics"])
    if product_candidates:
        diagnostics.append(f"product_winner={product_candidates[0]['id']}")
        diagnostics.append(f"product_alias={product_candidates[0].get('matched_alias') or ''}")
    else:
        diagnostics.append("product_winner=none")

    contradictions.extend(match["contradictions"])

    if "battery_powered" in explicit_traits and "mains_powered" in explicit_traits:
        contradictions.append("Both battery-powered and mains-powered signals were detected.")
    if "cloud" in explicit_traits and "local_only" in explicit_traits:
        contradictions.append("Both cloud-connected and local-only signals were detected.")
    if "professional" in explicit_traits and "household" in explicit_traits:
        contradictions.append("Both professional/commercial and household-use signals were detected.")
    if "wifi" in explicit_traits and _trait_is_negated(text, "internet") and {"cloud", "ota", "account"} & explicit_traits:
        contradictions.append("Wi-Fi is present while the text also says no internet, but cloud or OTA features were also detected.")

    known_traits = _known_trait_ids()
    explicit_traits = {trait for trait in _expand_related_traits(explicit_traits) if trait in known_traits}
    inferred_traits = {trait for trait in _expand_related_traits(inferred_traits | product_core_traits | product_default_traits) if trait in known_traits}
    confirmed_traits = {trait for trait in _expand_related_traits(confirmed_traits) if trait in known_traits}

    diagnostics.append("matched_products=" + ",".join(matched_products))
    diagnostics.append("routing_matched_products=" + ",".join(routing_matched_products))
    diagnostics.append("confirmed_products=" + ",".join(confirmed_products))
    diagnostics.append("product_genres=" + ",".join(sorted(product_genres)))
    diagnostics.append("preferred_standard_codes=" + ",".join(preferred_standard_codes))
    diagnostics.append("explicit_traits=" + ",".join(sorted(explicit_traits)))
    diagnostics.append("confirmed_traits=" + ",".join(sorted(confirmed_traits)))
    diagnostics.append("inferred_traits=" + ",".join(sorted(inferred_traits)))
    diagnostics.append("negations=" + ",".join(negations))
    diagnostics.append("contradiction_severity=" + _contradiction_severity(contradictions))

    match["audit"]["negations"] = negations
    return {
        "product_type": match.get("product_type"),
        "product_family": match.get("product_family"),
        "product_family_confidence": product_family_confidence,
        "product_subtype": match.get("product_subtype"),
        "product_subtype_confidence": product_subtype_confidence,
        "product_match_stage": product_match_stage,
        "matched_products": matched_products,
        "routing_matched_products": routing_matched_products,
        "confirmed_products": confirmed_products,
        "product_genres": sorted(product_genres),
        "preferred_standard_codes": preferred_standard_codes,
        "product_match_confidence": match.get("product_match_confidence"),
        "product_candidates": product_candidates,
        "functional_classes": sorted(functional_classes),
        "confirmed_functional_classes": sorted(confirmed_functional_classes),
        "explicit_traits": sorted(explicit_traits),
        "confirmed_traits": sorted(confirmed_traits),
        "inferred_traits": sorted((explicit_traits | inferred_traits) - confirmed_traits),
        "all_traits": sorted(explicit_traits | inferred_traits),
        "text_explicit_traits": sorted(explicit_traits),
        "text_inferred_traits": sorted({trait for trait in state_map["text_inferred"] if trait in known_traits}),
        "product_core_traits": sorted(product_core_traits & known_traits),
        "product_default_traits": sorted(product_default_traits & known_traits),
        "contradictions": contradictions,
        "contradiction_severity": _contradiction_severity(contradictions),
        "diagnostics": diagnostics,
        "trait_state_map": state_map,
        "trait_evidence": _trait_evidence_items(state_map, confirmed_traits),
        "product_match_audit": match["audit"],
        "engine_version": ENGINE_VERSION,
    }


def extract_traits_v1(description: str, category: str = "") -> dict:
    text = normalize(f"{category} {description}")
    explicit_traits: set[str] = set()
    inferred_traits: set[str] = set()
    confirmed_traits: set[str] = set()
    functional_classes: set[str] = set()
    confirmed_functional_classes: set[str] = set()
    contradictions: list[str] = []
    diagnostics: list[str] = []

    _add_regex_trait(text, explicit_traits)
    explicit_traits = _expand_related_traits(explicit_traits)
    inferred_traits.update(_infer_baseline_traits(text, explicit_traits))
    diagnostics.append(f"normalized_text={text}")

    match = _hierarchical_product_match(text, explicit_traits | inferred_traits)
    product_type = match["product_type"]
    product_match_confidence = match["product_match_confidence"]
    product_candidates = match["product_candidates"]
    matched_products = match["matched_products"]
    routing_matched_products = match["routing_matched_products"]
    confirmed_products = match["confirmed_products"]
    preferred_standard_codes = match["preferred_standard_codes"]
    product_family = match["product_family"]
    product_family_confidence = match["product_family_confidence"]
    product_subtype = match["product_subtype"]
    product_subtype_confidence = match["product_subtype_confidence"]
    product_match_stage = match["product_match_stage"]

    inferred_traits.update(match["family_traits"])
    inferred_traits.update(match["subtype_traits"])
    functional_classes.update(match["functional_classes"])
    confirmed_functional_classes.update(match["confirmed_functional_classes"])
    if product_family_confidence == "high":
        confirmed_traits.update(match["family_traits"])
    if product_match_stage == "subtype" and product_subtype_confidence == "high":
        confirmed_traits.update(match["subtype_traits"])

    diagnostics.extend(match["diagnostics"])
    if product_candidates:
        diagnostics.append(f"product_winner={product_candidates[0]['id']}")
        diagnostics.append(f"product_alias={product_candidates[0].get('matched_alias') or ''}")
    else:
        diagnostics.append("product_winner=none")

    contradictions.extend(match["contradictions"])

    if "battery_powered" in explicit_traits and "mains_powered" in explicit_traits:
        contradictions.append("Both battery-powered and mains-powered signals were detected.")
    if "cloud" in explicit_traits and "local_only" in explicit_traits:
        contradictions.append("Both cloud-connected and local-only signals were detected.")
    if "professional" in explicit_traits and "household" in explicit_traits:
        contradictions.append("Both professional/commercial and household-use signals were detected.")
    if "wifi" in explicit_traits and _trait_is_negated(text, "internet") and {"cloud", "ota", "account"} & explicit_traits:
        contradictions.append("Wi-Fi is present while the text also says no internet, but cloud or OTA features were also detected.")

    known_traits = _known_trait_ids()
    explicit_traits = _expand_related_traits(explicit_traits)
    inferred_traits = _expand_related_traits(inferred_traits)
    confirmed_traits = _expand_related_traits(confirmed_traits)
    explicit_traits = {t for t in explicit_traits if t in known_traits}
    inferred_traits = {t for t in inferred_traits if t in known_traits}
    confirmed_traits = {t for t in (confirmed_traits | explicit_traits) if t in known_traits}

    diagnostics.append("matched_products=" + ",".join(matched_products))
    diagnostics.append("routing_matched_products=" + ",".join(routing_matched_products))
    diagnostics.append("confirmed_products=" + ",".join(confirmed_products))
    diagnostics.append("preferred_standard_codes=" + ",".join(preferred_standard_codes))
    diagnostics.append("explicit_traits=" + ",".join(sorted(explicit_traits)))
    diagnostics.append("confirmed_traits=" + ",".join(sorted(confirmed_traits)))
    diagnostics.append("inferred_traits=" + ",".join(sorted(inferred_traits)))
    diagnostics.append("contradiction_severity=" + _contradiction_severity(contradictions))

    return {
        "product_type": product_type,
        "product_family": product_family,
        "product_family_confidence": product_family_confidence,
        "product_subtype": product_subtype,
        "product_subtype_confidence": product_subtype_confidence,
        "product_match_stage": product_match_stage,
        "matched_products": matched_products,
        "routing_matched_products": routing_matched_products,
        "confirmed_products": confirmed_products,
        "preferred_standard_codes": preferred_standard_codes,
        "product_match_confidence": product_match_confidence,
        "product_candidates": product_candidates,
        "functional_classes": sorted(functional_classes),
        "confirmed_functional_classes": sorted(confirmed_functional_classes),
        "explicit_traits": sorted(explicit_traits),
        "confirmed_traits": sorted(confirmed_traits),
        "inferred_traits": sorted(inferred_traits),
        "all_traits": sorted(explicit_traits | inferred_traits),
        "contradictions": contradictions,
        "contradiction_severity": _contradiction_severity(contradictions),
        "diagnostics": diagnostics,
    }


def extract_traits(description: str, category: str = "") -> dict:
    return extract_traits_v2(description=description, category=category)
