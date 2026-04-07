from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypedDict, cast

from app.domain.catalog_types import StandardCatalogRow
from app.services.standard_codes import canonical_standard_code_set, canonicalize_standard_code

from .contracts import ApplicableItems, FactBasis, MatchBasis, ProductHitType, StandardAuditOutcome, StandardItemType
from .gating_finalize import _finalize_selected_rows_v2


DIRECTIVE_ORDER = {
    "LVD": 0,
    "EMC": 1,
    "RED": 2,
    "RED_CYBER": 3,
    "ROHS": 4,
    "REACH": 5,
    "GDPR": 6,
    "FCM": 7,
    "FCM_PLASTIC": 8,
    "BATTERY": 9,
    "GPSR": 10,
    "TOY": 11,
    "UAS": 12,
    "WEEE": 13,
    "ECO": 14,
    "ESPR": 15,
    "CRA": 16,
    "AI_Act": 17,
    "MDR": 18,
    "MD": 19,
    "MACH_REG": 20,
    "OTHER": 99,
}

StandardRowLike = StandardCatalogRow | Mapping[str, Any]


class TraitGate(TypedDict):
    passes: bool
    soft_missing_any: bool
    soft_inferred_match: bool
    matched_traits_all: list[str]
    matched_traits_any: list[str]
    confirmed_traits_all: list[str]
    confirmed_traits_any: list[str]
    missing_required_traits: list[str]
    missing_any_group: list[str]
    excluded_by_traits: list[str]
    fact_basis: FactBasis


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, str)]


def _primary_directive(standard: StandardRowLike) -> str:
    directives = _string_list(standard.get("directives"))
    if directives:
        return directives[0]
    legislation_key = standard.get("legislation_key")
    return legislation_key if isinstance(legislation_key, str) and legislation_key else "OTHER"


def _standard_item_type(standard: StandardRowLike) -> StandardItemType:
    item_type = standard.get("item_type")
    if item_type in {"standard", "review"}:
        return cast(StandardItemType, item_type)
    code = str(standard.get("code", "")).lower()
    title = str(standard.get("title", "")).lower()
    return "review" if "review" in code or "review" in title else "standard"


def _directive_sort_key(standard: StandardRowLike) -> tuple[int, str]:
    directive = _primary_directive(standard)
    return DIRECTIVE_ORDER.get(directive, 99), str(standard.get("code", ""))


def _product_hit_type(
    standard: StandardRowLike,
    product_type: str | None,
    matched_products: list[str] | None,
    product_genres: list[str] | None = None,
) -> ProductHitType | None:
    applies_if_products = set(_string_list(standard.get("applies_if_products")))
    exclude_if_products = set(_string_list(standard.get("exclude_if_products")))
    applies_if_genres = set(_string_list(standard.get("applies_if_genres")))
    exclude_if_genres = set(_string_list(standard.get("exclude_if_genres")))
    matched_products = matched_products or []
    product_genres = product_genres or []

    if product_type and product_type in exclude_if_products:
        return None
    if any(pid in exclude_if_products for pid in matched_products):
        return None
    if exclude_if_genres & set(product_genres):
        return None

    if product_type and product_type in applies_if_products:
        return "primary_product"

    if any(pid in applies_if_products for pid in matched_products):
        return "alternate_product"

    if applies_if_products:
        return None

    if not applies_if_genres:
        return "not_product_gated"

    if applies_if_genres & set(product_genres):
        if _is_subtype_specific_standard(standard) and not product_type and not applies_if_products:
            return None
        return "primary_genre"

    return None


def _normalize_selection_group(standard: StandardRowLike) -> str | None:
    selection_group = standard.get("selection_group")
    if isinstance(selection_group, str) and selection_group.strip():
        return selection_group.strip()

    code = str(standard.get("code", "")).upper()
    if code.startswith("EN 60335-2-"):
        return "lvd_household_part2"
    return None


