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

DEFAULT_MUTATION_KINDS = (
    "paraphrase_set",
    "word_order_variation",
    "relation_variation",
    "secondary_object_distraction",
    "adjective_protocol_insertion",
)

DISTRACTION_SUFFIXES: dict[str, str] = {
    "building_access_controls": "status leds and mobile app",
    "power_charging": "status leds and wall mount kit",
    "lighting_optical": "timer and mobile app",
    "office_peripherals": "ethernet port and cable set",
    "household_core": "touch controls and timer",
    "wellness_boundary": "travel pouch and usb cable",
}

INSERTION_PREFIXES: dict[str, tuple[str, ...]] = {
    "building_access_controls": ("smart", "wifi"),
    "power_charging": ("smart", "din rail"),
    "lighting_optical": ("smart", "led"),
    "office_peripherals": ("desktop", "smart"),
    "household_core": ("portable", "compact"),
    "wellness_boundary": ("rechargeable", "wearable"),
}

GROUP_PARAPHRASES: dict[str, tuple[tuple[str, str], ...]] = {
    "building_access_controls": (
        ("door entry panel", "entry panel"),
        ("smart lock bridge", "lock bridge"),
        ("camera intercom", "video intercom"),
        ("garage door opener controller", "garage opener controller"),
    ),
    "power_charging": (
        ("load balancing meter", "energy meter module"),
        ("smart meter display", "energy display unit"),
        ("smart meter gateway", "energy gateway"),
        ("home battery gateway", "battery system gateway"),
    ),
    "lighting_optical": (
        ("grow light strip", "grow strip"),
        ("plant grow light", "grow light"),
        ("illuminated mirror", "lighted mirror"),
        ("ring light", "studio light"),
    ),
    "office_peripherals": (
        ("kiosk display", "display terminal"),
        ("built in pc", "integrated pc"),
        ("integrated windows pc", "windows pc"),
        ("monitor dock", "display dock"),
    ),
    "household_core": (
        ("induction hot plate", "induction cooker"),
        ("countertop induction cooker", "induction hob"),
        ("portable induction cooker", "induction cooker"),
    ),
    "wellness_boundary": (
        ("heated neck wrap", "warming neck wrap"),
        ("heated shoulder wrap", "warming shoulder wrap"),
        ("heated eye mask", "warm compress eye mask"),
        ("electric underblanket", "heated blanket"),
    ),
}


@dataclass(frozen=True, slots=True)
class EvalCase:
    case: MatchingQualityCase
    description: str
    evaluation_kind: str = "fixture"
    mutation_kind: str | None = None
    source_case_name: str | None = None

    @property
    def name(self) -> str:
        if self.evaluation_kind == "fixture":
            return self.case.name
        return f"{self.case.name}__{self.mutation_kind}"

    @property
    def tags(self) -> tuple[str, ...]:
        if self.evaluation_kind == "fixture" or self.mutation_kind is None:
            return self.case.tags
        return self.case.tags + ("mutation", self.mutation_kind)

    @property
    def modes(self) -> tuple[str, ...]:
        if self.evaluation_kind == "fixture":
            return self.case.modes
        return tuple(dict.fromkeys(self.case.modes + ("mutation", self.mutation_kind)))


@dataclass(frozen=True, slots=True)
class CaseResult:
    group: str
    name: str
    source_case_name: str
    evaluation_kind: str
    mutation_kind: str | None
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
    resolved_head_candidate: str | None
    companion_device_decision: str | None
    hybrid_detection_reason: str | None
    domain_disambiguation_reason: str | None
    negative_guard_activations: list[str]
    rejected_confusable_candidates: list[dict[str, Any]]
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
    for field in ("subtype_stop_reason", "family_level_limiter", "confidence_limiter", "ambiguity_reason"):
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


def _replace_once(text: str, old: str, new: str) -> str | None:
    if old not in text:
        return None
    return text.replace(old, new, 1)


