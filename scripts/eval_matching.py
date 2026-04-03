from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from pathlib import Path
import sys
from typing import Any, Callable

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from classifier import extract_traits  # noqa: E402
from knowledge_base import reset_cache  # noqa: E402
from tests.matching_quality_fixtures import (  # noqa: E402
    MATCHING_QUALITY_CASES,
    MATCHING_QUALITY_GROUPS,
    MatchingQualityCase,
    expected_case_family,
)


@dataclass(frozen=True, slots=True)
class CaseResult:
    group: str
    name: str
    description: str
    tags: tuple[str, ...]
    expected_family: str | None
    expected_subtype: str | None
    expected_stage: str | None
    product_family: str | None
    product_subtype: str | None
    product_match_stage: str
    case_passed: bool
    stage_passed: bool
    family_passed: bool | None
    subtype_passed: bool | None
    low_margin: bool
    forbidden_subtype_hit: str | None
    ambiguity_reason: str | None
    confidence_limiter: str | None
    family_level_limiter: str | None
    generic_alias_penalties: list[str]
    role_parse_primary_head: str | None
    role_parse_cues: list[str]
    top_candidates: list[dict[str, Any]]


def _margin(result: dict[str, Any]) -> int | None:
    candidates = result["product_match_audit"]["top_subtype_candidates"]
    if len(candidates) < 2:
        return None
    return int(candidates[0]["score"]) - int(candidates[1]["score"])


def _expected_family(case: MatchingQualityCase) -> str | None:
    return expected_case_family(case)


def _evaluate_case(case: MatchingQualityCase) -> CaseResult:
    result = extract_traits(case.description)
    audit = result["product_match_audit"]
    expected_family = _expected_family(case)
    family_passed = result["product_family"] == expected_family if expected_family is not None else None
    subtype_passed = result["product_subtype"] == case.expected_subtype if case.expected_subtype is not None else None
    stage_passed = result["product_match_stage"] == case.expected_stage if case.expected_stage is not None else True
    forbidden_hit = next((item for item in case.forbidden_subtypes if result["product_subtype"] == item), None)

    case_passed = stage_passed and forbidden_hit is None
    if family_passed is not None:
        case_passed = case_passed and family_passed
    if subtype_passed is not None:
        case_passed = case_passed and subtype_passed
    elif case.expected_stage in {"family", "ambiguous"}:
        case_passed = case_passed and result["product_subtype"] is None

    margin = _margin(result)
    role_parse = audit.get("role_parse", {})
    return CaseResult(
        group=case.group,
        name=case.name,
        description=case.description,
        tags=case.tags,
        expected_family=expected_family,
        expected_subtype=case.expected_subtype,
        expected_stage=case.expected_stage,
        product_family=result["product_family"],
        product_subtype=result["product_subtype"],
        product_match_stage=result["product_match_stage"],
        case_passed=case_passed,
        stage_passed=stage_passed,
        family_passed=family_passed,
        subtype_passed=subtype_passed,
        low_margin=bool(result["product_match_stage"] == "subtype" and margin is not None and margin < 12),
        forbidden_subtype_hit=forbidden_hit,
        ambiguity_reason=audit["ambiguity_reason"],
        confidence_limiter=audit["confidence_limiter"],
        family_level_limiter=audit["family_level_limiter"],
        generic_alias_penalties=list(audit["generic_alias_penalties"]),
        role_parse_primary_head=role_parse.get("primary_product_head"),
        role_parse_cues=list(role_parse.get("cue_hits", [])),
        top_candidates=list(audit["top_subtype_candidates"][:3]),
    )


def _accuracy(values: list[bool]) -> float:
    if not values:
        return 0.0
    return round(sum(1 for value in values if value) / len(values), 4)


def _rate(results: list[CaseResult], *, include: Callable[[CaseResult], bool], success: Callable[[CaseResult], bool]) -> float:
    scoped = [result for result in results if include(result)]
    return _accuracy([success(result) for result in scoped])


def _group_summary(results: list[CaseResult]) -> dict[str, Any]:
    return {
        "total_cases": len(results),
        "top1_accuracy": _accuracy([result.case_passed for result in results]),
        "family_accuracy": _accuracy([bool(result.family_passed) for result in results if result.family_passed is not None]),
        "subtype_accuracy": _accuracy([bool(result.subtype_passed) for result in results if result.subtype_passed is not None]),
        "family_only_success_rate": _rate(
            results,
            include=lambda result: result.expected_stage == "family",
            success=lambda result: result.case_passed,
        ),
        "ambiguity_precision": _rate(
            results,
            include=lambda result: result.expected_stage == "ambiguous",
            success=lambda result: result.case_passed,
        ),
        "accessory_boundary_stop_success_rate": _rate(
            results,
            include=lambda result: bool({"accessory", "boundary", "family_only"} & set(result.tags)),
            success=lambda result: result.case_passed,
        ),
    }