def _is_subtype_specific_standard(standard: StandardRowLike) -> bool:
    code = str(standard.get("code", "")).upper()
    family = str(standard.get("standard_family", "")).upper()
    selection_group = _normalize_selection_group(standard)
    return code.startswith("EN 60335-2-") or family.startswith("EN 60335-2-") or selection_group == "lvd_household_part2"


def _is_exact_preferred_standard(standard: StandardRowLike, preferred_standard_codes: set[str]) -> bool:
    if not preferred_standard_codes:
        return False
    code = standard.get("code")
    return isinstance(code, str) and canonicalize_standard_code(code) in canonical_standard_code_set(preferred_standard_codes)


def _is_family_preferred_standard(standard: StandardRowLike, preferred_standard_codes: set[str]) -> bool:
    if not preferred_standard_codes:
        return False
    family = standard.get("standard_family")
    return isinstance(family, str) and canonicalize_standard_code(family) in canonical_standard_code_set(preferred_standard_codes)


def _is_preferred_standard(standard: StandardRowLike, preferred_standard_codes: set[str]) -> bool:
    return _is_exact_preferred_standard(standard, preferred_standard_codes) or _is_family_preferred_standard(
        standard, preferred_standard_codes
    )


def _has_household_part2_preference(preferred_standard_codes: set[str]) -> bool:
    return any(code.startswith("EN 60335-2-") for code in canonical_standard_code_set(preferred_standard_codes))


def _directive_review_fallback_allowed(
    standard: StandardRowLike,
    preferred_standard_codes: set[str],
    product_hit_type: ProductHitType | None,
) -> bool:
    code = str(standard.get("code", "")).upper()
    category = str(standard.get("category", "")).lower()

    if category != "safety":
        return False
    if code == "EN 60335-1" and _has_household_part2_preference(preferred_standard_codes):
        return True
    if code == "EN 62368-1":
        return True
    if _is_preferred_standard(standard, preferred_standard_codes):
        return True
    return product_hit_type in {"primary_product", "alternate_product", "primary_genre"} and code.startswith("EN 60335-2-")


def _trait_gate_details(
    standard: StandardRowLike,
    traits: set[str],
    confirmed_traits: set[str],
    allow_soft_any_miss: bool,
) -> TraitGate:
    applies_if_all = set(_string_list(standard.get("applies_if_all")))
    applies_if_any = set(_string_list(standard.get("applies_if_any")))
    exclude_if = set(_string_list(standard.get("exclude_if")))

    excluded_by_traits = sorted(exclude_if & traits)
    matched_traits_all = sorted(applies_if_all & traits)
    matched_traits_any = sorted(applies_if_any & traits)
    confirmed_traits_all = sorted(applies_if_all & confirmed_traits)
    confirmed_traits_any = sorted(applies_if_any & confirmed_traits)
    missing_required_traits = sorted(applies_if_all - traits)
    missing_any_group = sorted(applies_if_any) if applies_if_any and not matched_traits_any else []
    soft_missing_any = bool(missing_any_group and allow_soft_any_miss)

    soft_inferred_match = False
    if not missing_required_traits:
        inferred_only_required = bool(applies_if_all and not applies_if_all.issubset(confirmed_traits))
        inferred_only_any = bool(applies_if_any and matched_traits_any and not confirmed_traits_any)
        soft_inferred_match = inferred_only_required or inferred_only_any

    passes = not excluded_by_traits and not missing_required_traits and (not missing_any_group or soft_missing_any)

    fact_basis: FactBasis = "confirmed"
    if soft_inferred_match and (confirmed_traits_all or confirmed_traits_any):
        fact_basis = "mixed"
    elif soft_inferred_match:
        fact_basis = "inferred"

    return {
        "passes": passes,
        "soft_missing_any": soft_missing_any,
        "soft_inferred_match": soft_inferred_match,
        "matched_traits_all": matched_traits_all,
        "matched_traits_any": matched_traits_any,
        "confirmed_traits_all": confirmed_traits_all,
        "confirmed_traits_any": confirmed_traits_any,
        "missing_required_traits": missing_required_traits,
        "missing_any_group": missing_any_group,
        "excluded_by_traits": excluded_by_traits,
        "fact_basis": fact_basis,
    }


