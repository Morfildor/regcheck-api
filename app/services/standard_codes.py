from __future__ import annotations

from collections.abc import Iterable
import re

_WHITESPACE_RE = re.compile(r"\s+")
_HYPHEN_RE = re.compile(r"\s*-\s*")
_STANDARD_CODE_PREFIX_RE = re.compile(r"^(?:EN|IEC|ISO|ETSI|CEN|CENELEC|UN)\b|^EN(?=\d)")

_CANONICAL_OVERRIDES = {
    "EN 61851-1": "EN IEC 61851-1",
    "EN 61851-21-2": "EN IEC 61851-21-2",
    "EN IEC 62196-2": "EN 62196-2",
}


def canonicalize_standard_code(code: object) -> str:
    text = _WHITESPACE_RE.sub(" ", str(code or "").strip())
    text = _HYPHEN_RE.sub("-", text)
    if not text:
        return ""

    normalized = text.upper()
    normalized = normalized.replace("EN/IEC", "EN IEC").replace("EN-IEC", "EN IEC")
    normalized = re.sub(r"\bEN\s+IEC(?=\d)", "EN IEC ", normalized)
    normalized = re.sub(r"\bEN(?=\d)", "EN ", normalized)
    normalized = _WHITESPACE_RE.sub(" ", normalized)
    normalized = _HYPHEN_RE.sub("-", normalized)

    if normalized in _CANONICAL_OVERRIDES:
        return _CANONICAL_OVERRIDES[normalized]
    if " REVIEW" in normalized:
        return text
    if _STANDARD_CODE_PREFIX_RE.match(normalized):
        return normalized
    return text


def normalized_standard_codes(codes: Iterable[object] | None) -> list[str]:
    normalized: list[str] = []
    seen: set[str] = set()
    for raw_code in codes or []:
        code = canonicalize_standard_code(raw_code)
        if not code or code in seen:
            continue
        seen.add(code)
        normalized.append(code)
    return normalized


def canonical_standard_code_set(codes: Iterable[object] | None) -> set[str]:
    return set(normalized_standard_codes(codes))
