from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

from app.core.settings import get_settings

from .paths import KnowledgeBaseError


@dataclass(frozen=True, slots=True)
class TaxonomyFamilyDefinition:
    id: str
    label: str
    default_genres: tuple[str, ...] = ()
    allowed_route_anchors: tuple[str, ...] = ()
    required_traits: tuple[str, ...] = ()
    boundary_tendencies: tuple[str, ...] = ()
    compatibility_aliases: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class TaxonomySubfamilyDefinition:
    id: str
    family: str
    label: str


@dataclass(frozen=True, slots=True)
class RouteAnchorDefinition:
    key: str
    route_family: str
    label: str
    scope: str
    primary_directive: str | None = None
    exact_primary_candidates: tuple[str, ...] = ()
    prefix_primary_candidates: tuple[str, ...] = ()
    signal_genres: tuple[str, ...] = ()
    signal_traits: tuple[str, ...] = ()
    signal_families: tuple[str, ...] = ()
    signal_subfamilies: tuple[str, ...] = ()
    signal_boundary_tags: tuple[str, ...] = ()
    connected_mode: str = "ignore"
    wearable_mode: str = "ignore"
    boundary_tags: tuple[str, ...] = ()
    max_match_stage: str | None = None
    route_confidence_cap: str | None = None
    family_level_reason: str | None = None


@dataclass(frozen=True, slots=True)
class BoundaryRuleDefinition:
    id: str
    boundary_class: str
    label: str
    priority: int
    preferred_route_anchor: str | None = None
    families_any: tuple[str, ...] = ()
    subfamilies_any: tuple[str, ...] = ()
    genres_any: tuple[str, ...] = ()
    traits_any: tuple[str, ...] = ()
    boundary_tags_any: tuple[str, ...] = ()
    standard_prefixes_any: tuple[str, ...] = ()
    id_tokens_any: tuple[str, ...] = ()
    add_boundary_tags: tuple[str, ...] = ()
    max_match_stage: str | None = None
    confidence_cap: str | None = None
    key_missing_differentiators: tuple[str, ...] = ()
    concise_reason: str = ""


@dataclass(frozen=True, slots=True)
class TaxonomyResolution:
    family: str | None
    subfamily: str | None
    family_source: str
    subfamily_source: str
    compatibility_fallback_used: bool = False
    issues: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class TaxonomySnapshot:
    families_by_id: dict[str, TaxonomyFamilyDefinition]
    subfamilies_by_id: dict[str, TaxonomySubfamilyDefinition]
    family_aliases: dict[str, str]
    route_anchors_by_id: dict[str, RouteAnchorDefinition]
    boundary_rules: tuple[BoundaryRuleDefinition, ...]

    def family_definition(self, family_id: str | None) -> TaxonomyFamilyDefinition | None:
        if not family_id:
            return None
        canonical = self.family_aliases.get(family_id, family_id)
        return self.families_by_id.get(canonical)

    def subfamily_definition(self, subfamily_id: str | None) -> TaxonomySubfamilyDefinition | None:
        if not subfamily_id:
            return None
        return self.subfamilies_by_id.get(subfamily_id)

    def canonical_family(self, family_id: str | None) -> str | None:
        if not family_id:
            return None
        return self.family_aliases.get(family_id, family_id)


def _taxonomy_dir() -> Path:
    settings = get_settings()
    data_dir = settings.data_dir or (settings.project_root / "data")
    return (data_dir / "taxonomy").resolve()


def _load_taxonomy_yaml(filename: str) -> dict[str, Any]:
    path = _taxonomy_dir() / filename
    if not path.exists() or not path.is_file():
        raise KnowledgeBaseError(f"Missing taxonomy source: {path}")
    try:
        with open(path, "r", encoding="utf-8") as handle:
            payload = yaml.safe_load(handle)
    except yaml.YAMLError as exc:
        raise KnowledgeBaseError(f"Invalid YAML in taxonomy file {path.name}: {exc}") from exc
    except OSError as exc:
        raise KnowledgeBaseError(f"Could not read taxonomy file: {path}") from exc
    if payload is None:
        return {}
    if not isinstance(payload, dict):
        raise KnowledgeBaseError(f"Taxonomy file {path.name} must contain a top-level mapping.")
    return payload


