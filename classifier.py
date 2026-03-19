import re
from typing import Any

from knowledge_base import load_products


def normalize(text: str) -> str:
    text = text.lower()
    replacements = {
        "wi-fi": "wifi",
        "wlan": "wifi",
        "bluetooth low energy": "bluetooth",
        "ble": "bluetooth",
        "over-the-air": "ota",
        "over the air": "ota",
        "multi-cooker": "multicooker",
        "bean-to-cup": "bean to cup",
    }
    for old, new in replacements.items():
        text = text.replace(old, new)
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _add_regex_trait(text: str, explicit_traits: set[str]) -> None:
    patterns = {
        "radio": [r"\bradio\b"],
        "bluetooth": [r"\bbluetooth\b"],
        "wifi": [r"\bwifi\b", r"\b802 11\b"],
        "zigbee": [r"\bzigbee\b"],
        "thread": [r"\bthread\b"],
        "matter": [r"\bmatter\b"],
        "nfc": [r"\bnfc\b"],
        "cellular": [r"\bcellular\b", r"\blte\b", r"\b4g\b", r"\b5g\b", r"\bgsm\b"],
        "app_control": [r"\bapp\b", r"\bmobile app\b", r"\bcompanion app\b"],
        "cloud": [r"\bcloud\b", r"\baws\b", r"\bazure\b", r"\bbackend\b", r"\bserver\b"],
        "internet": [r"\binternet\b", r"\bonline\b", r"\bremote access\b"],
        "local_only": [r"\boffline\b", r"\bno cloud\b", r"\bno internet\b", r"\blocal only\b"],
        "ota": [r"\bota\b", r"\bfirmware update\b", r"\bsoftware update\b"],
        "account": [r"\baccount\b", r"\blogin\b", r"\bsign in\b", r"\buser profile\b"],
        "authentication": [r"\bauthentication\b", r"\bpassword\b", r"\bpasscode\b", r"\bcredential\b"],
        "camera": [r"\bcamera\b"],
        "microphone": [r"\bmicrophone\b", r"\bmic\b", r"\bvoice\b"],
        "location": [r"\bgps\b", r"\bgnss\b", r"\blocation\b", r"\bgeolocation\b"],
        "battery_powered": [r"\bbattery\b", r"\brechargeable\b", r"\bcordless\b"],
        "usb_powered": [r"\busb\b", r"\busb c\b", r"\btype c\b"],
        "mains_powered": [r"\bmains\b", r"\b230v\b", r"\b220v\b", r"\b240v\b", r"\bac power\b", r"\bplug in\b"],
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
    exact_pattern = rf"(?<!\w){re.escape(alias_norm)}(?!\w)"
    if re.search(exact_pattern, text):
        score = len(alias_norm) * 10 + len(alias_norm.split()) * 25
        if alias_norm == text:
            score += 200
        return score

    tokens = alias_norm.split()
    if len(tokens) >= 2:
        gap_pattern = r"\b" + r"\b(?:\s+\w+){0,3}\s+\b".join(re.escape(t) for t in tokens) + r"\b"
        if re.search(gap_pattern, text):
            return len(alias_norm) * 8 + len(tokens) * 20

    return 0


def _product_candidates(text: str) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    for product in load_products():
        best_alias = None
        best_score = 0
        product_traits = set(product.get("implied_traits", []))
        for alias in product.get("aliases", []):
            score = _alias_score(text, alias)
            if score > 0:
                alias_norm = normalize(alias)
                if "robotic" in text and ("robotic" in alias_norm or "robotic" in product.get("id", "")):
                    score += 30
                if ("commercial" in text or "professional" in text) and ({"professional", "commercial_food_service"} & product_traits):
                    score += 25
                if "battery" in text and "battery_powered" in product_traits:
                    score += 10
                if "wifi" in text and "wifi" in product_traits:
                    score += 10
                if best_alias is None or score > best_score:
                    best_alias = alias
                    best_score = score
        if best_alias:
            candidates.append(
                {
                    "id": product["id"],
                    "label": product.get("label", product["id"]),
                    "score": best_score,
                    "matched_alias": best_alias,
                    "implied_traits": product.get("implied_traits", []),
                    "functional_classes": product.get("functional_classes", []),
                }
            )
    candidates.sort(key=lambda x: (-x["score"], x["id"]))
    return candidates


def extract_traits(description: str, category: str = "") -> dict:
    text = normalize(f"{category} {description}")
    explicit_traits: set[str] = set()
    inferred_traits: set[str] = set()
    functional_classes: set[str] = set()
    contradictions: list[str] = []

    _add_regex_trait(text, explicit_traits)

    candidates = _product_candidates(text)
    product_type = None
    matched_products: list[str] = []
    product_match_confidence = "low"

    if candidates:
        top = candidates[0]
        product_type = top["id"]
        matched_products = [c["id"] for c in candidates]
        inferred_traits.update(top["implied_traits"])
        functional_classes.update(top["functional_classes"])

        if len(candidates) == 1:
            product_match_confidence = "high"
        else:
            gap = top["score"] - candidates[1]["score"]
            product_match_confidence = "high" if gap >= 40 else "medium"
            if gap < 40:
                contradictions.append(
                    "Ambiguous product identification between "
                    f"{top['id'].replace('_', ' ')} and {candidates[1]['id'].replace('_', ' ')}."
                )

    if "battery_powered" in explicit_traits and "mains_powered" in explicit_traits:
        contradictions.append("Both battery-powered and mains-powered signals were detected.")

    return {
        "product_type": product_type,
        "matched_products": matched_products,
        "product_match_confidence": product_match_confidence,
        "functional_classes": sorted(functional_classes),
        "explicit_traits": sorted(explicit_traits),
        "inferred_traits": sorted(inferred_traits),
        "all_traits": sorted(explicit_traits | inferred_traits),
        "contradictions": contradictions,
    }
