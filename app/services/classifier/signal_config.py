from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
import re
from typing import Any

from app.services.knowledge_base.loader import _load_yaml_raw
from app.services.knowledge_base.paths import KnowledgeBaseError
from app.services.knowledge_base.validator import _validate_classifier_signal_catalog


def _compile_patterns(patterns: tuple[str, ...], *, context: str) -> tuple[re.Pattern[str], ...]:
    compiled: list[re.Pattern[str]] = []
    for pattern in patterns:
        try:
            compiled.append(re.compile(pattern))
        except re.error as exc:
            raise KnowledgeBaseError(f"Invalid regex in classifier_signals.yaml at {context}: {pattern}") from exc
    return tuple(compiled)


def _coerce_string_list(value: Any) -> tuple[str, ...]:
    if not isinstance(value, list):
        return ()
    return tuple(item for item in value if isinstance(item, str) and item)


def _load_grouped_patterns(
    payload: Mapping[str, Any],
    *,
    section_name: str,
) -> tuple[dict[str, dict[str, tuple[str, ...]]], dict[str, tuple[re.Pattern[str], ...]]]:
    section = payload.get(section_name)
    if not isinstance(section, Mapping):
        return {}, {}

    groups: dict[str, dict[str, tuple[str, ...]]] = {}
    flattened: dict[str, tuple[re.Pattern[str], ...]] = {}
    for group_name, group_payload in section.items():
        if not isinstance(group_name, str) or not isinstance(group_payload, Mapping):
            continue
        group_entries: dict[str, tuple[str, ...]] = {}
        for signal_name, patterns_payload in group_payload.items():
            if not isinstance(signal_name, str):
                continue
            patterns = _coerce_string_list(patterns_payload)
            if not patterns:
                continue
            group_entries[signal_name] = patterns
            flattened[signal_name] = _compile_patterns(
                patterns,
                context=f"{section_name}.{group_name}.{signal_name}",
            )
        if group_entries:
            groups[group_name] = group_entries
    return groups, flattened


def _load_grouped_suppressions(
    payload: Mapping[str, Any],
) -> tuple[dict[str, dict[str, frozenset[str]]], dict[str, frozenset[str]]]:
    section = payload.get("suppression_mappings")
    if not isinstance(section, Mapping):
        return {}, {}

    groups: dict[str, dict[str, frozenset[str]]] = {}
    flattened: dict[str, frozenset[str]] = {}
    for group_name, group_payload in section.items():
        if not isinstance(group_name, str) or not isinstance(group_payload, Mapping):
            continue
        group_entries: dict[str, frozenset[str]] = {}
        for signal_name, traits_payload in group_payload.items():
            if not isinstance(signal_name, str):
                continue
            traits = frozenset(_coerce_string_list(traits_payload))
            if not traits:
                continue
            group_entries[signal_name] = traits
            flattened[signal_name] = traits
        if group_entries:
            groups[group_name] = group_entries
    return groups, flattened


def _load_cue_groups(payload: Mapping[str, Any]) -> tuple[dict[str, tuple[str, ...]], dict[str, tuple[re.Pattern[str], ...]]]:
    section = payload.get("cue_groups")
    if not isinstance(section, Mapping):
        return {}, {}

    raw_groups: dict[str, tuple[str, ...]] = {}
    compiled_groups: dict[str, tuple[re.Pattern[str], ...]] = {}
    for cue_name, patterns_payload in section.items():
        if not isinstance(cue_name, str):
            continue
        patterns = _coerce_string_list(patterns_payload)
        if not patterns:
            continue
        raw_groups[cue_name] = patterns
        compiled_groups[cue_name] = _compile_patterns(patterns, context=f"cue_groups.{cue_name}")
    return raw_groups, compiled_groups


