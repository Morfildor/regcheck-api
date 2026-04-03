from __future__ import annotations

import argparse
import json
from collections import Counter
from dataclasses import asdict, dataclass
from pathlib import Path
import sys
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from classifier import extract_traits  # noqa: E402
from knowledge_base import reset_cache  # noqa: E402
from tests.matching_quality_fixtures import MATCHING_QUALITY_CASES, MatchingQualityCase  # noqa: E402


@dataclass(frozen=True, slots=True)
class CaseResult:
    name: str
    description: str
    product_family: str | None
    product_subtype: str | None
    product_match_stage: str
    case_passed: bool
    family_passed: bool | None
    subtype_passed: bool | None
    low_margin: bool
    forbidden_subtype_hit: str | None
    ambiguity_reason: str | None
    confidence_limiter: str | None
    generic_alias_penalties: list[str]
    top_candidates: list[dict[str, Any]]


def _margin(result: dict[str, Any]) -> int | None:
    candidates = result["product_match_audit"]["top_subtype_candidates"]
    if len(candidates) < 2:
        return None
    return int(candidates[0]["score"]) - int(candidates[1]["score"])


def _evaluate_case(case: MatchingQualityCase) -> CaseResult:
    result = extract_traits(case.description)
    audit = result["product_match_audit"]
    family_passed = result["product_family"] == case.expected_family if case.expected_family is not None else None
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
    return CaseResult(
        name=case.name,
        description=case.description,
        product_family=result["product_family"],
        product_subtype=result["product_subtype"],
        product_match_stage=result["product_match_stage"],
        case_passed=case_passed,
        family_passed=family_passed,
        subtype_passed=subtype_passed,
        low_margin=bool(result["product_match_stage"] == "subtype" and margin is not None and margin < 12),
        forbidden_subtype_hit=forbidden_hit,
        ambiguity_reason=audit["ambiguity_reason"],
        confidence_limiter=audit["confidence_limiter"],
        generic_alias_penalties=list(audit["generic_alias_penalties"]),
        top_candidates=list(audit["top_subtype_candidates"][:3]),
    )


def _accuracy(values: list[bool]) -> float:
    if not values:
        return 0.0
    return round(sum(1 for value in values if value) / len(values), 4)


def build_summary(cases: list[MatchingQualityCase]) -> dict[str, Any]:
    reset_cache()
    results = [_evaluate_case(case) for case in cases]
    family_checks = [item.family_passed for item in results if item.family_passed is not None]
    subtype_checks = [item.subtype_passed for item in results if item.subtype_passed is not None]
    common_confusions = Counter(
        f"{item.top_candidates[0]['id']} -> {item.top_candidates[1]['id']}"
        for item in results
        if len(item.top_candidates) >= 2 and item.top_candidates[0]["id"] != item.top_candidates[1]["id"]
    )

    return {
        "total_cases": len(results),
        "top1_accuracy": _accuracy([item.case_passed for item in results]),
        "family_accuracy": _accuracy([bool(item) for item in family_checks]),
        "subtype_accuracy": _accuracy([bool(item) for item in subtype_checks]),
        "ambiguous_cases": [item.name for item in results if item.product_match_stage == "ambiguous"],
        "low_margin_wins": [item.name for item in results if item.low_margin],
        "false_positive_generic_alias_matches": [
            item.name
            for item in results
            if item.generic_alias_penalties and item.product_match_stage == "subtype"
        ],
        "common_confusions": dict(common_confusions.most_common(10)),
        "failed_cases": [item.name for item in results if not item.case_passed],
        "results": [asdict(item) for item in results],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate product matching quality fixtures.")
    parser.add_argument("--json-out", type=Path, default=None, help="Write the summary JSON to this path.")
    parser.add_argument("--filter", default="", help="Only run fixture names containing this substring.")
    args = parser.parse_args()

    selected = [case for case in MATCHING_QUALITY_CASES if args.filter in case.name]
    summary = build_summary(selected)

    print(f"Cases: {summary['total_cases']}")
    print(f"Top-1 accuracy: {summary['top1_accuracy']:.4f}")
    print(f"Family accuracy: {summary['family_accuracy']:.4f}")
    print(f"Subtype accuracy: {summary['subtype_accuracy']:.4f}")
    print(f"Ambiguous cases: {', '.join(summary['ambiguous_cases']) or 'none'}")
    print(f"Low-margin wins: {', '.join(summary['low_margin_wins']) or 'none'}")
    print(f"Failed cases: {', '.join(summary['failed_cases']) or 'none'}")

    if args.json_out is not None:
        args.json_out.write_text(json.dumps(summary, indent=2), encoding="utf-8")
        print(f"JSON summary written to {args.json_out}")
    else:
        print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