def build_summary(cases: list[MatchingQualityCase]) -> dict[str, Any]:
    reset_cache()
    results = [_evaluate_case(case) for case in cases]

    subtype_confusions = Counter(
        f"{result.expected_subtype} -> {result.product_subtype or 'none'}"
        for result in results
        if result.expected_subtype is not None and result.expected_subtype != result.product_subtype
    )
    family_confusions = Counter(
        f"{result.expected_family} -> {result.product_family or 'none'}"
        for result in results
        if result.expected_family is not None and result.expected_family != result.product_family
    )
    low_margin_wins = [result.name for result in results if result.low_margin and result.case_passed]
    failed_cases = [result.name for result in results if not result.case_passed]
    generic_false_positive_cases = [
        result.name
        for result in results
        if result.generic_alias_penalties and not result.case_passed
    ]

    role_parse_heads = Counter(result.role_parse_primary_head for result in results if result.role_parse_primary_head)
    role_parse_cues = Counter(cue for result in results for cue in result.role_parse_cues)
    groups: dict[str, Any] = {}
    grouped_results: dict[str, list[CaseResult]] = defaultdict(list)
    for result in results:
        grouped_results[result.group].append(result)
    for group_name, group_results in grouped_results.items():
        groups[group_name] = {
            **_group_summary(group_results),
            "failed_cases": [result.name for result in group_results if not result.case_passed],
        }

    summary = {
        "total_cases": len(results),
        "available_groups": sorted(MATCHING_QUALITY_GROUPS),
        **_group_summary(results),
        "low_margin_wins": low_margin_wins,
        "failed_cases": failed_cases,
        "generic_alias_false_positive_count": len(generic_false_positive_cases),
        "generic_alias_false_positive_cases": generic_false_positive_cases,
        "common_family_confusions": dict(family_confusions.most_common(15)),
        "common_subtype_confusions": dict(subtype_confusions.most_common(20)),
        "role_parsing_audit_summaries": {
            "primary_heads": dict(role_parse_heads.most_common(15)),
            "cue_hits": dict(role_parse_cues.most_common(15)),
        },
        "groups": groups,
        "results": [asdict(result) for result in results],
    }
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate grouped product matching quality fixtures.")
    parser.add_argument("--json-out", type=Path, default=None, help="Write the summary JSON to this path.")
    parser.add_argument("--filter", default="", help="Only run fixture names containing this substring.")
    parser.add_argument("--group", default="", help="Only run fixtures in the given portfolio group.")
    parser.add_argument("--tag", default="", help="Only run fixtures containing this tag.")
    args = parser.parse_args()

    selected = [
        case
        for case in MATCHING_QUALITY_CASES
        if args.filter in case.name
        and (not args.group or case.group == args.group)
        and (not args.tag or args.tag in case.tags)
    ]
    summary = build_summary(selected)

    print(f"Cases: {summary['total_cases']}")
    print(f"Top-1 accuracy: {summary['top1_accuracy']:.4f}")
    print(f"Family accuracy: {summary['family_accuracy']:.4f}")
    print(f"Subtype accuracy: {summary['subtype_accuracy']:.4f}")
    print(f"Family-only success rate: {summary['family_only_success_rate']:.4f}")
    print(f"Ambiguity precision: {summary['ambiguity_precision']:.4f}")
    print(f"Accessory/boundary stop success rate: {summary['accessory_boundary_stop_success_rate']:.4f}")
    print(f"Generic alias false positives: {summary['generic_alias_false_positive_count']}")
    print(f"Low-margin wins: {', '.join(summary['low_margin_wins'][:12]) or 'none'}")
    print(f"Failed cases: {', '.join(summary['failed_cases'][:18]) or 'none'}")
    print("Group breakdown:")
    for group_name, group_summary in summary["groups"].items():
        print(
            "  "
            f"{group_name}: total={group_summary['total_cases']} "
            f"top1={group_summary['top1_accuracy']:.4f} "
            f"family={group_summary['family_accuracy']:.4f} "
            f"subtype={group_summary['subtype_accuracy']:.4f}"
        )

    if args.json_out is not None:
        args.json_out.write_text(json.dumps(summary, indent=2), encoding="utf-8")
        print(f"JSON summary written to {args.json_out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
