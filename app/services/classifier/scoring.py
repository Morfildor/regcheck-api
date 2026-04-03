from __future__ import annotations

from collections.abc import Mapping
import re
from typing import Any

from app.domain.catalog_types import ProductCatalogRow

from .normalization import normalize
from .signal_config import get_classifier_signal_snapshot

ProductRowLike = ProductCatalogRow | Mapping[str, Any]

GENERIC_ALIASES = {
    "air",
    "alarm",
    "boiler",
    "camera",
    "charger",
    "clock",
    "cooler",
    "controller",
    "display",
    "dryer",
    "fan",
    "fryer",
    "grill",
    "heater",
    "hood",
    "hub",
    "iron",
    "kettle",
    "lamp",
    "microwave",
    "monitor",
    "oven",
    "player",
    "pump",
    "receiver",
    "shaver",
    "switch",
    "terminal",
    "toaster",
    "vacuum",
    "washer",
    "station",
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

_PHRASE_PATTERN_CACHE: dict[str, re.Pattern] = {}
_ALIAS_PATTERN_CACHE: dict[str, tuple[re.Pattern, re.Pattern | None]] = {}

ALIAS_FIELD_BONUS: dict[str, int] = {
    "strong_aliases": 12,
    "aliases": 0,
    "marketplace_aliases": 6,
    "weak_aliases": -4,
}

def _alias_score(text: str, alias: str) -> int:
    alias_norm = normalize(alias)
    if not alias_norm:
        return 0

    cached = _ALIAS_PATTERN_CACHE.get(alias_norm)
    if cached is None:
        exact_pat = re.compile(rf"(?<!\w){re.escape(alias_norm)}(?!\w)")
        tokens = alias_norm.split()
        gap_pat = (
            re.compile(r"\b" + r"\b(?:\s+\w+){0,2}\s+\b".join(re.escape(t) for t in tokens) + r"\b")
            if len(tokens) >= 2
            else None
        )
        cached = (exact_pat, gap_pat)
        _ALIAS_PATTERN_CACHE[alias_norm] = cached

    exact_pat, gap_pat = cached
    if exact_pat.search(text):
        score = 100 + len(alias_norm) * 3 + len(alias_norm.split()) * 22
        if alias_norm == text:
            score += 80
        return score

    if gap_pat is not None and gap_pat.search(text):
        return 42 + len(alias_norm.split()) * 12

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


def _product_family(product: ProductRowLike) -> str:
    return str(product.get("product_family") or "")


def _product_subfamily(product: ProductRowLike) -> str:
    return str(product.get("product_subfamily") or "")


def _phrase_present(text: str, phrase: str) -> bool:
    norm = normalize(phrase)
    if not norm:
        return False
    pattern = _PHRASE_PATTERN_CACHE.get(norm)
    if pattern is None:
        pattern = re.compile(rf"(?<!\w){re.escape(norm)}(?!\w)")
        _PHRASE_PATTERN_CACHE[norm] = pattern
    return pattern.search(text) is not None


def _matching_clues(text: str, clues: list[str]) -> list[str]:
    return [clue for clue in clues if _phrase_present(text, clue)]


def _trait_overlap_score(explicit_traits: set[str], product_traits: set[str], weight: int = 7) -> int:
    return len(explicit_traits & product_traits) * weight


def _context_bonus(text: str, product: ProductRowLike, explicit_traits: set[str]) -> tuple[int, list[str]]:
    score = 0
    reasons: list[str] = []
    pid = product["id"]
    traits = set(_string_list(product.get("subtype_traits")) or _string_list(product.get("implied_traits")))
    cue_groups = get_classifier_signal_snapshot().compiled_cue_groups

    if any(pattern.search(text) for pattern in cue_groups.get("professional_use", ())):
        if "professional" in traits or "commercial_food_service" in traits:
            score += 20
            reasons.append("commercial/professional context fits")
        elif "consumer" in traits or "household" in traits:
            score -= 16
            reasons.append("consumer product conflicts with commercial wording")

    if any(pattern.search(text) for pattern in cue_groups.get("household_use", ())):
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
    if ({"wearable", "body_worn_or_applied"} & explicit_traits) and ({"wearable", "body_worn_or_applied"} & traits):
        score += 10
        reasons.append("body-contact wording fits")
    if ({"health_related", "biometric"} & explicit_traits) and ({"health_related", "biometric"} & traits):
        score += 10
        reasons.append("health or biometric wording fits")
    if "scanner" in text and {"professional", "handheld", "av_ict"} & traits:
        score += 8
        reasons.append("scanner wording fits")
    if "robot" in text and "robot" in pid:
        score += 10
        reasons.append("robot wording fits")
    if ({"cloud", "app_control", "ota"} & explicit_traits) and ({"wifi", "bluetooth", "thread", "zigbee", "matter", "radio"} & traits):
        score += 10
        reasons.append("connected context fits")
    if ({"app_control", "cloud", "bluetooth", "wifi"} & explicit_traits) and ({"personal_care", "hair_care", "oral_care"} & traits):
        score += 8
        reasons.append("connected personal-care context fits")

    return score, reasons

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

def _contradiction_severity(contradictions: list[str]) -> str:
    if not contradictions:
        return "none"
    if any("ambiguous" in item.lower() for item in contradictions):
        return "high"
    if len(contradictions) >= 2:
        return "high"
    return "medium"

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

def _common_sets(rows: list[dict[str, Any]], field: str) -> set[str]:
    if not rows:
        return set()
    common = set(_string_list(rows[0].get(field)))
    for row in rows[1:]:
        common &= set(_string_list(row.get(field)))
    return common


def reset_scoring_cache() -> None:
    _PHRASE_PATTERN_CACHE.clear()
    _ALIAS_PATTERN_CACHE.clear()


__all__ = [
    "ALIAS_FIELD_BONUS",
    "CONNECTED_TRAITS",
    "ELECTRONIC_SIGNAL_TRAITS",
    "ENGINE_VERSION",
    "GENERIC_ALIASES",
    "POWER_TRAITS",
    "RADIO_TRAITS",
    "SERVICE_DEPENDENT_TRAITS",
    "_alias_score",
    "_alias_specificity_bonus",
    "_candidate_confidence",
    "_candidate_confidence_v2",
    "_common_sets",
    "_common_strings",
    "_context_bonus",
    "_contradiction_severity",
    "_family_confidence",
    "_matching_clues",
    "_phrase_present",
    "_product_family",
    "_product_subfamily",
    "_string_list",
    "_trait_overlap_score",
    "reset_scoring_cache",
]
