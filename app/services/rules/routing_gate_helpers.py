from __future__ import annotations

from collections.abc import Callable

from app.domain.catalog_types import StandardCatalogRow
from app.services.standards_engine.contracts import SelectionContext


def _gate_per_item(
    item: StandardCatalogRow,
    context: SelectionContext,
    traits: set[str],
    allowed_directives: set[str],
    product_genres: set[str] | None,
    preferred_standard_codes: set[str] | None,
    diagnostics: list[str],
    *,
    keep_preferred_62368_review_in_appliance_scope: Callable[[StandardCatalogRow, set[str] | None, set[str] | None], bool],
) -> StandardCatalogRow | None:
    code = item.code
    route = str(item.get("directive") or item.get("legislation_key") or "OTHER")

    if code in {"EN 55032", "EN 55035"} and context.scope_route == "appliance":
        diagnostics.append(f"gate=drop_{code}:appliance_primary")
        return None

    if code == "EN 62368-1" and context.scope_route == "appliance":
        if keep_preferred_62368_review_in_appliance_scope(item, product_genres, preferred_standard_codes):
            diagnostics.append("gate=keep_EN62368-1:preferred_small_smart_review")
        else:
            diagnostics.append("gate=drop_EN62368-1:appliance_primary")
            return None

    if code.startswith("EN 60335-") and context.scope_route == "av_ict":
        diagnostics.append(f"gate=drop_{code}:av_ict_primary")
        return None

    if code.startswith("EN 55014-") and context.scope_route == "av_ict":
        diagnostics.append(f"gate=drop_{code}:av_ict_primary")
        return None

    if code == "Charger / external PSU review":
        if route == "EMC":
            diagnostics.append("gate=drop_external_psu_from_emc")
            return None
        if not context.has_external_psu:
            diagnostics.append("gate=drop_external_psu_review:no_external_psu_signal")
            return None
        item = item.model_copy(update={"directive": "LVD", "legislation_key": "LVD"})
    elif code == "EN 50563":
        if not context.has_external_psu:
            diagnostics.append("gate=drop_EN50563:no_external_psu_signal")
            return None
        item = item.model_copy(update={"directive": "ECO", "legislation_key": "ECO"})

    if code == "EN 62311":
        if context.prefer_62233 and not ("radio" in traits and ({"wearable", "handheld", "body_worn_or_applied"} & traits)):
            diagnostics.append("gate=drop_EN62311:prefer_EN62233")
            return None
        directive = "RED" if "radio" in traits else "LVD"
        item = item.model_copy(update={"directive": directive, "legislation_key": directive})

    if code == "EN 62479":
        if "radio" not in traits:
            diagnostics.append("gate=drop_EN62479:no_radio_signal")
            return None
        if context.prefer_specific_red_emf:
            diagnostics.append("gate=drop_EN62479:prefer_specific_red_emf_route")
            return None

    if code.startswith("EN 62209") and not (
        "radio" in traits and ({"wearable", "handheld", "body_worn_or_applied", "cellular"} & traits)
    ):
        diagnostics.append(f"gate=drop_{code}:not_close_proximity_radio")
        return None

    if code == "EN 60825-1" and not context.has_laser_source:
        diagnostics.append("gate=drop_EN60825-1:no_laser_source")
        return None

    if code == "EN 62471" and not context.has_photobiological_source:
        diagnostics.append("gate=drop_EN62471:no_photobiological_source")
        return None

    effective_route = str(item.get("directive") or "OTHER")
    if effective_route not in allowed_directives and effective_route != "OTHER":
        diagnostics.append(f"gate=drop_{code}:directive_{effective_route}_not_selected")
        return None

    return item


def _promote_household_part1(kept: list[StandardCatalogRow], diagnostics: list[str]) -> list[StandardCatalogRow]:
    household_part2_selected = any(item.code.startswith("EN 60335-2-") and item.get("item_type") == "standard" for item in kept)
    if not household_part2_selected:
        return kept
    updated: list[StandardCatalogRow] = []
    for item in kept:
        if item.code != "EN 60335-1" or item.get("item_type") != "review":
            updated.append(item)
            continue
        reason = item.get("reason")
        if isinstance(reason, str):
            reason = reason.replace(
                ". some routing traits are inferred from product context and still need confirmation",
                "",
            )
        updated.append(item.model_copy(update={"item_type": "standard", "fact_basis": "confirmed", "reason": reason}))
        diagnostics.append("gate=promote_EN60335-1:paired_with_household_part2")
    return updated


def _prune_emf_duplicate(
    kept: list[StandardCatalogRow],
    context: SelectionContext,
    diagnostics: list[str],
) -> list[StandardCatalogRow]:
    codes = {item.code for item in kept}
    if "EN 62233" not in codes or "EN 62311" not in codes:
        return kept
    if context.prefer_62233:
        diagnostics.append("gate=prune_EN62311_after_pairing")
        return [item for item in kept if item.code != "EN 62311"]
    if context.prefer_62311:
        diagnostics.append("gate=prune_EN62233_after_pairing")
        return [item for item in kept if item.code != "EN 62233"]
    return kept


def _prune_battery_safety_review(
    kept: list[StandardCatalogRow],
    context: SelectionContext,
    traits: set[str],
    diagnostics: list[str],
) -> list[StandardCatalogRow]:
    codes = {item.code for item in kept}
    if (
        "Battery safety review" in codes
        and "EN 62133-2" in codes
        and context.scope_route == "av_ict"
        and not ({"wearable", "handheld", "body_worn_or_applied", "replaceable_battery"} & traits)
    ):
        diagnostics.append("gate=prune_Battery_safety_review:covered_by_EN62133-2")
        return [item for item in kept if item.code != "Battery safety review"]
    return kept


__all__ = [
    "_gate_per_item",
    "_promote_household_part1",
    "_prune_battery_safety_review",
    "_prune_emf_duplicate",
]