def _string_tuple(value: Any, *, owner: str, key: str) -> tuple[str, ...]:
    if value is None:
        return ()
    if not isinstance(value, list):
        raise KnowledgeBaseError(f"{owner} field '{key}' must be a list when present.")
    items: list[str] = []
    for item in value:
        if not isinstance(item, str) or not item.strip():
            raise KnowledgeBaseError(f"{owner} field '{key}' must contain only non-empty strings.")
        items.append(item.strip())
    return tuple(items)


def _required_string(value: Any, *, owner: str, key: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise KnowledgeBaseError(f"{owner} field '{key}' is required.")
    return value.strip()


def _optional_string(value: Any, *, owner: str, key: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str) or not value.strip():
        raise KnowledgeBaseError(f"{owner} field '{key}' must be a non-empty string when present.")
    return value.strip()


def _required_int(value: Any, *, owner: str, key: str) -> int:
    if not isinstance(value, int):
        raise KnowledgeBaseError(f"{owner} field '{key}' is required and must be an integer.")
    return value


def _validate_enum(value: str | None, *, owner: str, key: str, allowed: set[str]) -> str | None:
    if value is None:
        return None
    if value not in allowed:
        raise KnowledgeBaseError(f"{owner} field '{key}' must be one of: {', '.join(sorted(allowed))}.")
    return value


def _load_families() -> tuple[dict[str, TaxonomyFamilyDefinition], dict[str, str]]:
    payload = _load_taxonomy_yaml("families.yaml")
    raw_rows = payload.get("families")
    if not isinstance(raw_rows, list):
        raise KnowledgeBaseError("taxonomy/families.yaml must contain a top-level 'families' list.")

    families_by_id: dict[str, TaxonomyFamilyDefinition] = {}
    family_aliases: dict[str, str] = {}

    for index, row in enumerate(raw_rows, start=1):
        if not isinstance(row, dict):
            raise KnowledgeBaseError(f"taxonomy/families.yaml family #{index} must be a mapping.")
        owner = f"Taxonomy family #{index}"
        family_id = _required_string(row.get("id"), owner=owner, key="id")
        if family_id in families_by_id:
            raise KnowledgeBaseError(f"Duplicate taxonomy family id: {family_id}")
        definition = TaxonomyFamilyDefinition(
            id=family_id,
            label=_required_string(row.get("label"), owner=owner, key="label"),
            default_genres=_string_tuple(row.get("default_genres"), owner=owner, key="default_genres"),
            allowed_route_anchors=_string_tuple(row.get("allowed_route_anchors"), owner=owner, key="allowed_route_anchors"),
            required_traits=_string_tuple(row.get("required_traits"), owner=owner, key="required_traits"),
            boundary_tendencies=_string_tuple(row.get("boundary_tendencies"), owner=owner, key="boundary_tendencies"),
            compatibility_aliases=_string_tuple(row.get("compatibility_aliases"), owner=owner, key="compatibility_aliases"),
        )
        families_by_id[family_id] = definition
        family_aliases[family_id] = family_id
        for alias in definition.compatibility_aliases:
            if alias in family_aliases and family_aliases[alias] != family_id:
                raise KnowledgeBaseError(f"Taxonomy family alias '{alias}' maps to multiple families.")
            family_aliases[alias] = family_id

    return families_by_id, family_aliases


def _load_subfamilies(family_aliases: dict[str, str]) -> dict[str, TaxonomySubfamilyDefinition]:
    payload = _load_taxonomy_yaml("subfamilies.yaml")
    raw_rows = payload.get("subfamilies")
    if not isinstance(raw_rows, list):
        raise KnowledgeBaseError("taxonomy/subfamilies.yaml must contain a top-level 'subfamilies' list.")

    subfamilies_by_id: dict[str, TaxonomySubfamilyDefinition] = {}
    for index, row in enumerate(raw_rows, start=1):
        if not isinstance(row, dict):
            raise KnowledgeBaseError(f"taxonomy/subfamilies.yaml subfamily #{index} must be a mapping.")
        owner = f"Taxonomy subfamily #{index}"
        subfamily_id = _required_string(row.get("id"), owner=owner, key="id")
        if subfamily_id in subfamilies_by_id:
            raise KnowledgeBaseError(f"Duplicate taxonomy subfamily id: {subfamily_id}")
        family = _required_string(row.get("family"), owner=owner, key="family")
        canonical_family = family_aliases.get(family, family)
        if canonical_family not in family_aliases.values():
            raise KnowledgeBaseError(f"{owner} references unknown family '{family}'.")
        subfamilies_by_id[subfamily_id] = TaxonomySubfamilyDefinition(
            id=subfamily_id,
            family=canonical_family,
            label=_required_string(row.get("label"), owner=owner, key="label"),
        )
    return subfamilies_by_id


def _load_route_anchors() -> dict[str, RouteAnchorDefinition]:
    payload = _load_taxonomy_yaml("route_anchors.yaml")
    raw_rows = payload.get("route_anchors")
    if not isinstance(raw_rows, list):
        raise KnowledgeBaseError("taxonomy/route_anchors.yaml must contain a top-level 'route_anchors' list.")

    anchors: dict[str, RouteAnchorDefinition] = {}
    for index, row in enumerate(raw_rows, start=1):
        if not isinstance(row, dict):
            raise KnowledgeBaseError(f"taxonomy/route_anchors.yaml route anchor #{index} must be a mapping.")
        owner = f"Route anchor #{index}"
        anchor_id = _required_string(row.get("id"), owner=owner, key="id")
        if anchor_id in anchors:
            raise KnowledgeBaseError(f"Duplicate route anchor id: {anchor_id}")
        anchors[anchor_id] = RouteAnchorDefinition(
            key=anchor_id,
            route_family=_required_string(row.get("route_family"), owner=owner, key="route_family"),
            label=_required_string(row.get("label"), owner=owner, key="label"),
            scope=_required_string(row.get("scope"), owner=owner, key="scope"),
            primary_directive=_optional_string(row.get("primary_directive"), owner=owner, key="primary_directive"),
            exact_primary_candidates=_string_tuple(row.get("exact_primary_candidates"), owner=owner, key="exact_primary_candidates"),
            prefix_primary_candidates=_string_tuple(row.get("prefix_primary_candidates"), owner=owner, key="prefix_primary_candidates"),
            signal_genres=_string_tuple(row.get("signal_genres"), owner=owner, key="signal_genres"),
            signal_traits=_string_tuple(row.get("signal_traits"), owner=owner, key="signal_traits"),
            signal_families=_string_tuple(row.get("signal_families"), owner=owner, key="signal_families"),
            signal_subfamilies=_string_tuple(row.get("signal_subfamilies"), owner=owner, key="signal_subfamilies"),
            signal_boundary_tags=_string_tuple(row.get("signal_boundary_tags"), owner=owner, key="signal_boundary_tags"),
            connected_mode=_validate_enum(
                _required_string(row.get("connected_mode", "ignore"), owner=owner, key="connected_mode"),
                owner=owner,
                key="connected_mode",
                allowed={"ignore", "prefer", "require", "avoid"},
            )
            or "ignore",
            wearable_mode=_validate_enum(
                _required_string(row.get("wearable_mode", "ignore"), owner=owner, key="wearable_mode"),
                owner=owner,
                key="wearable_mode",
                allowed={"ignore", "prefer", "require", "avoid"},
            )
            or "ignore",
            boundary_tags=_string_tuple(row.get("boundary_tags"), owner=owner, key="boundary_tags"),
            max_match_stage=_validate_enum(
                _optional_string(row.get("max_match_stage"), owner=owner, key="max_match_stage"),
                owner=owner,
                key="max_match_stage",
                allowed={"family", "subtype"},
            ),
            route_confidence_cap=_validate_enum(
                _optional_string(row.get("route_confidence_cap"), owner=owner, key="route_confidence_cap"),
                owner=owner,
                key="route_confidence_cap",
                allowed={"low", "medium", "high"},
            ),
            family_level_reason=_optional_string(row.get("family_level_reason"), owner=owner, key="family_level_reason"),
        )
    return anchors


def _load_boundary_rules(route_anchors: dict[str, RouteAnchorDefinition]) -> tuple[BoundaryRuleDefinition, ...]:
    payload = _load_taxonomy_yaml("boundaries.yaml")
    raw_rows = payload.get("boundaries")
    if not isinstance(raw_rows, list):
        raise KnowledgeBaseError("taxonomy/boundaries.yaml must contain a top-level 'boundaries' list.")

    rules: list[BoundaryRuleDefinition] = []
    seen_ids: set[str] = set()
    for index, row in enumerate(raw_rows, start=1):
        if not isinstance(row, dict):
            raise KnowledgeBaseError(f"taxonomy/boundaries.yaml rule #{index} must be a mapping.")
        owner = f"Boundary rule #{index}"
        rule_id = _required_string(row.get("id"), owner=owner, key="id")
        if rule_id in seen_ids:
            raise KnowledgeBaseError(f"Duplicate boundary rule id: {rule_id}")
        seen_ids.add(rule_id)
        preferred_route_anchor = _optional_string(row.get("preferred_route_anchor"), owner=owner, key="preferred_route_anchor")
        if preferred_route_anchor and preferred_route_anchor not in route_anchors:
            raise KnowledgeBaseError(f"{owner} references unknown preferred_route_anchor '{preferred_route_anchor}'.")
        rules.append(
            BoundaryRuleDefinition(
                id=rule_id,
                boundary_class=_required_string(row.get("boundary_class"), owner=owner, key="boundary_class"),
                label=_required_string(row.get("label"), owner=owner, key="label"),
                priority=_required_int(row.get("priority"), owner=owner, key="priority"),
                preferred_route_anchor=preferred_route_anchor,
                families_any=_string_tuple(row.get("families_any"), owner=owner, key="families_any"),
                subfamilies_any=_string_tuple(row.get("subfamilies_any"), owner=owner, key="subfamilies_any"),
                genres_any=_string_tuple(row.get("genres_any"), owner=owner, key="genres_any"),
                traits_any=_string_tuple(row.get("traits_any"), owner=owner, key="traits_any"),
                boundary_tags_any=_string_tuple(row.get("boundary_tags_any"), owner=owner, key="boundary_tags_any"),
                standard_prefixes_any=_string_tuple(row.get("standard_prefixes_any"), owner=owner, key="standard_prefixes_any"),
                id_tokens_any=_string_tuple(row.get("id_tokens_any"), owner=owner, key="id_tokens_any"),
                add_boundary_tags=_string_tuple(row.get("add_boundary_tags"), owner=owner, key="add_boundary_tags"),
                max_match_stage=_validate_enum(
                    _optional_string(row.get("max_match_stage"), owner=owner, key="max_match_stage"),
                    owner=owner,
                    key="max_match_stage",
                    allowed={"family", "subtype"},
                ),
                confidence_cap=_validate_enum(
                    _optional_string(row.get("confidence_cap"), owner=owner, key="confidence_cap"),
                    owner=owner,
                    key="confidence_cap",
                    allowed={"low", "medium", "high"},
                ),
                key_missing_differentiators=_string_tuple(
                    row.get("key_missing_differentiators"),
                    owner=owner,
                    key="key_missing_differentiators",
                ),
                concise_reason=_required_string(row.get("concise_reason"), owner=owner, key="concise_reason"),
            )
        )

    rules.sort(key=lambda rule: (-rule.priority, rule.id))
    return tuple(rules)


@lru_cache(maxsize=1)
def get_taxonomy_snapshot() -> TaxonomySnapshot:
    families_by_id, family_aliases = _load_families()
    subfamilies_by_id = _load_subfamilies(family_aliases)
    route_anchors_by_id = _load_route_anchors()
    boundary_rules = _load_boundary_rules(route_anchors_by_id)

    for family in families_by_id.values():
        for anchor in family.allowed_route_anchors:
            if anchor not in route_anchors_by_id:
                raise KnowledgeBaseError(
                    f"Taxonomy family '{family.id}' allows unknown route anchor '{anchor}'."
                )

    return TaxonomySnapshot(
        families_by_id=families_by_id,
        subfamilies_by_id=subfamilies_by_id,
        family_aliases=family_aliases,
        route_anchors_by_id=route_anchors_by_id,
        boundary_rules=boundary_rules,
    )


def reset_taxonomy_cache() -> None:
    get_taxonomy_snapshot.cache_clear()


def resolve_product_taxonomy(
    *,
    product_id: str,
    declared_family: str | None,
    declared_subfamily: str | None,
    allow_legacy_fallback: bool,
) -> TaxonomyResolution:
    snapshot = get_taxonomy_snapshot()
    issues: list[str] = []
    compatibility_fallback_used = False

    canonical_family = snapshot.canonical_family(declared_family)
    family_source = "missing"
    if canonical_family:
        if canonical_family not in snapshot.families_by_id:
            issues.append(f"unknown_family:{canonical_family}")
            canonical_family = None
        else:
            family_source = "declared"

    canonical_subfamily = declared_subfamily.strip() if declared_subfamily and declared_subfamily.strip() else None
    subfamily_source = "missing"
    subfamily_definition = snapshot.subfamily_definition(canonical_subfamily)
    if canonical_subfamily:
        if subfamily_definition is None:
            issues.append(f"unknown_subfamily:{canonical_subfamily}")
        else:
            canonical_subfamily = subfamily_definition.id
            subfamily_source = "declared"
            if canonical_family is None:
                canonical_family = subfamily_definition.family
                family_source = "taxonomy_subfamily"
            elif canonical_family != subfamily_definition.family:
                issues.append(f"subfamily_family_mismatch:{canonical_subfamily}:{canonical_family}")
                canonical_family = subfamily_definition.family
                family_source = "taxonomy_subfamily"

    if canonical_subfamily is None:
        id_definition = snapshot.subfamily_definition(product_id)
        if id_definition is not None:
            canonical_subfamily = id_definition.id
            subfamily_source = "taxonomy_id"
            if canonical_family is None:
                canonical_family = id_definition.family
                family_source = "taxonomy_id"
            elif canonical_family != id_definition.family:
                issues.append(f"id_family_mismatch:{product_id}:{canonical_family}")
                canonical_family = id_definition.family
                family_source = "taxonomy_id"

    if canonical_family is None and allow_legacy_fallback:
        canonical_family = product_id
        family_source = "compatibility_product_id"
        compatibility_fallback_used = True
        issues.append("compatibility_family_fallback")

    if canonical_subfamily is None and allow_legacy_fallback:
        canonical_subfamily = product_id
        subfamily_source = "compatibility_product_id"
        compatibility_fallback_used = True
        issues.append("compatibility_subfamily_fallback")

    return TaxonomyResolution(
        family=canonical_family,
        subfamily=canonical_subfamily,
        family_source=family_source,
        subfamily_source=subfamily_source,
        compatibility_fallback_used=compatibility_fallback_used,
        issues=tuple(issues),
    )


def validate_product_taxonomy_row(row: dict[str, Any]) -> None:
    snapshot = get_taxonomy_snapshot()
    owner = f"Product '{row.get('id')}'"

    family = _optional_string(row.get("product_family"), owner=owner, key="product_family")
    canonical_family = snapshot.canonical_family(family)
    if canonical_family is not None and canonical_family not in snapshot.families_by_id:
        raise KnowledgeBaseError(f"{owner} field 'product_family' references unknown taxonomy family '{family}'.")

    subfamily = _optional_string(row.get("product_subfamily"), owner=owner, key="product_subfamily")
    if subfamily is not None:
        subfamily_definition = snapshot.subfamily_definition(subfamily)
        if subfamily_definition is None:
            raise KnowledgeBaseError(f"{owner} field 'product_subfamily' references unknown taxonomy subfamily '{subfamily}'.")
        if canonical_family is not None and subfamily_definition.family != canonical_family:
            raise KnowledgeBaseError(
                f"{owner} field 'product_subfamily' belongs to family '{subfamily_definition.family}', not '{canonical_family}'."
            )

    route_anchor = _optional_string(row.get("route_anchor"), owner=owner, key="route_anchor")
    if route_anchor is not None and route_anchor not in snapshot.route_anchors_by_id:
        raise KnowledgeBaseError(f"{owner} field 'route_anchor' references unknown route anchor '{route_anchor}'.")

    if route_anchor is not None and canonical_family is not None:
        family_definition = snapshot.family_definition(canonical_family)
        if family_definition and family_definition.allowed_route_anchors and route_anchor not in family_definition.allowed_route_anchors:
            raise KnowledgeBaseError(
                f"{owner} field 'route_anchor' is not allowed for taxonomy family '{canonical_family}'."
            )

    route_family = _optional_string(row.get("route_family"), owner=owner, key="route_family")
    if route_anchor is not None and route_family is not None:
        anchor_definition = snapshot.route_anchors_by_id[route_anchor]
        if route_family != anchor_definition.route_family:
            raise KnowledgeBaseError(
                f"{owner} field 'route_family' must match route anchor '{route_anchor}' family '{anchor_definition.route_family}'."
            )


def validate_taxonomy_snapshot(*, trait_ids: set[str], genre_ids: set[str]) -> None:
    snapshot = get_taxonomy_snapshot()

    for family in snapshot.families_by_id.values():
        for genre in family.default_genres:
            if genre not in genre_ids:
                raise KnowledgeBaseError(
                    f"Taxonomy family '{family.id}' references unknown default genre '{genre}'."
                )
        for trait in family.required_traits:
            if trait not in trait_ids:
                raise KnowledgeBaseError(
                    f"Taxonomy family '{family.id}' references unknown required trait '{trait}'."
                )

    family_ids = set(snapshot.families_by_id)
    subfamily_ids = set(snapshot.subfamilies_by_id)

    for anchor in snapshot.route_anchors_by_id.values():
        for genre in anchor.signal_genres:
            if genre not in genre_ids:
                raise KnowledgeBaseError(
                    f"Route anchor '{anchor.key}' references unknown signal genre '{genre}'."
                )
        for family_id in anchor.signal_families:
            if family_id not in family_ids:
                raise KnowledgeBaseError(
                    f"Route anchor '{anchor.key}' references unknown signal family '{family_id}'."
                )
        for subfamily_id in anchor.signal_subfamilies:
            if subfamily_id not in subfamily_ids:
                raise KnowledgeBaseError(
                    f"Route anchor '{anchor.key}' references unknown signal subfamily '{subfamily_id}'."
                )

    for rule in snapshot.boundary_rules:
        for family_id in rule.families_any:
            if family_id not in family_ids:
                raise KnowledgeBaseError(
                    f"Boundary rule '{rule.id}' references unknown family '{family_id}'."
                )
        for subfamily_id in rule.subfamilies_any:
            if subfamily_id not in subfamily_ids:
                raise KnowledgeBaseError(
                    f"Boundary rule '{rule.id}' references unknown subfamily '{subfamily_id}'."
                )
        for genre in rule.genres_any:
            if genre not in genre_ids:
                raise KnowledgeBaseError(
                    f"Boundary rule '{rule.id}' references unknown genre '{genre}'."
                )
        for trait in rule.traits_any:
            if trait not in trait_ids:
                raise KnowledgeBaseError(
                    f"Boundary rule '{rule.id}' references unknown trait '{trait}'."
                )


__all__ = [
    "BoundaryRuleDefinition",
    "RouteAnchorDefinition",
    "TaxonomyFamilyDefinition",
    "TaxonomyResolution",
    "TaxonomySnapshot",
    "TaxonomySubfamilyDefinition",
    "get_taxonomy_snapshot",
    "reset_taxonomy_cache",
    "resolve_product_taxonomy",
    "validate_taxonomy_snapshot",
    "validate_product_taxonomy_row",
]
