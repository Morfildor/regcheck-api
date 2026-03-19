import re
from knowledge_base import load_products


def normalize(text: str) -> str:
    text = text.lower()
    text = text.replace("wi-fi", "wifi")
    text = text.replace("bluetooth low energy", "bluetooth")
    text = text.replace("over-the-air", "ota")
    return text


def extract_traits(description: str, category: str = "") -> dict:
    text = normalize(f"{category} {description}")
    explicit_traits = set()
    inferred_traits = set()
    functional_classes = set()
    contradictions = []
    product_type = None

    if re.search(r"\bbluetooth\b|\bble\b", text):
        explicit_traits.update(["radio", "bluetooth"])

    if re.search(r"\bwifi\b|\b802\.11\b|\bwlan\b", text):
        explicit_traits.update(["radio", "wifi"])

    if re.search(r"\bapp\b|\bmobile app\b|\bcompanion app\b", text):
        explicit_traits.add("app_control")

    if re.search(r"\bcloud\b|\baws\b|\bazure\b|\bbackend\b|\bserver\b", text):
        explicit_traits.update(["cloud", "internet"])

    if re.search(r"\boffline\b|\bno cloud\b|\bno internet\b|\blocal only\b", text):
        explicit_traits.add("local_only")

    products = load_products()
    for product in products:
        for alias in product.get("aliases", []):
            pattern = r"\b" + re.escape(alias.lower()) + r"\b"
            if re.search(pattern, text):
                product_type = product["id"]
                inferred_traits.update(product.get("implied_traits", []))
                functional_classes.update(product.get("functional_classes", []))
                break
        if product_type:
            break

    return {
        "product_type": product_type,
        "functional_classes": sorted(functional_classes),
        "explicit_traits": sorted(explicit_traits),
        "inferred_traits": sorted(inferred_traits),
        "all_traits": sorted(explicit_traits | inferred_traits),
        "contradictions": contradictions,
    }