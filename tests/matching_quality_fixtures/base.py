from __future__ import annotations

from dataclasses import dataclass

from knowledge_base import get_knowledge_base_snapshot


@dataclass(frozen=True, slots=True)
class MatchingQualityCase:
    group: str
    name: str
    description: str
    expected_family: str | None = None
    expected_subtype: str | None = None
    expected_stage: str | None = None
    forbidden_subtypes: tuple[str, ...] = ()
    tags: tuple[str, ...] = ()
    modes: tuple[str, ...] = ("curated",)


def subtype_case(
    group: str,
    name: str,
    description: str,
    expected_subtype: str,
    *,
    forbidden_subtypes: tuple[str, ...] = (),
    tags: tuple[str, ...] = (),
    modes: tuple[str, ...] = ("curated",),
) -> MatchingQualityCase:
    return MatchingQualityCase(
        group=group,
        name=name,
        description=description,
        expected_subtype=expected_subtype,
        expected_stage="subtype",
        forbidden_subtypes=forbidden_subtypes,
        tags=("positive",) + tags,
        modes=modes,
    )


def family_case(
    group: str,
    name: str,
    description: str,
    expected_family: str,
    *,
    forbidden_subtypes: tuple[str, ...] = (),
    tags: tuple[str, ...] = (),
    modes: tuple[str, ...] = ("curated",),
) -> MatchingQualityCase:
    return MatchingQualityCase(
        group=group,
        name=name,
        description=description,
        expected_family=expected_family,
        expected_stage="family",
        forbidden_subtypes=forbidden_subtypes,
        tags=("family_only",) + tags,
        modes=modes,
    )


def ambiguous_case(
    group: str,
    name: str,
    description: str,
    *,
    forbidden_subtypes: tuple[str, ...] = (),
    tags: tuple[str, ...] = (),
    modes: tuple[str, ...] = ("curated",),
) -> MatchingQualityCase:
    return MatchingQualityCase(
        group=group,
        name=name,
        description=description,
        expected_stage="ambiguous",
        forbidden_subtypes=forbidden_subtypes,
        tags=("ambiguous",) + tags,
        modes=modes,
    )


def expected_case_family(case: MatchingQualityCase) -> str | None:
    if case.expected_family is not None or case.expected_subtype is None:
        return case.expected_family

    snapshot = get_knowledge_base_snapshot()
    for product in snapshot.products:
        if product["id"] == case.expected_subtype:
            return str(product.get("product_family") or "").strip() or None
    return None


__all__ = [
    "MatchingQualityCase",
    "ambiguous_case",
    "expected_case_family",
    "family_case",
    "subtype_case",
]
