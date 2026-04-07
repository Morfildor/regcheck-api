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
    modes: tuple[str, ...]
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
    low_margin_family: bool
    forbidden_subtype_hit: str | None
    ambiguity_reason: str | None
    confidence_limiter: str | None
    family_level_limiter: str | None
    final_stop_reason: str | None
    generic_alias_penalties: list[str]
    role_parse_primary_head: str | None
    role_parse_primary_head_term: str | None
    role_parse_primary_head_quality: str | None
    role_parse_head_conflict_reason: str | None
    role_parse_cues: list[str]
    domain_role_reasons: list[str]
    confusable_domain_reasons: list[str]
    failure_reasons: tuple[str, ...]
    top_candidates: list[dict[str, Any]]


def _margin(result: dict[str, Any]) -> int | None:
    candidates = result["product_match_audit"]["top_subtype_candidates"]
    if len(candidates) < 2:
        return None
    return int(candidates[0]["score"]) - int(candidates[1]["score"])


def _family_margin(result: dict[str, Any]) -> int | None:
    candidates = result["product_match_audit"]["top_family_candidates"]
    if len(candidates) < 2:
        return None
    return int(candidates[0]["score"]) - int(candidates[1]["score"])


def _expected_family(case: MatchingQualityCase) -> str | None:
    return expected_case_family(case)


def _final_stop_reason(audit: dict[str, Any]) -> str | None:
    for candidate in audit.get("top_subtype_candidates", [])[:3]:
        reason = str(candidate.get("final_stop_reason") or "").strip()
        if reason:
            return reason
    for field in ("family_level_limiter", "confidence_limiter", "ambiguity_reason"):
        reason = str(audit.get(field) or "").strip()
        if reason:
            return reason
    return None


def _failure_reasons(
    *,
    case: MatchingQualityCase,
    case_passed: bool,
    stage_passed: bool,
    family_passed: bool | None,
    subtype_passed: bool | None,
    forbidden_hit: str | None,
    actual_family: str | None,
    actual_stage: str,
) -> tuple[str, ...]:
    if case_passed:
        return ()

    reasons: list[str] = []
    if forbidden_hit is not None:
        reasons.append("forbidden_subtype")
    if family_passed is False:
        reasons.append("domain_confusion")
    if subtype_passed is False:
        reasons.append("subtype_confusion")
    if not stage_passed:
        if case.expected_stage == "subtype" and actual_stage == "family" and expected_case_family(case) == actual_family:
            reasons.append("unresolved_valid_product")
        elif case.expected_stage == "family" and actual_stage == "subtype":
            reasons.append("overcommitted_subtype")
        elif case.expected_stage == "ambiguous":
            reasons.append("missed_ambiguity_boundary")
        else:
            reasons.append("stage_mismatch")
    if not reasons:
        reasons.append("other")
    return tuple(dict.fromkeys(reasons))


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
    family_margin = _family_margin(result)
    role_parse = audit.get("role_parse", {})
    failure_reasons = _failure_reasons(
        case=case,
        case_passed=case_passed,
        stage_passed=stage_passed,
        family_passed=family_passed,
        subtype_passed=subtype_passed,
        forbidden_hit=forbidden_hit,
        actual_family=result["product_family"],
        actual_stage=result["product_match_stage"],
    )
    return CaseResult(
        group=case.group,
        name=case.name,
        description=case.description,
        tags=case.tags,
        modes=case.modes,
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
        low_margin_family=bool(result["product_match_stage"] == "family" and family_margin is not None and family_margin < 10),
        forbidden_subtype_hit=forbidden_hit,
        ambiguity_reason=audit["ambiguity_reason"],
        confidence_limiter=audit["confidence_limiter"],
        family_level_limiter=audit["family_level_limiter"],
        final_stop_reason=_final_stop_reason(audit),
        generic_alias_penalties=list(audit["generic_alias_penalties"]),
        role_parse_primary_head=role_parse.get("primary_product_head"),
        role_parse_primary_head_term=role_parse.get("primary_product_head_term"),
        role_parse_primary_head_quality=role_parse.get("primary_head_quality"),
        role_parse_head_conflict_reason=role_parse.get("head_conflict_reason"),
        role_parse_cues=list(role_parse.get("cue_hits", [])),
        domain_role_reasons=list(audit.get("domain_role_disambiguation_reasons", [])),
        confusable_domain_reasons=list(audit.get("confusable_domain_reasons", [])),
        failure_reasons=failure_reasons,
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
        "low_margin_family_win_rate": _rate(
            results,
            include=lambda result: result.product_match_stage == "family",
            success=lambda result: result.case_passed and result.low_margin_family,
        ),
        # Wave 5 companion / hybrid quality metrics
        "companion_device_accuracy": _rate(
            results,
            include=lambda result: "companion" in result.tags,
            success=lambda result: result.case_passed,
        ),
        "hybrid_product_accuracy": _rate(
            results,
            include=lambda result: "hybrid" in result.tags,
            success=lambda result: result.case_passed,
        ),
        "main_device_false_positive_rate": _rate(
            results,
            include=lambda result: "companion" in result.tags or "contrastive" in result.tags,
            success=lambda result: result.forbidden_subtype_hit is not None,
        ),
    }


