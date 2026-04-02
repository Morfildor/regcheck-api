from __future__ import annotations

import re
from typing import Literal

from app.domain.models import KnownFactItem, MissingInformationItem, ProductMatchStage, QuickAddItem
from app.services.classifier import normalize

from .facts_questions import populate_missing_information_questions
from .routing import RoutePlan, _has_wireless_fact_signal


MissingImportance = Literal["high", "medium", "low"]


def _build_known_facts(description: str) -> list[KnownFactItem]:
    text = normalize(description)
    facts: list[KnownFactItem] = []
    seen: set[str] = set()

    def add(key: str, label: str, value: str, related_traits: list[str]) -> None:
        if key in seen:
            return
        seen.add(key)
        facts.append(
            KnownFactItem(
                key=key,
                label=label,
                value=value,
                source="parsed",
                related_traits=related_traits,
            )
        )

    if re.search(r"\b(?:bluetooth|ble|bluetooth low energy)\b", text):
        add("connectivity.bluetooth", "Bluetooth", "Bluetooth is explicitly stated.", ["bluetooth", "radio"])
    if re.search(r"\b(?:wifi|wi fi|wlan|802 11)\b", text):
        add("connectivity.wifi", "Wi-Fi", "Wi-Fi is explicitly stated.", ["wifi", "radio"])
    if re.search(r"\bnfc\b", text):
        add("connectivity.nfc", "NFC", "NFC is explicitly stated.", ["nfc", "radio"])
    if re.search(
        r"\b(?:mobile app|smartphone app|companion app|app control|app controlled|app connected|app sync(?:ed)?|syncs? with (?:the )?(?:mobile )?app|via (?:the )?(?:mobile )?app|bluetooth app|wifi app)\b",
        text,
    ):
        add("service.app_control", "App control", "App control or app sync is explicitly stated.", ["app_control"])
    if re.search(r"\b(?:cloud account required|cloud account|account required|requires account|vendor account|cloud login)\b", text):
        add("service.cloud_account_required", "Cloud/account requirement", "A cloud or account requirement is explicitly stated.", ["cloud", "account"])
    elif re.search(r"\b(?:cloud|cloud service|cloud required|requires cloud|cloud dependency|cloud dependent)\b", text):
        add("service.cloud_dependency", "Cloud connectivity", "Cloud connectivity is explicitly stated.", ["cloud"])
    if re.search(r"\b(?:local only|offline only|no cloud|cloud free|lan only)\b", text):
        add("service.local_only", "Local-only operation", "Local-only or no-cloud operation is explicitly stated.", ["local_only"])
    if re.search(r"\b(?:ota|ota updates?|firmware updates?|firmware update|over the air|software updates?|wireless firmware update)\b", text):
        add("software.ota_updates", "OTA / firmware updates", "OTA or firmware updates are explicitly stated.", ["ota"])
    if re.search(r"\b(?:rechargeable battery|rechargeable|battery powered|battery operated|cordless|battery pack|battery cell)\b", text):
        add("power.rechargeable_battery", "Rechargeable / battery power", "Battery-powered or rechargeable operation is explicitly stated.", ["battery_powered"])
    if re.search(r"\b(?:li[ -]?ion|lithium ion|lithium battery|li ion)\b", text):
        add("power.lithium_ion", "Lithium-ion battery", "Lithium-ion battery chemistry is explicitly stated.", ["battery_powered"])
    if re.search(r"\b(?:consumer use|consumer|domestic|household|home use|personal use)\b", text):
        add("use.consumer", "Consumer use", "Consumer or household use is explicitly stated.", ["consumer", "household"])
    if re.search(r"\b(?:professional use|for professional use|professional|commercial use|commercial|industrial use|industrial|warehouse|enterprise)\b", text):
        add("use.professional", "Professional use", "Professional, commercial, or industrial use is explicitly stated.", ["professional"])
    if re.search(r"\b(?:indoor|indoor use|indoors)\b", text):
        add("environment.indoor", "Indoor use", "Indoor use is explicitly stated.", ["indoor_use"])
    if re.search(r"\b(?:outdoor|outdoor use|garden|lawn)\b", text):
        add("environment.outdoor", "Outdoor use", "Outdoor use is explicitly stated.", ["outdoor_use"])
    if re.search(r"\b(?:wearable|fitness tracker|smart band|smart watch|smartwatch|activity tracker|smart ring|wrist worn|wristband)\b", text):
        add("contact.wearable", "Wearable use", "Wearable or body-worn use is explicitly stated.", ["wearable", "body_worn_or_applied"])
    if re.search(r"\b(?:body contact|skin contact|body worn|on body|on skin|chest strap|sensor patch|wearable patch|armband)\b", text):
        add("contact.body_contact", "Body contact", "Body-contact or skin-contact use is explicitly stated.", ["body_worn_or_applied"])
    if re.search(r"\b(?:heart rate|pulse|spo2|blood oxygen|oxygen saturation|ecg|ekg|biometric|physiological)\b", text):
        add("data.health_related", "Health / biometric data", "Health, biometric, or physiological monitoring wording is explicitly stated.", ["health_related", "biometric"])
    if re.search(
        r"\b(?:diagnos(?:e|is|tic)|treat(?:ment|s|ing)?|therapy|therapeutic|disease monitoring|patient monitoring|clinical use|medical claims?|medical grade|wellness monitor|physiological monitoring|heart rate monitor|pulse oximeter|ecg monitor|ekg monitor)\b",
        text,
    ):
        add("boundary.possible_medical", "Possible medical boundary", "Medical, clinical, or physiological monitoring wording is explicitly stated.", ["possible_medical_boundary"])
    if not _has_wireless_fact_signal(text):
        add("connectivity.no_wifi", "No Wi-Fi stated", "No Wi-Fi is stated in the description.", [])
        add("connectivity.no_radio", "No radio stated", "No radio or wireless connectivity is stated in the description.", [])

    return facts