def _rejection_reason(product_hit_type: ProductHitType | None, gate: TraitGate) -> str:
    if product_hit_type is None:
        return "product gating failed"
    if gate["excluded_by_traits"]:
        return "excluded by traits: " + ", ".join(gate["excluded_by_traits"])
    if gate["missing_required_traits"]:
        return "missing required traits: " + ", ".join(gate["missing_required_traits"])
    if gate["missing_any_group"]:
        return "missing one-of traits: " + ", ".join(gate["missing_any_group"])
    return "not applicable"


def _build_reason(
    standard: StandardRowLike,
    product_type: str | None,
    matched_products: list[str],
    product_genres: list[str],
    product_hit_type: ProductHitType | None,
    gate: TraitGate,
    is_preferred: bool,
) -> tuple[str, MatchBasis]:
    parts: list[str] = []
    match_basis: MatchBasis = "traits"

    if product_hit_type == "primary_product" and product_type:
        parts.append(f"exact product match: {product_type.replace('_', ' ')}")
        match_basis = "product"
    elif product_hit_type == "alternate_product":
        applies_if_products = set(_string_list(standard.get("applies_if_products")))
        alternate_products = [pid for pid in matched_products if pid in applies_if_products] or matched_products
        matched_list = ", ".join(pid.replace("_", " ") for pid in alternate_products)
        parts.append(f"matched through alternate detected product candidate: {matched_list}")
        match_basis = "alternate_product"
    elif product_hit_type == "primary_genre":
        applies_if_genres = set(_string_list(standard.get("applies_if_genres")))
        matched_genres = [gid for gid in product_genres if gid in applies_if_genres] or sorted(applies_if_genres)
        matched_list = ", ".join(gid.replace("_", " ") for gid in matched_genres)
        parts.append(f"matched genre route: {matched_list}")
        match_basis = "genre"
    elif is_preferred:
        parts.append("recommended by the matched product knowledge base")
        match_basis = "preferred_product"

    matched_all = gate["matched_traits_all"]
    matched_any = gate["matched_traits_any"]
    if matched_all:
        parts.append("required traits matched: " + ", ".join(matched_all))
    if matched_any:
        parts.append("additional traits matched: " + ", ".join(matched_any))
    if gate["soft_inferred_match"]:
        parts.append("some routing traits are inferred from product context and still need confirmation")
    if gate["soft_missing_any"]:
        parts.append("product context suggests relevance but the feature-specific trigger still needs confirmation")

    notes = standard.get("notes")
    if isinstance(notes, str) and notes:
        parts.append(notes)

    return ". ".join(parts), match_basis

FACT_BASIS_RANK: dict[FactBasis, int] = {"inferred": 0, "mixed": 1, "confirmed": 2}

RADIO_EXPLICIT_TRAITS = {"wifi", "bluetooth", "zigbee", "thread", "matter", "nfc", "cellular", "dect", "radio"}
ELECTRICAL_EXPLICIT_TRAITS = {
    "electrical",
    "electronic",
    "radio",
    "av_ict",
    "heating",
    "motorized",
    "camera",
    "display",
    "microphone",
    "speaker",
    "mains_powered",
    "mains_power_likely",
    "battery_powered",
    "usb_powered",
    "poe_powered",
    "poe_supply",
    "backup_battery",
    "ev_charging",
    "vehicle_supply",
    "wireless_charging_rx",
    "wireless_charging_tx",
}
ELECTRONIC_EXPLICIT_TRAITS = {
    "electronic",
    "av_ict",
    "radio",
    "camera",
    "display",
    "microphone",
    "speaker",
    "data_storage",
    "ota",
    "cloud",
    "app_control",
    "wifi",
    "bluetooth",
    "zigbee",
    "thread",
    "matter",
    "cellular",
    "nfc",
    "dect",
}

