from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from app.domain.catalog_types import StandardCatalogRow

from .audit import _reject_selected_row
from .contracts import RejectionEntry, SelectionContext


def _finalize_selected_rows_v2(
    selected_rows: list[StandardCatalogRow],
    *,
    traits: set[str],
    allowed_directives: set[str] | None,
    selection_context: SelectionContext | Mapping[str, Any] | None,
    rejections: list[RejectionEntry],
) -> tuple[list[StandardCatalogRow], list[StandardCatalogRow]]:
    if not selected_rows:
        return [], []

    context = SelectionContext.from_mapping(selection_context)
    allowed_directives = allowed_directives or set()
    rejected_rows: list[StandardCatalogRow] = []
    kept: list[StandardCatalogRow] = []
    scope_route = context.scope_route
    primary_route_family = context.primary_route_family or ""
    has_external_psu = context.has_external_psu
    has_laser_source = context.has_laser_source
    has_photobiological_source = context.has_photobiological_source
    prefer_specific_red_emf = context.prefer_specific_red_emf
    prefer_62233 = context.prefer_62233
    prefer_62311 = context.prefer_62311

    for original_row in selected_rows:
        row = original_row
        code = str(row.get("code") or "")
        route = str(row.get("directive") or row.get("legislation_key") or "OTHER")

        if primary_route_family == "building_hardware" and (
            code == "EN 62368-1" or code.startswith("EN 60335-") or code.startswith("EN 55014-") or code in {"EN 55032", "EN 55035"}
        ):
            _reject_selected_row(row, "building-hardware route takes precedence over generic AV/ICT or appliance safety routes", rejected_rows, rejections)
            continue

        if primary_route_family == "lighting_device" and (
            code == "EN 62368-1" or code.startswith("EN 60335-") or code.startswith("EN 55014-") or code in {"EN 55032", "EN 55035"}
        ):
            _reject_selected_row(row, "lighting route takes precedence over generic AV/ICT or appliance safety routes", rejected_rows, rejections)
            continue

        if primary_route_family == "life_safety_alarm" and (
            code == "EN 62368-1" or code.startswith("EN 60335-") or code.startswith("EN 55014-") or code in {"EN 55032", "EN 55035"}
        ):
            _reject_selected_row(row, "alarm-specific safety routes take precedence over generic AV/ICT or appliance routes", rejected_rows, rejections)
            continue

        if primary_route_family == "hvac_control" and (
            code == "EN 62368-1" or code.startswith("EN 60335-") or code.startswith("EN 55014-") or code in {"EN 55032", "EN 55035"}
        ):
            _reject_selected_row(row, "HVAC control routes take precedence over generic AV/ICT or appliance routes", rejected_rows, rejections)
            continue

        if primary_route_family == "ev_charging" and (
            code == "EN 62368-1" or code.startswith("EN 60335-") or code.startswith("EN 55014-") or code in {"EN 55032", "EN 55035"}
        ):
            _reject_selected_row(row, "EV charging routes take precedence over generic AV/ICT or household-appliance routes", rejected_rows, rejections)
            continue

        if primary_route_family == "ev_connector_accessory" and (
            code in {"EN IEC 61851-1", "EN IEC 61851-21-2", "IEC 62752", "EN 62368-1"}
            or code.startswith("EN 60335-")
            or code.startswith("EN 55014-")
            or code in {"EN 55032", "EN 55035"}
        ):
            _reject_selected_row(
                row,
                "connector-accessory routes take precedence over EVSE system, AV/ICT, and household-appliance routes",
                rejected_rows,
                rejections,
            )
            continue

        if primary_route_family == "machinery_power_tool" and (
            code == "EN 62368-1" or code.startswith("EN 60335-") or code.startswith("EN 55014-") or code in {"EN 55032", "EN 55035"}
        ):
            _reject_selected_row(row, "machinery power-tool routes take precedence over AV/ICT and appliance routes", rejected_rows, rejections)
            continue

        if primary_route_family == "toy" and code == "EN 62368-1":
            _reject_selected_row(row, "toy-specific safety routes take precedence over generic AV/ICT safety routes", rejected_rows, rejections)
            continue

        if code in {"EN 55032", "EN 55035"} and scope_route == "appliance":
            _reject_selected_row(row, f"scope route '{scope_route}' prefers appliance EMC standards", rejected_rows, rejections)
            continue

        if code == "EN 62368-1" and scope_route == "appliance":
            if row.get("item_type") != "review":
                _reject_selected_row(row, f"scope route '{scope_route}' prefers household safety standards", rejected_rows, rejections)
                continue

        if code.startswith("EN 60335-") and scope_route == "av_ict":
            _reject_selected_row(row, f"scope route '{scope_route}' prefers AV/ICT safety standards", rejected_rows, rejections)
            continue

        if code.startswith("EN 55014-") and scope_route == "av_ict":
            _reject_selected_row(row, f"scope route '{scope_route}' prefers AV/ICT EMC standards", rejected_rows, rejections)
            continue

        if code == "Charger / external PSU review":
            if not has_external_psu:
                _reject_selected_row(row, "external PSU signal missing", rejected_rows, rejections)
                continue
            row = row.model_copy(update={"directive": "LVD", "legislation_key": "LVD"})
        elif code == "EN 50563":
            if not has_external_psu:
                _reject_selected_row(row, "external PSU signal missing", rejected_rows, rejections)
                continue
            row = row.model_copy(update={"directive": "ECO", "legislation_key": "ECO"})

        if code == "EN 62311":
            if prefer_62233 and not ("radio" in traits and ({"wearable", "handheld", "body_worn_or_applied"} & traits)):
                _reject_selected_row(row, "EN 62233 takes precedence for the detected household EMF route", rejected_rows, rejections)
                continue
            row = row.model_copy(
                update={
                    "directive": "RED" if "radio" in traits else "LVD",
                    "legislation_key": "RED" if "radio" in traits else "LVD",
                }
            )

        if code == "EN 60825-1" and not has_laser_source:
            _reject_selected_row(row, "laser source signal missing", rejected_rows, rejections)
            continue

        if code == "EN 62471" and not has_photobiological_source:
            _reject_selected_row(row, "photobiological source signal missing", rejected_rows, rejections)
            continue

        if code == "EN 62479":
            if "radio" not in traits:
                _reject_selected_row(row, "radio signal missing", rejected_rows, rejections)
                continue
            if prefer_specific_red_emf:
                _reject_selected_row(row, "a more specific RED EMF route takes precedence", rejected_rows, rejections)
                continue

        if code.startswith("EN 62209") and not (
            "radio" in traits and ({"wearable", "handheld", "body_worn_or_applied", "cellular"} & traits)
        ):
            _reject_selected_row(row, "close-proximity radio signal missing", rejected_rows, rejections)
            continue

        route = str(row.get("directive") or "OTHER")
        if allowed_directives and route not in allowed_directives and route != "OTHER":
            _reject_selected_row(row, f"directive '{route}' was not selected", rejected_rows, rejections)
            continue

        kept.append(row)

    household_part2_selected = any(
        str(row.get("code") or "").startswith("EN 60335-2-") and row.get("item_type") == "standard"
        for row in kept
    )
    if household_part2_selected:
        for index, row in enumerate(kept):
            if str(row.get("code") or "") != "EN 60335-1" or row.get("item_type") != "review":
                continue
            updated_reason = row.get("reason")
            if isinstance(updated_reason, str):
                updated_reason = updated_reason.replace(
                    ". some routing traits are inferred from product context and still need confirmation",
                    "",
                )
            replacement = row.model_copy(
                update={
                    "item_type": "standard",
                    "fact_basis": "confirmed",
                    "reason": updated_reason,
                }
            )
            kept[index] = replacement

    codes = {str(row.get("code") or "") for row in kept}
    if "EN 62233" in codes and "EN 62311" in codes and prefer_62233:
        for row in list(kept):
            if row.get("code") != "EN 62311":
                continue
            kept.remove(row)
            _reject_selected_row(row, "EN 62233 takes precedence for the detected household EMF route", rejected_rows, rejections)
    elif "EN 62233" in codes and "EN 62311" in codes and prefer_62311:
        for row in list(kept):
            if row.get("code") != "EN 62233":
                continue
            kept.remove(row)
            _reject_selected_row(row, "EN 62311 takes precedence for the detected AV/ICT or close-proximity EMF route", rejected_rows, rejections)

    codes = {str(row.get("code") or "") for row in kept}
    if (
        "Battery safety review" in codes
        and "EN 62133-2" in codes
        and scope_route == "av_ict"
        and not ({"wearable", "handheld", "body_worn_or_applied", "replaceable_battery"} & traits)
    ):
        for row in list(kept):
            if row.get("code") != "Battery safety review":
                continue
            kept.remove(row)
            _reject_selected_row(row, "EN 62133-2 already covers the detected AV/ICT battery route", rejected_rows, rejections)

    return kept, rejected_rows


__all__ = ["_finalize_selected_rows_v2"]
