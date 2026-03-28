from __future__ import annotations

import re
from typing import Any

from .gating import (
    ProductHitType,
    TraitGate,
    _standard_item_type,
    _string_list,
)



BASE_STANDARD_PRIORITY = {
    "EN 60335-1": 260,
    "EN 60335-2": 240,
    "EN 55014-1": 220,
    "EN 55014-2": 215,
    "EN 61000-3-2": 210,
    "EN 61000-3-3": 205,
    "EN 61000-3-11": 200,
    "EN 300 328": 190,
    "EN 301 489-1": 185,
    "EN 301 489-17": 180,
    "EN 301 893": 175,
    "EN 62311": 170,
    "EN 62479": 165,
    "EN 62209-1528": 160,
    "EN 18031-1": 150,
    "EN 18031-2": 145,
    "EN 18031-3": 140,
    "EN 63000": 130,
}


def _priority_bonus(standard: dict[str, Any]) -> int:
    code = str(standard.get("code", "")).upper()
    for prefix, bonus in BASE_STANDARD_PRIORITY.items():
        if code.startswith(prefix):
            return bonus
    item_type = _standard_item_type(standard)
    return 100 if item_type == "standard" else 30


def _score_standard(
    standard: dict[str, Any],
    gate: TraitGate,
    product_hit_type: ProductHitType | None,
    is_preferred: bool,
) -> int:
    score = _priority_bonus(standard)

    if product_hit_type == "primary_product":
        score += 300
    elif product_hit_type == "alternate_product":
        score += 220
    elif product_hit_type == "primary_genre":
        score += 150

    if is_preferred:
        score += 80

    score += len(gate["confirmed_traits_all"]) * 40
    score += len(gate["confirmed_traits_any"]) * 18
    score += (len(gate["matched_traits_all"]) - len(gate["confirmed_traits_all"])) * 16
    score += (len(gate["matched_traits_any"]) - len(gate["confirmed_traits_any"])) * 8

    if gate["soft_missing_any"]:
        score -= 20
    if gate["soft_inferred_match"]:
        score -= 35

    if _standard_item_type(standard) == "standard":
        score += 40
    else:
        score -= 10

    confidence = standard.get("confidence", "medium")
    if confidence == "high":
        score += 20
    elif confidence == "low":
        score -= 5

    harmonization_status = standard.get("harmonization_status")
    if harmonization_status == "harmonized":
        score += 25
    elif harmonization_status == "state_of_the_art":
        score += 10
    elif harmonization_status == "review":
        score -= 5

    return score

BASE_STANDARD_PRIORITY_V2 = {
    "EN 14846": 220,
    "EN 12209": 205,
    "EN 60335-1": 155,
    "EN 60335-2": 175,
    "EN 60730-1": 210,
    "EN 60730-2-9": 225,
    "EN IEC 61851-1": 230,
    "EN IEC 61851-21-2": 220,
    "EN 62196-2": 210,
    "EN IEC 62560": 220,
    "EN 62031": 195,
    "EN 55014-1": 145,
    "EN 55014-2": 140,
    "EN 55032": 145,
    "EN 55035": 140,
    "EN 62368-1": 155,
    "EN 14604": 220,
    "EN 50291-1": 215,
    "EN 62841-1": 225,
    "EN 62841-2-1": 235,
    "EN 62311": 130,
    "EN 62479": 125,
    "EN 62209": 150,
    "EN 50566": 145,
    "EN 18031-": 150,
    "EN 300 328": 155,
    "EN 301 489-1": 145,
    "EN 301 489-17": 140,
    "EN 301 893": 140,
    "EN 63000": 120,
}

def _keyword_hits(standard: dict[str, Any], normalized_text: str) -> list[str]:
    hits: list[str] = []
    if not normalized_text:
        return hits
    text_terms = set(normalized_text.split())
    for keyword in _string_list(standard.get("keywords")):
        phrase = " ".join(str(keyword).lower().split())
        if phrase and phrase in normalized_text:
            hits.append(keyword)
            continue
        keyword_terms = [part for part in re.split(r"[^a-z0-9]+", phrase) if part]
        if len(keyword_terms) > 1 and all(term in text_terms for term in keyword_terms):
            hits.append(keyword)
    return hits


def _priority_bonus_v2(standard: dict[str, Any]) -> int:
    code = str(standard.get("code", "")).upper()
    for prefix, bonus in BASE_STANDARD_PRIORITY_V2.items():
        if code.startswith(prefix):
            return bonus
    return 95 if _standard_item_type(standard) == "standard" else 45