def _mode_summary(results: list[CaseResult]) -> dict[str, Any]:
    grouped: dict[str, list[CaseResult]] = defaultdict(list)
    for result in results:
        for mode in result.modes:
            grouped[mode].append(result)
    return {
        mode: {
            **_group_summary(mode_results),
            "failed_cases": [result.name for result in mode_results if not result.case_passed],
        }
        for mode, mode_results in sorted(grouped.items())
    }


def _head_resolution_disagreements(results: list[CaseResult]) -> dict[str, Any]:
    relevant = [
        result
        for result in results
        if (
            result.role_parse_head_conflict_reason
            or result.role_parse_primary_head_quality in {"low", None}
            or "unresolved_valid_product" in result.failure_reasons
        )
        and (not result.case_passed or result.low_margin_family)
    ]
    return {
        "count": len(relevant),
        "primary_heads": dict(
            Counter(result.role_parse_primary_head_term or result.role_parse_primary_head or "none" for result in relevant).most_common(15)
        ),
        "conflict_reasons": dict(
            Counter(result.role_parse_head_conflict_reason or "low_or_missing_head" for result in relevant).most_common(10)
        ),
        "cases": [asdict(result) for result in relevant[:40]],
    }


def build_summary(cases: list[MatchingQualityCase]) -> dict[str, Any]:
    reset_cache()
    results = [_evaluate_case(case) for case in cases]
    available_modes = sorted({mode for case in cases for mode in case.modes})

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
    low_margin_family_wins = [result.name for result in results if result.low_margin_family and result.case_passed]
    failed_cases = [result.name for result in results if not result.case_passed]
    generic_false_positive_cases = [
        result.name
        for result in results
        if result.generic_alias_penalties and not result.case_passed
    ]
    unresolved_valid_products = [
        result
        for result in results
        if "unresolved_valid_product" in result.failure_reasons
    ]
    failures_by_reason: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for result in results:
        if result.case_passed:
            continue
        for reason in result.failure_reasons:
            failures_by_reason[reason].append(asdict(result))

    role_parse_heads = Counter(result.role_parse_primary_head for result in results if result.role_parse_primary_head)
    role_parse_head_terms = Counter(result.role_parse_primary_head_term for result in results if result.role_parse_primary_head_term)
    role_parse_cues = Counter(cue for result in results for cue in result.role_parse_cues)
    domain_role_reasons = Counter(reason for result in results for reason in result.domain_role_reasons)
    confusable_domain_reasons = Counter(reason for result in results for reason in result.confusable_domain_reasons)
    groups: dict[str, Any] = {}
    grouped_results: dict[str, list[CaseResult]] = defaultdict(list)
    for result in results:
        grouped_results[result.group].append(result)
    for group_name, group_results in grouped_results.items():
        groups[group_name] = {
            **_group_summary(group_results),
            "failed_cases": [result.name for result in group_results if not result.case_passed],
        }

    # Companion vs main-device confusion analysis
    companion_results = [result for result in results if "companion" in result.tags]
    hybrid_results = [result for result in results if "hybrid" in result.tags]
    companion_confusions = Counter(
        f"{result.expected_family or result.expected_subtype} -> {result.product_family or 'none'}"
        for result in companion_results
        if not result.case_passed
    )
    heater_confusions = Counter(
        f"{result.expected_subtype or result.expected_family} -> {result.product_subtype or result.product_family or 'none'}"
        for result in results
        if (result.expected_subtype or result.expected_family or "").startswith(("water_heating", "electric_shower", "personal_heating"))
        and not result.case_passed
    )
    ev_confusions = Counter(
        f"{result.expected_subtype or result.expected_family} -> {result.product_subtype or result.product_family or 'none'}"
        for result in results
        if (
            "ev" in result.description.lower()
            or (result.expected_subtype or result.expected_family or "").startswith("ev_")
            or result.expected_family in {"ev_charging_equipment", "energy_power_system"}
        )
        and not result.case_passed
    )

    summary = {
        "total_cases": len(results),
        "available_groups": sorted(MATCHING_QUALITY_GROUPS),
        "available_modes": available_modes,
        **_group_summary(results),
        "mode_summaries": _mode_summary(results),
        "low_margin_wins": low_margin_wins,
        "low_margin_family_wins": low_margin_family_wins,
        "failed_cases": failed_cases,
        "generic_alias_false_positive_count": len(generic_false_positive_cases),
        "generic_alias_false_positive_cases": generic_false_positive_cases,
        "domain_confusion_summaries": dict(family_confusions.most_common(20)),
        "common_subtype_confusions": dict(subtype_confusions.most_common(20)),
        "unresolved_valid_products": [asdict(result) for result in unresolved_valid_products],
        "unresolved_valid_product_summaries": dict(
            Counter(result.expected_subtype or result.expected_family or result.name for result in unresolved_valid_products).most_common(20)
        ),
        "head_resolution_disagreements": _head_resolution_disagreements(results),
        "failures_by_reason": dict(sorted(failures_by_reason.items())),
        "role_parsing_audit_summaries": {
            "primary_heads": dict(role_parse_heads.most_common(15)),
            "primary_head_terms": dict(role_parse_head_terms.most_common(15)),
            "cue_hits": dict(role_parse_cues.most_common(15)),
        },
        "domain_role_reason_summaries": dict(domain_role_reasons.most_common(20)),
        "confusable_domain_reason_summaries": dict(confusable_domain_reasons.most_common(20)),
        # Wave 5 companion / hybrid quality summaries
        "companion_device_total": len(companion_results),
        "companion_device_passed": sum(1 for result in companion_results if result.case_passed),
        "hybrid_device_total": len(hybrid_results),
        "hybrid_device_passed": sum(1 for result in hybrid_results if result.case_passed),
        "companion_vs_main_confusions": dict(companion_confusions.most_common(15)),
        "heater_type_confusions": dict(heater_confusions.most_common(10)),
        "ev_module_vs_charger_confusions": dict(ev_confusions.most_common(10)),
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
    parser.add_argument(
        "--mode",
        default="",
        help="Only run fixtures in one or more evaluation modes (comma-separated: curated, adversarial, paraphrase, organic).",
    )
    args = parser.parse_args()
    selected_modes = {item.strip() for item in args.mode.split(",") if item.strip()}

    selected = [
        case
        for case in MATCHING_QUALITY_CASES
        if args.filter in case.name
        and (not args.group or case.group == args.group)
        and (not args.tag or args.tag in case.tags)
        and (not selected_modes or bool(selected_modes & set(case.modes)))
    ]
    summary = build_summary(selected)

    print(f"Cases: {summary['total_cases']}")
    print(f"Top-1 accuracy: {summary['top1_accuracy']:.4f}")
    print(f"Family accuracy: {summary['family_accuracy']:.4f}")
    print(f"Subtype accuracy: {summary['subtype_accuracy']:.4f}")
    print(f"Family-only success rate: {summary['family_only_success_rate']:.4f}")
    print(f"Ambiguity precision: {summary['ambiguity_precision']:.4f}")
    print(f"Accessory/boundary stop success rate: {summary['accessory_boundary_stop_success_rate']:.4f}")
    print(f"Low-margin family wins: {', '.join(summary['low_margin_family_wins'][:12]) or 'none'}")
    print(f"Generic alias false positives: {summary['generic_alias_false_positive_count']}")
    print(f"Low-margin wins: {', '.join(summary['low_margin_wins'][:12]) or 'none'}")
    print(f"Failed cases: {', '.join(summary['failed_cases'][:18]) or 'none'}")
    adversarial_summary = summary["mode_summaries"].get("adversarial")
    if adversarial_summary is not None:
        print(
            "Adversarial summary: "
            f"cases={adversarial_summary['total_cases']} "
            f"top1={adversarial_summary['top1_accuracy']:.4f} "
            f"family_only={adversarial_summary['family_only_success_rate']:.4f}"
        )
    if summary["unresolved_valid_product_summaries"]:
        print(
            "Unresolved valid products: "
            + ", ".join(
                f"{name}={count}" for name, count in list(summary["unresolved_valid_product_summaries"].items())[:8]
            )
        )
    if summary["domain_confusion_summaries"]:
        print(
            "Domain confusions: "
            + ", ".join(
                f"{pair}={count}" for pair, count in list(summary["domain_confusion_summaries"].items())[:8]
            )
        )
    companion_total = summary.get("companion_device_total", 0)
    if companion_total:
        companion_passed = summary.get("companion_device_passed", 0)
        companion_acc = round(companion_passed / companion_total, 4) if companion_total else 0.0
        print(
            f"Companion-device accuracy: {companion_acc:.4f} "
            f"({companion_passed}/{companion_total})"
        )
    hybrid_total = summary.get("hybrid_device_total", 0)
    if hybrid_total:
        hybrid_passed = summary.get("hybrid_device_passed", 0)
        hybrid_acc = round(hybrid_passed / hybrid_total, 4) if hybrid_total else 0.0
        print(
            f"Hybrid-product accuracy: {hybrid_acc:.4f} "
            f"({hybrid_passed}/{hybrid_total})"
        )
    if summary.get("companion_vs_main_confusions"):
        print(
            "Companion vs main-device confusions: "
            + ", ".join(
                f"{pair}={count}" for pair, count in list(summary["companion_vs_main_confusions"].items())[:6]
            )
        )
    if summary.get("heater_type_confusions"):
        print(
            "Heater-type confusions: "
            + ", ".join(
                f"{pair}={count}" for pair, count in list(summary["heater_type_confusions"].items())[:6]
            )
        )
    print("Group breakdown:")
    for group_name, group_summary in summary["groups"].items():
        print(
            "  "
            f"{group_name}: total={group_summary['total_cases']} "
            f"top1={group_summary['top1_accuracy']:.4f} "
            f"family={group_summary['family_accuracy']:.4f} "
            f"subtype={group_summary['subtype_accuracy']:.4f} "
            f"family_low_margin={group_summary['low_margin_family_win_rate']:.4f}"
        )

    if args.json_out is not None:
        args.json_out.write_text(json.dumps(summary, indent=2), encoding="utf-8")
        print(f"JSON summary written to {args.json_out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