SMALL_SMART_DEVICE_GENRES = {
    "smart_home_iot",
    "security_access_iot",
    "pet_tech",
}

EN62368_FALLBACK_EXCLUDED_TRAITS = {
    "air_treatment",
    "water_contact",
}

def _baseline_confirmed_traits(explicit_traits: set[str]) -> set[str]:
    confirmed: set[str] = set()
    if explicit_traits & RADIO_EXPLICIT_TRAITS:
        confirmed.add("radio")
    if explicit_traits & ELECTRICAL_EXPLICIT_TRAITS:
        confirmed.add("electrical")
    if explicit_traits & ELECTRONIC_EXPLICIT_TRAITS:
        confirmed.add("electronic")
    if "wifi" in explicit_traits and ({"cloud", "ota", "account", "authentication", "app_control"} & explicit_traits):
        confirmed.add("internet")
    if "cellular" in explicit_traits:
        confirmed.add("internet")
    if "battery_powered" in explicit_traits:
        confirmed.add("portable")
    if "food_contact" in explicit_traits:
        confirmed.add("consumer")
    return confirmed


def _has_small_smart_62368_preference(preferred_standard_codes: set[str], product_genres: list[str]) -> bool:
    if "EN 62368-1" not in canonical_standard_code_set(preferred_standard_codes):
        return False
    return bool(set(product_genres) & SMALL_SMART_DEVICE_GENRES)


def _soften_preferred_62368_gate(
    standard: StandardRowLike,
    gate: TraitGate,
    preferred_standard_codes: set[str],
    product_genres: list[str],
) -> tuple[TraitGate, str | None]:
    code = str(standard.get("code", ""))
    excluded_by_traits = set(gate["excluded_by_traits"])
    if code != "EN 62368-1":
        return gate, None
    if gate["passes"]:
        return gate, None
    if not _has_small_smart_62368_preference(preferred_standard_codes, product_genres):
        return gate, None
    if not excluded_by_traits or not excluded_by_traits.issubset(EN62368_FALLBACK_EXCLUDED_TRAITS):
        return gate, None

    softened_gate = dict(gate)
    softened_gate["passes"] = True
    softened_gate["excluded_by_traits"] = []
    softened_gate["soft_inferred_match"] = True
    softened_gate["fact_basis"] = "inferred"
    reason = (
        "retained as a review route because EN 62368-1 is explicitly preferred for a small smart-device "
        "product and the blocking trait is appliance-adjacent"
    )
    return cast(TraitGate, softened_gate), reason


def _recover_preferred_62368_group_loser(
    row: StandardCatalogRow,
    preferred_standard_codes: set[str],
    product_genres: list[str],
) -> bool:
    if str(row.get("code", "")) != "EN 62368-1":
        return False
    if str(row.get("selection_group", "")) != "lvd_primary_safety":
        return False
    return _has_small_smart_62368_preference(preferred_standard_codes, product_genres)


def _fact_basis_satisfies(required: FactBasis, actual: FactBasis) -> bool:
    return FACT_BASIS_RANK[actual] >= FACT_BASIS_RANK[required]

__all__ = [
    "ApplicableItems",
    "DIRECTIVE_ORDER",
    "FACT_BASIS_RANK",
    "FactBasis",
    "MatchBasis",
    "ProductHitType",
    "StandardAuditOutcome",
    "StandardItemType",
    "TraitGate",
    "_baseline_confirmed_traits",
    "_build_reason",
    "_directive_review_fallback_allowed",
    "_directive_sort_key",
    "_fact_basis_satisfies",
    "_finalize_selected_rows_v2",
    "_has_household_part2_preference",
    "_normalize_selection_group",
    "_product_hit_type",
    "_primary_directive",
    "_recover_preferred_62368_group_loser",
    "_rejection_reason",
    "_soften_preferred_62368_gate",
    "_standard_item_type",
    "_string_list",
    "_trait_gate_details",
]