def _context_bonus_v2(standard: dict[str, Any], context_tags: set[str]) -> int:
    code = str(standard.get("code", ""))
    bonus = 0
    if "scope:av_ict" in context_tags and (code == "EN 62368-1" or code in {"EN 55032", "EN 55035"}):
        bonus += 80
    if "scope:av_ict" in context_tags and (code.startswith("EN 60335-") or code.startswith("EN 55014-")):
        bonus -= 90
    if "scope:appliance" in context_tags and (code.startswith("EN 60335-") or code.startswith("EN 55014-")):
        bonus += 80
    if "scope:appliance" in context_tags and (code == "EN 62368-1" or code in {"EN 55032", "EN 55035"}):
        bonus -= 110
    if "exposure:close_proximity" in context_tags and (
        code.startswith("EN 62209") or code in {"EN 50566", "EN 50663 / EN 62311 review", "EN 50665"}
    ):
        bonus += 70
    if "exposure:household_emf" in context_tags and code == "EN 62233":
        bonus += 45
    if "optical:laser" in context_tags and code == "EN 60825-1":
        bonus += 35
    if "optical:photobio" in context_tags and code == "EN 62471":
        bonus += 30
    if "power:external_psu" in context_tags and code == "EN 50563":
        bonus += 35
    if "power:external_psu" not in context_tags and code == "EN 50563":
        bonus -= 40
    if "power:portable_battery" in context_tags and code in {"EN 62133-2", "Battery safety review", "UN 38.3 review"}:
        bonus += 40
    if "contact:skin" in context_tags and code == "Biocompatibility / skin-contact review":
        bonus += 85
    if "data:personal_or_health" in context_tags and code in {"EN 18031-2", "GDPR review"}:
        bonus += 60
    if "cyber:connected_radio" in context_tags and code in {"EN 18031-1", "CRA review"}:
        bonus += 45
    if "boundary:medical_wellness" in context_tags and code == "MDR borderline review":
        bonus += 75
    if "primary:building_hardware" in context_tags:
        if code == "EN 14846":
            bonus += 230
        elif code == "EN 12209":
            bonus += 180
        elif code == "EN 62368-1" or code.startswith("EN 60335-") or code.startswith("EN 55014-") or code in {"EN 55032", "EN 55035"}:
            bonus -= 220
    if "primary:lighting_device" in context_tags:
        if code == "EN IEC 62560":
            bonus += 230
        elif code == "EN 62031":
            bonus += 180
        elif code == "EN 62368-1" or code.startswith("EN 60335-") or code.startswith("EN 55014-") or code in {"EN 55032", "EN 55035"}:
            bonus -= 220
    if "primary:life_safety_alarm" in context_tags:
        if code == "EN 14604":
            bonus += 230
        elif code == "EN 50291-1":
            bonus += 180
        elif code == "EN 62368-1" or code.startswith("EN 60335-") or code.startswith("EN 55014-") or code in {"EN 55032", "EN 55035"}:
            bonus -= 220
    if "primary:hvac_control" in context_tags:
        if code == "EN 60730-2-9":
            bonus += 230
        elif code == "EN 60730-1":
            bonus += 180
        elif code == "EN 62368-1" or code.startswith("EN 60335-") or code.startswith("EN 55014-") or code in {"EN 55032", "EN 55035"}:
            bonus -= 220
    if "primary:ev_charging" in context_tags:
        if code == "EN IEC 61851-1":
            bonus += 240
        elif code == "EN IEC 61851-21-2":
            bonus += 215
        elif code in {"EN 62196-2", "IEC 62752"}:
            bonus += 180
        elif code == "EN 62368-1" or code.startswith("EN 60335-") or code.startswith("EN 55014-") or code in {"EN 55032", "EN 55035"}:
            bonus -= 230
    if "primary:machinery_power_tool" in context_tags:
        if code == "EN 62841-2-1":
            bonus += 240
        elif code == "EN 62841-1":
            bonus += 200
        elif code == "Power tool safety review":
            bonus += 80
        elif code == "EN 62368-1" or code.startswith("EN 60335-") or code.startswith("EN 55014-") or code in {"EN 55032", "EN 55035"}:
            bonus -= 230
    if "primary:toy" in context_tags:
        if code == "EN 62115":
            bonus += 220
        elif code == "EN 71 review":
            bonus += 160
        elif code == "EN 62368-1":
            bonus -= 220
    return bonus


def _score_standard_v2(
    standard: dict[str, Any],
    gate: TraitGate,
    product_hit_type: ProductHitType | None,
    is_preferred: bool,
    keyword_hits: list[str],
    context_tags: set[str],
) -> int:
    score = _priority_bonus_v2(standard)

    if product_hit_type == "primary_product":
        score += 135
    elif product_hit_type == "alternate_product":
        score += 85
    elif product_hit_type == "primary_genre":
        score += 55
    if is_preferred:
        score += 65

    score += len(gate["confirmed_traits_all"]) * 34
    score += len(gate["confirmed_traits_any"]) * 16
    score += (len(gate["matched_traits_all"]) - len(gate["confirmed_traits_all"])) * 12
    score += (len(gate["matched_traits_any"]) - len(gate["confirmed_traits_any"])) * 6
    score += len(keyword_hits) * 16
    score += int(standard.get("selection_priority") or 0) * 2
    score += _context_bonus_v2(standard, context_tags)

    if gate["soft_missing_any"]:
        score -= 18
    if gate["soft_inferred_match"]:
        score -= 28

    confidence = standard.get("confidence", "medium")
    if confidence == "high":
        score += 18
    elif confidence == "low":
        score -= 8

    harmonization_status = standard.get("harmonization_status")
    if harmonization_status == "harmonized":
        score += 24
    elif harmonization_status == "state_of_the_art":
        score += 12
    elif harmonization_status == "review":
        score -= 10

    return score


__all__ = [
    "BASE_STANDARD_PRIORITY",
    "BASE_STANDARD_PRIORITY_V2",
    "_context_bonus_v2",
    "_keyword_hits",
    "_priority_bonus",
    "_priority_bonus_v2",
    "_score_standard",
    "_score_standard_v2",
]