def _load_relation_cue_packs(
    payload: Mapping[str, Any],
) -> tuple[dict[str, dict[str, tuple[str, ...]]], dict[str, dict[str, tuple[re.Pattern[str], ...]]]]:
    section = payload.get("relation_cue_packs")
    if not isinstance(section, Mapping):
        return {}, {}

    raw_packs: dict[str, dict[str, tuple[str, ...]]] = {}
    compiled_packs: dict[str, dict[str, tuple[re.Pattern[str], ...]]] = {}
    for role_name, role_payload in section.items():
        if not isinstance(role_name, str) or not isinstance(role_payload, Mapping):
            continue
        raw_role_entries: dict[str, tuple[str, ...]] = {}
        compiled_role_entries: dict[str, tuple[re.Pattern[str], ...]] = {}
        for cue_name, patterns_payload in role_payload.items():
            if not isinstance(cue_name, str):
                continue
            patterns = _coerce_string_list(patterns_payload)
            if not patterns:
                continue
            raw_role_entries[cue_name] = patterns
            compiled_role_entries[cue_name] = _compile_patterns(
                patterns,
                context=f"relation_cue_packs.{role_name}.{cue_name}",
            )
        if raw_role_entries:
            raw_packs[role_name] = raw_role_entries
            compiled_packs[role_name] = compiled_role_entries
    return raw_packs, compiled_packs


@dataclass(frozen=True, slots=True)
class ClassifierSignalSnapshot:
    catalog_version: str | None
    trait_detection_groups: dict[str, dict[str, tuple[str, ...]]]
    trait_patterns: dict[str, tuple[re.Pattern[str], ...]]
    negation_groups: dict[str, dict[str, tuple[str, ...]]]
    negations: dict[str, tuple[re.Pattern[str], ...]]
    suppression_groups: dict[str, dict[str, frozenset[str]]]
    negated_trait_suppressions: dict[str, frozenset[str]]
    cue_groups: dict[str, tuple[str, ...]]
    compiled_cue_groups: dict[str, tuple[re.Pattern[str], ...]]
    relation_cue_packs: dict[str, dict[str, tuple[str, ...]]]
    compiled_relation_cue_packs: dict[str, dict[str, tuple[re.Pattern[str], ...]]]
    wireless_mention_patterns: tuple[str, ...]
    wireless_mentions: tuple[re.Pattern[str], ...]


def build_classifier_signal_snapshot(*, catalog_version: str | None = None, trait_ids: set[str] | None = None) -> ClassifierSignalSnapshot:
    payload = _load_yaml_raw("classifier_signals.yaml")
    if trait_ids is not None:
        _validate_classifier_signal_catalog(payload, trait_ids)
    trait_detection_groups, trait_patterns = _load_grouped_patterns(payload, section_name="trait_detection")
    negation_groups, negations = _load_grouped_patterns(payload, section_name="negations")
    suppression_groups, negated_trait_suppressions = _load_grouped_suppressions(payload)
    cue_groups, compiled_cue_groups = _load_cue_groups(payload)
    relation_cue_packs, compiled_relation_cue_packs = _load_relation_cue_packs(payload)
    wireless_mention_patterns = _coerce_string_list(payload.get("wireless_mentions"))

    return ClassifierSignalSnapshot(
        catalog_version=catalog_version,
        trait_detection_groups=trait_detection_groups,
        trait_patterns=trait_patterns,
        negation_groups=negation_groups,
        negations=negations,
        suppression_groups=suppression_groups,
        negated_trait_suppressions=negated_trait_suppressions,
        cue_groups=cue_groups,
        compiled_cue_groups=compiled_cue_groups,
        relation_cue_packs=relation_cue_packs,
        compiled_relation_cue_packs=compiled_relation_cue_packs,
        wireless_mention_patterns=wireless_mention_patterns,
        wireless_mentions=_compile_patterns(wireless_mention_patterns, context="wireless_mentions"),
    )


def get_classifier_signal_snapshot() -> ClassifierSignalSnapshot:
    from app.services.knowledge_base import get_knowledge_base_snapshot

    snapshot = get_knowledge_base_snapshot()
    compiled = snapshot.classifier_signal_runtime
    if isinstance(compiled, ClassifierSignalSnapshot):
        return compiled
    return build_classifier_signal_snapshot(catalog_version=snapshot.meta.version)


__all__ = [
    "ClassifierSignalSnapshot",
    "build_classifier_signal_snapshot",
    "get_classifier_signal_snapshot",
]