def _paraphrase_mutation(case: MatchingQualityCase) -> str | None:
    for old, new in GROUP_PARAPHRASES.get(case.group, ()):
        mutated = _replace_once(case.description, old, new)
        if mutated and mutated != case.description:
            return mutated
    for old, new in (("built in", "integrated"), ("integrated", "built in"), ("usb c", "usb-c"), ("wifi", "wi-fi")):
        mutated = _replace_once(case.description, old, new)
        if mutated and mutated != case.description:
            return mutated
    return None


def _word_order_mutation(case: MatchingQualityCase) -> str | None:
    tokens = case.description.split()
    if len(tokens) < 3:
        return None
    leading_modifiers = {"smart", "portable", "rechargeable", "wireless", "desktop", "countertop", "heated", "electric"}
    if tokens[0] in leading_modifiers:
        return " ".join(tokens[1:] + [tokens[0]])
    if " with " in case.description:
        left, right = case.description.split(" with ", 1)
        return f"{right} with {left}"
    return None


def _relation_mutation(case: MatchingQualityCase) -> str | None:
    for old, new in ((" built in ", " integrated "), (" integrated ", " built in "), (" with ", " featuring "), (" for ", " with ")):
        mutated = _replace_once(case.description, old, new)
        if mutated and mutated != case.description:
            return mutated
    return None


def _secondary_object_mutation(case: MatchingQualityCase) -> str | None:
    suffix = DISTRACTION_SUFFIXES.get(case.group)
    if not suffix:
        return None
    connector = " and " if " with " in case.description else " with "
    mutated = f"{case.description}{connector}{suffix}"
    return mutated if mutated != case.description else None


def _adjective_protocol_mutation(case: MatchingQualityCase) -> str | None:
    lowered = case.description.lower()
    for prefix in INSERTION_PREFIXES.get(case.group, ()):
        if prefix not in lowered:
            return f"{prefix} {case.description}"
    return None


def _generate_mutations(case: MatchingQualityCase, *, selected_kinds: set[str]) -> list[EvalCase]:
    generators: dict[str, Callable[[MatchingQualityCase], str | None]] = {
        "paraphrase_set": _paraphrase_mutation,
        "word_order_variation": _word_order_mutation,
        "relation_variation": _relation_mutation,
        "secondary_object_distraction": _secondary_object_mutation,
        "adjective_protocol_insertion": _adjective_protocol_mutation,
    }
    generated: list[EvalCase] = []
    seen: set[str] = set()
    for kind in DEFAULT_MUTATION_KINDS:
        if kind not in selected_kinds:
            continue
        mutated = generators[kind](case)
        if not mutated or mutated == case.description or mutated in seen:
            continue
        seen.add(mutated)
        generated.append(
            EvalCase(
                case=case,
                description=mutated,
                evaluation_kind="mutation",
                mutation_kind=kind,
                source_case_name=case.name,
            )
        )
    return generated


def _evaluate_case(eval_case: EvalCase) -> CaseResult:
    case = eval_case.case
    result = extract_traits(eval_case.description)
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
        name=eval_case.name,
        source_case_name=eval_case.source_case_name or case.name,
        evaluation_kind=eval_case.evaluation_kind,
        mutation_kind=eval_case.mutation_kind,
        description=eval_case.description,
        tags=eval_case.tags,
        modes=eval_case.modes,
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
        resolved_head_candidate=audit.get("resolved_head_candidate"),
        companion_device_decision=audit.get("companion_device_decision"),
        hybrid_detection_reason=audit.get("hybrid_detection_reason"),
        domain_disambiguation_reason=audit.get("domain_disambiguation_reason"),
        negative_guard_activations=list(audit.get("negative_guard_activations", [])),
        rejected_confusable_candidates=list(audit.get("rejected_confusable_candidates", [])),
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
        "family_only_success_rate": _rate(results, include=lambda result: result.expected_stage == "family", success=lambda result: result.case_passed),
        "ambiguity_precision": _rate(results, include=lambda result: result.expected_stage == "ambiguous", success=lambda result: result.case_passed),
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
        "companion_device_accuracy": _rate(results, include=lambda result: "companion" in result.tags, success=lambda result: result.case_passed),
        "hybrid_product_accuracy": _rate(results, include=lambda result: "hybrid" in result.tags, success=lambda result: result.case_passed),
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