def _missing_information(
    traits: set[str],
    matched_products: set[str],
    description: str,
    product_type: str | None = None,
    product_match_stage: ProductMatchStage = "ambiguous",
    route_plan: RoutePlan | None = None,
) -> list[MissingInformationItem]:
    text = normalize(description)
    items: list[MissingInformationItem] = []
    seen_keys: set[str] = set()
    route_plan = route_plan or RoutePlan()

    def add(
        key: str,
        message: str,
        importance: MissingImportance = "medium",
        examples: list[str] | None = None,
        related: list[str] | None = None,
        route_impact: list[str] | None = None,
        next_actions: list[str] | None = None,
    ) -> None:
        if key in seen_keys:
            return
        seen_keys.add(key)
        items.append(
            MissingInformationItem(
                key=key,
                message=message,
                importance=importance,
                examples=examples or [],
                related_traits=related or [],
                route_impact=route_impact or [],
                next_actions=next_actions or [],
            )
        )

    known_fact_keys = {item.key for item in _build_known_facts(description)}
    populate_missing_information_questions(
        traits=traits,
        matched_products=matched_products,
        product_type=product_type,
        product_match_stage=product_match_stage,
        route_family=route_plan.primary_route_family,
        text=text,
        known_fact_keys=known_fact_keys,
        add=add,
    )
    return items[:8]


def _build_quick_adds(missing: list[MissingInformationItem]) -> list[QuickAddItem]:
    out: list[QuickAddItem] = []
    seen: set[str] = set()
    for item in missing:
        for example in item.examples[:2]:
            if example in seen:
                continue
            seen.add(example)
            out.append(QuickAddItem(label=item.key.replace("_", " "), text=example))
    return out[:10]


def _top_actions_from_missing(missing: list[MissingInformationItem], limit: int) -> list[str]:
    actions: list[str] = []
    seen: set[str] = set()
    for item in missing:
        for action in item.next_actions or [item.message]:
            if action in seen:
                continue
            seen.add(action)
            actions.append(action)
            if len(actions) >= limit:
                return actions
    return actions[:limit]


__all__ = [
    "MissingImportance",
    "_build_known_facts",
    "_build_quick_adds",
    "_missing_information",
    "_top_actions_from_missing",
]
