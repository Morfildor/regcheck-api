from __future__ import annotations

import re


NORMALIZATION_REPLACEMENTS: list[tuple[str, str]] = [
    (r"\bwi[ -]?fi\b", "wifi"),
    (r"\bwlan\b", "wifi"),
    (r"\bbluetooth low energy\b", "bluetooth"),
    (r"\bble\b", "bluetooth"),
    (r"\bover[ -]?the[ -]?air\b", "ota"),
    (r"\bsign[ -]?in\b", "sign in"),
    (r"\blog[ -]?in\b", "log in"),
    (r"\b5[ -]?ghz\b", "5ghz"),
    (r"\bmulti[ -]?cooker\b", "multicooker"),
    (r"\bbean[ -]?to[ -]?cup\b", "bean to cup"),
    (r"\bair[ -]?conditioning\b", "air conditioner"),
    (r"\btooth[ -]?brush\b", "toothbrush"),
    (r"\be[ -]?ink\b", "eink"),
    (r"\be[ -]?paper\b", "epaper"),
    (r"\bpower over ethernet\b", "poe"),
]
_COMPILED_NORMALIZATION: list[tuple[re.Pattern, str]] = [
    (re.compile(p), r) for p, r in NORMALIZATION_REPLACEMENTS
]
_COMPILED_CLEANUP1 = re.compile(r"[^a-z0-9_]+")
_COMPILED_CLEANUP2 = re.compile(r"\s+")


def normalize(text: str) -> str:
    text = (text or "").lower()
    for pattern, replacement in _COMPILED_NORMALIZATION:
        text = pattern.sub(replacement, text)
    text = _COMPILED_CLEANUP1.sub(" ", text)
    return _COMPILED_CLEANUP2.sub(" ", text).strip()


__all__ = ["NORMALIZATION_REPLACEMENTS", "normalize"]
