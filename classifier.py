from __future__ import annotations

import re
from typing import Any

from knowledge_base import load_products, load_traits

TRAIT_IDS_CACHE: set[str] | None = None


def normalize(text: str) -> str:
    text = (text or "").lower()
    replacements = {
        "wi-fi": "wifi",
        "wlan": "wifi",
        "bluetooth low energy": "bluetooth",
        "ble": "bluetooth",
        "over-the-air": "ota",
        "over the air": "ota",
        "multi-cooker": "multicooker",
        "bean-to-cup": "bean to cup",
        "air-conditioning": "air conditioner",
        "smart home": "smart_home",
    }
    for old, new in replacements.items():
        text = text.replace(old, new)
    text = re.sub(r"[^a-z0-9_]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _known_trait_ids() -> set[str]:
    global TRAIT_IDS_CACHE
    if TRAIT_IDS_CACHE is None:
        TRAIT_IDS_CACHE = {row["id"] for row in load_traits()}
    return TRAIT_IDS_CACHE


def _add_regex_trait(text: str, explicit_traits: set[str]) -> None:
    patterns = {
        "radio": [r"\bradio\b"],
        "bluetooth": [r"\bbluetooth\b"],
        "wifi": [r"\bwifi\b", r"\b802 11\b"],
        "zigbee": [r"\bzigbee\b"],
        "thread": [r"\bthread\b"],
        "matter": [r"\bmatter\b"],
        "nfc": [r"\bnfc\b"],
        "cellular": [r"\bcellular\b", r"\blte\b", r"\b4g\b", r"\b5g\b", r"\bgsm\b", r"\bsim\b"],
        "app_control": [r"\bapp\b", r"\bmobile app\b", r"\bcompanion app\b", r"\bsmartphone control\b"],
        "cloud": [r"\bcloud\b", r"\baws\b", r"\bazure\b", r"\bbackend\b", r"\bserver\b"],
        "internet": [r"\binternet\b", r"\bonline\b", r"\bremote access\b"],
        "local_only": [r"\boffline\b", r"\bno cloud\b", r"\bno internet\b", r"\blocal only\b"],
        "ota": [r"\bota\b", r"\bfirmware update\b", r"\bsoftware update\b", r"\bover the air\b"],
        "account": [r"\baccount\b", r"\blogin\b", r"\bsign in\b", r"\buser profile\b"],
        "authentication": [r"\bauthentication\b", r"\bpassword\b", r"\bpasscode\b", r"\bcredential\b", r"\bpin\b"],
        "camera": [r"\bcamera\b"],
        "microphone": [r"\bmicrophone\b", r"\bmic\b", r"\bvoice\b"],
        "location": [r"\bgps\b", r"\bgnss\b", r"\blocation\b", r"\bgeolocation\b"],
        "battery_powered": [r"\bbattery\b", r"\brechargeable\b", r"\bcordless\b"],
        "usb_powered": [r"\busb\b", r"\busb c\b", r"\btype c\b"],
        "mains_powered": [r"\bmains\b", r"\b230v\b", r"\b220v\b", r"\b240v\b", r"\bac power\b", r"\bplug in\b"],
        "professional": [r"\bprofessional\b", r"\bcommercial\b", r"\bindustrial\b", r"\bcatering\b", r"\bhoreca\b"],
        "consumer": [r"\bconsumer\b", r"\bdomestic\b", r"\bhousehold\b", r"\bhome use\b"],
        "household": [r"\bhousehold\b", r"\bdomestic\b", r"\bhome use\b"],
        "outdoor_use": [r"\boutdoor\b", r"\bgarden\b", r"\blawn\b"],
        "fixed_installation": [r"\bbuilt in\b", r"\bfixed\b", r"\bwall mounted\b", r"\bceiling mounted\b", r"\bpermanently installed\b"],
        "portable": [r"\bportable\b", r"\btravel\b"],
        "water_contact": [r"\bwater\b", r"\bliquid\b", r"\bsteam\b"],
        "heating": [r"\bheating\b", r"\bheater\b", r"\bhot\b", r"\bboil\b", r"\bbrew\b", r"\bsteam\b"],
        "cooling": [r"\bcooling\b", r"\brefrigerat", r"\bfreezer\b", r"\bice\b", r"\bchill\b"],
        "motorized": [r"\bmotor\b", r"\bfan\b", r"\bpump\b", r"\bcompressor\b", r"\bdrive\b"],
        "remote_control": [r"\bremote control\b", r"\bremote start\b", r"\bremote operation\b"],
        "ai_related": [r"\bai\b", r"\bmachine learning\b", r"\bneural\b", r"\bmodel\b", r"\bllm\b"],
        "personal_data_likely": [r"\bpersonal data\b", r"\bprofile\b", r"\buser data\b", r"\baccount\b", r"\blogin\b"],
        "food_contact": [r"\bfood\b", r"\bdrink\b", r"\bwater tank\b", r"\bbrew\b", r"\bcook\b"],
    }

    for trait, regexes in patterns.items():
        if any(re.search(rx, text) for rx in regexes):
            explicit_traits.add(trait)

    if any(t in explicit_traits for t in ["bluetooth", "wifi", "zigbee", "thread", "matter", "nfc", "cellular"]):
        explicit_traits.add("radio")
    if "cloud" in explicit_traits:
        explicit_traits.add("internet")


def _alias_score(text: str, alias: str) -> int:
    alias_norm = normalize(alias)
    if not alias_norm:
        return 0

    exact_pattern = rf"(?<!\w){re.escape(alias_norm)}(?!\w)"
    if re.search(exact_pattern, text):
        score = 100 + len(alias_norm) * 3 + len(alias_norm.split()) * 20
        if alias_norm == text:
            score += 80
        return score

    tokens = alias_norm.split()
    if len(tokens) >= 2:
        if all(token in text.split() for token in tokens):
            return 45 + len(tokens) * 10

        gap_pattern = r"\b" + r"\b(?:\s+\w+){0,2}\s+\b".join(re.escape(t) for t in tokens) + r"\b"
        if re.search(gap_pattern, text):
            return 35 + len(tokens) * 8

    return 0


def _trait_overlap_score(explicit_traits: set[str], product_traits: set[str]) -> int:
    strong_overlap = explicit_traits & product_traits
    return len(strong_overlap) * 6


def _context_bonus(text: str, product: dict[str, Any], explicit_traits: set[str]) -> tuple[int, list[str]]:
    score = 0
    reasons: list[str] = []
    pid = product["id"]
    traits = set(product.get("implied_traits", []))

    if "commercial" in text or "professional" in text:
        if "professional" in traits or "commercial_food_service" in traits:
            score += 20
            reasons.append("commercial/professional context fits")
        elif "consumer" in traits or "household" in traits:
            score -= 15
            reasons.append("consumer product conflicts with commercial wording")

    if "household" in text or "domestic" in text or "home use" in text:
        if "consumer" in traits or "household" in traits:
            score += 15
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
    if "built in" in text and "fixed_installation" in traits:
        score += 8
        reasons.append("built-in wording fits")
    if "portable" in text and "portable" in traits:
        score += 6
        reasons.append("portable wording fits")
    if "robot" in text and "robot" in pid:
        score += 10
        reasons.append("robot wording fits")

    return score, reasons


def _product_candidates(text: str, explicit_traits: set[str]) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    for product in load_products():
        best_alias = None
        best_score = 0
        best_reasons: list[str] = []
        product_traits = set(product.get("implied_traits", []))

        for alias in product.get("aliases", []):
            score = _alias_score(text, alias)
            if score <= 0:
                continue

            reasons = [f"matched alias '{alias}'"]
            overlap = _trait_overlap_score(explicit_traits, product_traits)
            if overlap:
                score += overlap
                reasons.append(f"trait overlap +{overlap}")

            bonus, bonus_reasons = _context_bonus(text, product, explicit_traits)
            score += bonus
            reasons.extend(bonus_reasons)

            if best_alias is None or score > best_score:
                best_alias = alias
                best_score = score
                best_reasons = reasons

        if best_alias:
            candidates.append(
                {
                    "id": product["id"],
                    "label": product.get("label", product["id"]),
                    "score": best_score,
                    "matched_alias": best_alias,
                    "reasons": best_reasons,
                    "implied_traits": product.get("implied_traits", []),
                    "functional_classes": product.get("functional_classes", []),
                    "likely_standards": product.get("likely_standards", []),
                }
            )

    candidates.sort(key=lambda x: (-x["score"], x["id"]))
    return candidates


def _candidate_confidence(index: int, candidate: dict[str, Any], next_candidate: dict[str, Any] | None) -> str:
    score = candidate["score"]
    gap = score - next_candidate["score"] if next_candidate else score

    if index == 0 and score >= 150 and gap >= 25:
        return "high"
    if index == 0 and score >= 110 and gap >= 10:
        return "medium"
    if score >= 90:
        return "medium"
    return "low"


def _contradiction_severity(contradictions: list[str]) -> str:
    if not contradictions:
        return "none"
    if any("ambiguous" in item.lower() for item in contradictions):
        return "high"
    if len(contradictions) >= 2:
        return "high"
    return "medium"


def extract_traits(description: str, category: str = "") -> dict:
    text = normalize(f"{category} {description}")
    explicit_traits: set[str] = set()
    inferred_traits: set[str] = set()
    functional_classes: set[str] = set()
    contradictions: list[str] = []
    diagnostics: list[str] = []

    _add_regex_trait(text, explicit_traits)
    diagnostics.append(f"normalized_text={text}")

    candidates = _product_candidates(text, explicit_traits)
    top_candidates = candidates[:5]

    product_type = None
    product_match_confidence = "low"
    matched_products: list[str] = []
    product_candidates: list[dict[str, Any]] = []

    for idx, candidate in enumerate(top_candidates):
        confidence = _candidate_confidence(idx, candidate, top_candidates[idx + 1] if idx + 1 < len(top_candidates) else None)
        item = {
            "id": candidate["id"],
            "label": candidate["label"],
            "matched_alias": candidate["matched_alias"],
            "score": candidate["score"],
            "confidence": confidence,
            "reasons": candidate["reasons"],
            "likely_standards": candidate.get("likely_standards", []),
        }
        product_candidates.append(item)
        matched_products.append(candidate["id"])

    if product_candidates:
        winner = product_candidates[0]
        product_type = winner["id"]
        product_match_confidence = winner["confidence"]
        diagnostics.append(f"product_winner={winner['id']}")
        diagnostics.append(f"product_alias={winner.get('matched_alias') or ''}")

        winner_full = top_candidates[0]
        inferred_traits.update(winner_full.get("implied_traits", []))
        functional_classes.update(winner_full.get("functional_classes", []))

        if len(product_candidates) > 1 and product_candidates[0]["score"] - product_candidates[1]["score"] < 15:
            contradictions.append(
                "Product identification is ambiguous between "
                f"{product_candidates[0]['id'].replace('_', ' ')} and "
                f"{product_candidates[1]['id'].replace('_', ' ')}."
            )
    else:
        diagnostics.append("product_winner=none")

    if "battery_powered" in explicit_traits and "mains_powered" in explicit_traits:
        contradictions.append("Both battery-powered and mains-powered signals were detected.")
    if "cloud" in explicit_traits and "local_only" in explicit_traits:
        contradictions.append("Both cloud-connected and local-only signals were detected.")
    if "professional" in explicit_traits and "household" in explicit_traits:
        contradictions.append("Both professional/commercial and household-use signals were detected.")

    known_traits = _known_trait_ids()
    explicit_traits = {t for t in explicit_traits if t in known_traits}
    inferred_traits = {t for t in inferred_traits if t in known_traits}

    diagnostics.append("explicit_traits=" + ",".join(sorted(explicit_traits)))
    diagnostics.append("inferred_traits=" + ",".join(sorted(inferred_traits)))
    diagnostics.append("contradiction_severity=" + _contradiction_severity(contradictions))

    return {
        "product_type": product_type,
        "matched_products": matched_products,
        "product_match_confidence": product_match_confidence,
        "product_candidates": product_candidates,
        "functional_classes": sorted(functional_classes),
        "explicit_traits": sorted(explicit_traits),
        "inferred_traits": sorted(inferred_traits),
        "all_traits": sorted(explicit_traits | inferred_traits),
        "contradictions": contradictions,
        "contradiction_severity": _contradiction_severity(contradictions),
        "diagnostics": diagnostics,
    }