def _mutation_summary(results: list[CaseResult]) -> dict[str, Any]:
    mutation_results = [result for result in results if result.evaluation_kind == "mutation"]
    grouped: dict[str, list[CaseResult]] = defaultdict(list)
    for result in mutation_results:
        grouped[result.mutation_kind or "unknown"].append(result)
    false_positive_scope = [result for result in mutation_results if result.expected_stage in {"family", "ambiguous"}]
    false_positive_rate = 0.0
    if false_positive_scope:
        false_positive_rate = round(
            sum(1 for result in false_positive_scope if result.product_match_stage == "subtype") / len(false_positive_scope),
            4,
        )
    return {
        "total_mutations": len(mutation_results),
        "mutation_robustness": _accuracy([result.case_passed for result in mutation_results]),
        "family_only_stability": _rate(
            mutation_results,
            include=lambda result: result.expected_family is not None,
            success=lambda result: result.family_passed is True,
        ),
        "false_positive_subtype_collapse_rate": false_positive_rate,
        "kinds": {
            kind: {
                **_group_summary(kind_results),
                "failed_cases": [result.name for result in kind_results if not result.case_passed],
            }
            for kind, kind_results in sorted(grouped.items())
        },
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


def _failure_clusters(results: list[CaseResult]) -> dict[str, Any]:
    clusters: dict[str, dict[str, Any]] = {}
    for result in results:
        if result.case_passed:
            continue
        reason = result.failure_reasons[0] if result.failure_reasons else "other"
        confusion = f"{result.expected_family or result.expected_subtype or 'none'} -> {result.product_family or result.product_subtype or 'none'}"
        key = f"{reason}|{result.evaluation_kind}|{result.mutation_kind or 'base'}|{confusion}"
        bucket = clusters.setdefault(
            key,
            {
                "reason": reason,
                "evaluation_kind": result.evaluation_kind,
                "mutation_kind": result.mutation_kind,
                "confusion": confusion,
                "count": 0,
                "cases": [],
            },
        )
        bucket["count"] += 1
        if len(bucket["cases"]) < 10:
            bucket["cases"].append(result.name)
    return dict(sorted(clusters.items(), key=lambda item: (-item[1]["count"], item[0])))


def build_summary(
    cases: list[MatchingQualityCase],
    *,
    include_mutations: bool = True,
    mutation_kinds: set[str] | None = None,
) -> dict[str, Any]:
    reset_cache()
    selected_mutation_kinds = mutation_kinds or set(DEFAULT_MUTATION_KINDS)

    eval_cases = [EvalCase(case=case, description=case.description, source_case_name=case.name) for case in cases]
    if include_mutations:
        for case in cases:
            eval_cases.extend(_generate_mutations(case, selected_kinds=selected_mutation_kinds))

    results = [_evaluate_case(case) for case in eval_cases]
    fixture_results = [result for result in results if result.evaluation_kind == "fixture"]
    mutation_results = [result for result in results if result.evaluation_kind == "mutation"]
    available_modes = sorted({mode for case in cases for mode in case.modes})

    subtype_confusions = Counter(
        f"{result.expected_subtype} -> {result.product_subtype or 'none'}"
        for result in fixture_results
        if result.expected_subtype is not None and result.expected_subtype != result.product_subtype
    )
    family_confusions = Counter(
        f"{result.expected_family} -> {result.product_family or 'none'}"
        for result in fixture_results
        if result.expected_family is not None and result.expected_family != result.product_family
    )
    mutation_family_confusions = Counter(
        f"{result.expected_family} -> {result.product_family or 'none'}"
        for result in mutation_results
        if result.expected_family is not None and result.expected_family != result.product_family
    )
    low_margin_wins = [result.name for result in fixture_results if result.low_margin and result.case_passed]
    low_margin_family_wins = [result.name for result in fixture_results if result.low_margin_family and result.case_passed]
    failed_cases = [result.name for result in fixture_results if not result.case_passed]
    generic_false_positive_cases = [result.name for result in fixture_results if result.generic_alias_penalties and not result.case_passed]
    unresolved_valid_products = [result for result in fixture_results if "unresolved_valid_product" in result.failure_reasons]
    failures_by_reason: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for result in fixture_results:
        if result.case_passed:
            continue
        for reason in result.failure_reasons:
            failures_by_reason[reason].append(asdict(result))

    role_parse_heads = Counter(result.role_parse_primary_head for result in fixture_results if result.role_parse_primary_head)
    role_parse_head_terms = Counter(result.role_parse_primary_head_term for result in fixture_results if result.role_parse_primary_head_term)
    role_parse_cues = Counter(cue for result in fixture_results for cue in result.role_parse_cues)
    domain_role_reasons = Counter(reason for result in fixture_results for reason in result.domain_role_reasons)
    confusable_domain_reasons = Counter(reason for result in fixture_results for reason in result.confusable_domain_reasons)
    groups: dict[str, Any] = {}
    grouped_results: dict[str, list[CaseResult]] = defaultdict(list)
    for result in fixture_results:
        grouped_results[result.group].append(result)
    for group_name, group_results in grouped_results.items():
        groups[group_name] = {**_group_summary(group_results), "failed_cases": [result.name for result in group_results if not result.case_passed]}

    companion_results = [result for result in fixture_results if "companion" in result.tags]
    hybrid_results = [result for result in fixture_results if "hybrid" in result.tags]
    companion_confusions = Counter(
        f"{result.expected_family or result.expected_subtype} -> {result.product_family or result.product_subtype or 'none'}"
        for result in companion_results
        if not result.case_passed
    )
    mutation_confusions = Counter(
        f"{result.expected_family or result.expected_subtype or 'none'} -> {result.product_family or result.product_subtype or 'none'}"
        for result in mutation_results
        if not result.case_passed
    )

    return {
        "total_cases": len(fixture_results),
        "total_evaluated_prompts": len(results),
        "available_groups": sorted(MATCHING_QUALITY_GROUPS),
        "available_modes": available_modes,
        "mutation_kinds": sorted(selected_mutation_kinds),
        **_group_summary(fixture_results),
        "mode_summaries": _mode_summary(fixture_results),
        "mutation_summary": _mutation_summary(results),
        "low_margin_wins": low_margin_wins,
        "low_margin_family_wins": low_margin_family_wins,
        "failed_cases": failed_cases,
        "generic_alias_false_positive_count": len(generic_false_positive_cases),
        "generic_alias_false_positive_cases": generic_false_positive_cases,
        "domain_confusion_summaries": dict(family_confusions.most_common(20)),
        "mutation_domain_confusion_summaries": dict(mutation_family_confusions.most_common(20)),
        "common_subtype_confusions": dict(subtype_confusions.most_common(20)),
        "unresolved_valid_products": [asdict(result) for result in unresolved_valid_products],
        "unresolved_valid_product_summaries": dict(
            Counter(result.expected_subtype or result.expected_family or result.name for result in unresolved_valid_products).most_common(20)
        ),
        "head_resolution_disagreements": _head_resolution_disagreements(fixture_results),
        "failures_by_reason": dict(sorted(failures_by_reason.items())),
        "role_parsing_audit_summaries": {
            "primary_heads": dict(role_parse_heads.most_common(15)),
            "primary_head_terms": dict(role_parse_head_terms.most_common(15)),
            "cue_hits": dict(role_parse_cues.most_common(15)),
        },
        "domain_role_reason_summaries": dict(domain_role_reasons.most_common(20)),
        "confusable_domain_reason_summaries": dict(confusable_domain_reasons.most_common(20)),
        "companion_device_total": len(companion_results),
        "companion_device_passed": sum(1 for result in companion_results if result.case_passed),
        "hybrid_device_total": len(hybrid_results),
        "hybrid_device_passed": sum(1 for result in hybrid_results if result.case_passed),
        "companion_vs_main_confusions": dict(companion_confusions.most_common(15)),
        "mutation_confusion_summaries": dict(mutation_confusions.most_common(15)),
        "failure_clusters": _failure_clusters(results),
        "groups": groups,
        "results": [asdict(result) for result in results],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate grouped product matching quality fixtures and prompt mutations.")
    parser.add_argument("--json-out", type=Path, default=None, help="Write the summary JSON to this path.")
    parser.add_argument("--filter", default="", help="Only run fixture names containing this substring.")
    parser.add_argument("--group", default="", help="Only run fixtures in the given portfolio group.")
    parser.add_argument("--tag", default="", help="Only run fixtures containing this tag.")
    parser.add_argument(
        "--mode",
        default="",
        help="Only run fixtures in one or more evaluation modes (comma-separated: curated, adversarial, paraphrase, organic).",
    )
    parser.add_argument("--no-mutations", action="store_true", help="Disable generated prompt mutations.")
    parser.add_argument(
        "--mutation-kinds",
        default=",".join(DEFAULT_MUTATION_KINDS),
        help="Comma-separated mutation kinds to generate.",
    )
    args = parser.parse_args()

    selected_modes = {item.strip() for item in args.mode.split(",") if item.strip()}
    selected_mutation_kinds = {item.strip() for item in args.mutation_kinds.split(",") if item.strip()}
    selected = [
        case
        for case in MATCHING_QUALITY_CASES
        if args.filter in case.name
        and (not args.group or case.group == args.group)
        and (not args.tag or args.tag in case.tags)
        and (not selected_modes or bool(selected_modes & set(case.modes)))
    ]
    summary = build_summary(selected, include_mutations=not args.no_mutations, mutation_kinds=selected_mutation_kinds)

    print(f"Fixture cases: {summary['total_cases']}")
    print(f"Evaluated prompts: {summary['total_evaluated_prompts']}")
    print(f"Top-1 accuracy: {summary['top1_accuracy']:.4f}")
    print(f"Family accuracy: {summary['family_accuracy']:.4f}")
    print(f"Subtype accuracy: {summary['subtype_accuracy']:.4f}")
    print(f"Family-only success rate: {summary['family_only_success_rate']:.4f}")
    print(f"Ambiguity precision: {summary['ambiguity_precision']:.4f}")
    print(f"Accessory/boundary stop success rate: {summary['accessory_boundary_stop_success_rate']:.4f}")
    mutation_summary = summary["mutation_summary"]
    print(f"Mutation robustness: {mutation_summary['mutation_robustness']:.4f} (mutations={mutation_summary['total_mutations']})")
    print(f"Family-only stability: {mutation_summary['family_only_stability']:.4f}")
    print(f"False-positive subtype collapse rate: {mutation_summary['false_positive_subtype_collapse_rate']:.4f}")
    print(f"Low-margin family wins: {', '.join(summary['low_margin_family_wins'][:12]) or 'none'}")
    print(f"Generic alias false positives: {summary['generic_alias_false_positive_count']}")
    print(f"Low-margin wins: {', '.join(summary['low_margin_wins'][:12]) or 'none'}")
    print(f"Failed fixture cases: {', '.join(summary['failed_cases'][:18]) or 'none'}")
    if summary["domain_confusion_summaries"]:
        print("Domain confusions: " + ", ".join(f"{pair}={count}" for pair, count in list(summary["domain_confusion_summaries"].items())[:8]))
    if summary["mutation_domain_confusion_summaries"]:
        print("Mutation confusions: " + ", ".join(f"{pair}={count}" for pair, count in list(summary["mutation_domain_confusion_summaries"].items())[:8]))
    print("Mutation kinds:")
    for kind, kind_summary in summary["mutation_summary"]["kinds"].items():
        print(
            "  "
            f"{kind}: total={kind_summary['total_cases']} "
            f"top1={kind_summary['top1_accuracy']:.4f} "
            f"family={kind_summary['family_accuracy']:.4f} "
            f"subtype={kind_summary['subtype_accuracy']:.4f}"
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
