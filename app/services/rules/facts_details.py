from __future__ import annotations

import re


def _has_battery_chemistry_detail(text: str) -> bool:
    return bool(
        re.search(
            r"\b(?:li[ -]?ion|lithium(?:[ -](?:ion|iron phosphate))?|lifepo4|nimh|ni[ -]?mh|nicd|ni[ -]?cd|lead[ -]?acid|alkaline)\b",
            text,
        )
    )


def _has_battery_capacity_detail(text: str) -> bool:
    return bool(re.search(r"\b\d+(?:\.\d+)?\s*(?:mah|ah|wh|v)\b", text))


def _has_battery_pack_format_detail(text: str) -> bool:
    return bool(re.search(r"\b(?:integrated battery|built in battery|removable battery|replaceable battery|battery pack supplied)\b", text))


def _has_data_storage_detail(text: str) -> bool:
    return bool(
        re.search(
            r"\b(?:data storage|local storage|cloud storage|sd card|event history|recording|logs?|telemetry|retention|video storage)\b",
            text,
        )
    )


def _has_update_route_detail(text: str) -> bool:
    return bool(
        re.search(
            r"\b(?:ota|over the air|firmware update|software update|manual update|usb update|no updates?|security updates?)\b",
            text,
        )
    )


def _has_cloud_dependency_detail(text: str) -> bool:
    return bool(
        re.search(
            r"\b(?:cloud|cloud required|requires cloud|cloud dependency|cloud account|required account|account required|local only|offline only|cloud free|no cloud)\b",
            text,
        )
    )


def _has_access_model_detail(text: str) -> bool:
    return bool(
        re.search(
            r"\b(?:account|login|log in|sign in|pairing|pairing code|authentication|password|pin|guest mode|local only|cloud only|offline only)\b",
            text,
        )
    )


def _has_data_category_detail(text: str) -> bool:
    return bool(
        re.search(
            r"\b(?:personal data|health data|biometric|heart rate|pulse|spo2|blood oxygen|oxygen saturation|location data|video|audio|camera|microphone|voice|diagnostic data|telemetry|user profile)\b",
            text,
        )
    )


def _has_radio_band_detail(text: str) -> bool:
    return bool(
        re.search(
            r"\b(?:2\.4 ?ghz|5 ?ghz|6 ?ghz|868 ?mhz|915 ?mhz|433 ?mhz|13\.56 ?mhz|ble|bluetooth le|wifi 6|wifi 7|802\.11|802 11)\b",
            text,
        )
    )


def _has_radio_power_detail(text: str) -> bool:
    return bool(re.search(r"\b(?:eirp|dbm|mw|output power|transmit power|tx power)\b", text))


def _has_pressure_detail(text: str) -> bool:
    return bool(re.search(r"\b\d+(?:\.\d+)?\s*(?:bar|psi|mpa|kpa|l|litre|liter|gallon)\b", text))


def _has_installation_detail(text: str) -> bool:
    return bool(re.search(r"\b(?:portable|handheld|bench(?:top)?|stationary|fixed(?:[ -]?installation)?|floor[ -]?standing)\b", text))


def _has_body_contact_material_detail(text: str) -> bool:
    return bool(
        re.search(
            r"\b(?:silicone|tpu|stainless steel|polycarbonate|skin contact material|biocompatib|irritation|sensitization|contact duration)\b",
            text,
        )
    )


def _has_medical_boundary_resolution(text: str) -> bool:
    return bool(
        re.search(
            r"\b(?:not a medical device|wellness only|fitness only|clinical use|patient use|diagnosis|treatment|therapeutic|medical grade)\b",
            text,
        )
    )


__all__ = [
    "_has_access_model_detail",
    "_has_battery_capacity_detail",
    "_has_battery_chemistry_detail",
    "_has_battery_pack_format_detail",
    "_has_body_contact_material_detail",
    "_has_cloud_dependency_detail",
    "_has_data_category_detail",
    "_has_data_storage_detail",
    "_has_installation_detail",
    "_has_medical_boundary_resolution",
    "_has_pressure_detail",
    "_has_radio_band_detail",
    "_has_radio_power_detail",
    "_has_update_route_detail",
]
