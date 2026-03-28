from __future__ import annotations

from typing import Any

from app.domain.catalog_types import LikelyStandardRef

from .paths import KnowledgeBaseError


def _require_list(parent: dict[str, Any], key: str, filename: str) -> list[Any]:
    value = parent.get(key)
    if not isinstance(value, list):
        raise KnowledgeBaseError(f"{filename} must contain a top-level '{key}' list.")
    return value


def _optional_list(parent: dict[str, Any], key: str) -> list[Any]:
    value = parent.get(key)
    if value is None:
        return []
    if not isinstance(value, list):
        raise KnowledgeBaseError(f"Optional key '{key}' must be a list when present.")
    return value

ALLOWED_HARMONIZATION_STATUSES = {"harmonized", "state_of_the_art", "review", "unknown"}
ALLOWED_FACT_BASIS = {"confirmed", "mixed", "inferred"}
ALLOWED_TEST_FOCUS = {
    "safety",
    "mechanical",
    "electrical",
    "emc",
    "emission",
    "immunity",
    "harmonics",
    "flicker",
    "rf",
    "emf",
    "cybersecurity",
    "privacy",
    "materials",
    "food_contact",
    "software",
    "battery",
    "energy",
}

def _string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, str) and item.strip()]


def _dedupe_keep_order(items: list[Any]) -> list[Any]:
    out: list[Any] = []
    seen: set[str] = set()
    for item in items:
        key = repr(item)
        if key in seen:
            continue
        seen.add(key)
        out.append(item)
    return out


def _merge_records(base_rows: list[dict[str, Any]], extra_rows: list[dict[str, Any]], id_key: str) -> list[dict[str, Any]]:
    merged: dict[str, dict[str, Any]] = {}
    order: list[str] = []

    def apply(row: dict[str, Any]) -> None:
        if not isinstance(row, dict):
            raise KnowledgeBaseError(f"Merged record for '{id_key}' must be a mapping.")
        key = row.get(id_key)
        if not isinstance(key, str) or not key.strip():
            raise KnowledgeBaseError(f"Merged record missing valid '{id_key}'.")
        key = key.strip()
        if key not in merged:
            merged[key] = {}
            order.append(key)
        target = merged[key]
        for field, value in row.items():
            if field == id_key:
                target[field] = key
                continue
            if isinstance(value, list):
                target[field] = _dedupe_keep_order(list(target.get(field, [])) + value)
            elif isinstance(value, dict) and isinstance(target.get(field), dict):
                tmp = dict(target[field])
                tmp.update(value)
                target[field] = tmp
            else:
                target[field] = value

    for row in base_rows:
        apply(row)
    for row in extra_rows:
        apply(row)

    return [merged[key] for key in order]


# ---------- validation ----------

def _validate_traits(data: dict[str, Any]) -> list[dict[str, Any]]:
    traits = _require_list(data, "traits", "traits.yaml")
    seen: set[str] = set()

    for idx, row in enumerate(traits, start=1):
        if not isinstance(row, dict):
            raise KnowledgeBaseError(f"traits.yaml trait #{idx} must be a mapping.")
        for field in ("id", "label", "description"):
            value = row.get(field)
            if not isinstance(value, str) or not value.strip():
                raise KnowledgeBaseError(f"traits.yaml trait #{idx} is missing a valid '{field}'.")
        trait_id = row["id"]
        if trait_id in seen:
            raise KnowledgeBaseError(f"Duplicate trait id in merged trait catalog: {trait_id}")
        seen.add(trait_id)
    return traits


def _validate_genres(data: dict[str, Any], trait_ids: set[str]) -> list[dict[str, Any]]:
    genres = _optional_list(data, "genres")
    seen: set[str] = set()
    for idx, row in enumerate(genres, start=1):
        if not isinstance(row, dict):
            raise KnowledgeBaseError(f"product_genres.yaml genre #{idx} must be a mapping.")
        for field in ("id", "label"):
            value = row.get(field)
            if not isinstance(value, str) or not value.strip():
                raise KnowledgeBaseError(f"product_genres.yaml genre #{idx} is missing a valid '{field}'.")
        genre_id = row["id"]
        if genre_id in seen:
            raise KnowledgeBaseError(f"Duplicate genre id in product_genres.yaml: {genre_id}")
        seen.add(genre_id)
        for key in ("traits", "default_traits"):
            for trait in _string_list(row.get(key)):
                if trait not in trait_ids:
                    raise KnowledgeBaseError(f"Genre '{genre_id}' references unknown trait '{trait}'.")
        for key in ("keywords", "functional_classes", "likely_standards"):
            value = row.get(key, [])
            if value is not None and not isinstance(value, list):
                raise KnowledgeBaseError(f"Genre '{genre_id}' field '{key}' must be a list when present.")
        _normalize_likely_standard_refs(row, f"Genre '{genre_id}'")
    return genres


def _validate_products(data: dict[str, Any], trait_ids: set[str], genre_ids: set[str] | None = None) -> list[dict[str, Any]]:
    products = _require_list(data, "products", "products.yaml")
    seen: set[str] = set()
    genre_ids = genre_ids or set()

    for idx, row in enumerate(products, start=1):
        if not isinstance(row, dict):
            raise KnowledgeBaseError(f"products.yaml product #{idx} must be a mapping.")
        for field in ("id", "label"):
            value = row.get(field)
            if not isinstance(value, str) or not value.strip():
                raise KnowledgeBaseError(f"products.yaml product #{idx} is missing a valid '{field}'.")

        pid = row["id"]
        if pid in seen:
            raise KnowledgeBaseError(f"Duplicate product id in merged product catalog: {pid}")
        seen.add(pid)

        aliases = row.get("aliases", [])
        if not isinstance(aliases, list) or not aliases or not all(isinstance(item, str) and item.strip() for item in aliases):
            raise KnowledgeBaseError(f"Product '{pid}' must define a non-empty aliases list.")

        for field in ("product_family", "product_subfamily"):
            value = row.get(field)
            if value is not None and (not isinstance(value, str) or not value.strip()):
                raise KnowledgeBaseError(f"Product '{pid}' field '{field}' must be a non-empty string when provided.")
        if row.get("confusable_with") and not row.get("product_family"):
            raise KnowledgeBaseError(f"Product '{pid}' field 'confusable_with' requires product_family to be set.")

        for key in ("implied_traits", "functional_classes", "likely_standards", "family_keywords", "genres"):
            value = row.get(key, [])
            if not isinstance(value, list):
                raise KnowledgeBaseError(f"Product '{pid}' field '{key}' must be a list.")
            for item in value:
                if not isinstance(item, str) or not item.strip():
                    raise KnowledgeBaseError(f"Product '{pid}' field '{key}' must contain only non-empty strings.")
            if key == "implied_traits":
                for trait in value:
                    if trait not in trait_ids:
                        raise KnowledgeBaseError(f"Product '{pid}' references unknown trait '{trait}'.")
            if key == "genres":
                for genre in value:
                    if genre not in genre_ids:
                        raise KnowledgeBaseError(f"Product '{pid}' references unknown genre '{genre}'.")

        _normalize_likely_standard_refs(row, f"Product '{pid}'")

        for key in ("core_traits", "default_traits", "required_clues", "preferred_clues", "exclude_clues", "confusable_with", "family_traits", "subtype_traits"):
            value = row.get(key, [])
            if not isinstance(value, list):
                raise KnowledgeBaseError(f"Product '{pid}' field '{key}' must be a list.")
            for item in value:
                if not isinstance(item, str) or not item.strip():
                    raise KnowledgeBaseError(f"Product '{pid}' field '{key}' must contain only non-empty strings.")
            if key in {"core_traits", "default_traits", "family_traits", "subtype_traits"}:
                for trait in value:
                    if trait not in trait_ids:
                        raise KnowledgeBaseError(f"Product '{pid}' field '{key}' references unknown trait '{trait}'.")

    for row in products:
        pid = row["id"]
        for other in row.get("confusable_with", []):
            if other not in seen:
                raise KnowledgeBaseError(f"Product '{pid}' field 'confusable_with' references unknown product '{other}'.")

    return products


def _validate_legislations(data: dict[str, Any], product_ids: set[str], trait_ids: set[str], genre_ids: set[str]) -> list[dict[str, Any]]:
    legislations = _require_list(data, "legislations", "legislation_catalog.yaml")
    seen_codes: set[str] = set()
    allowed_priorities = {"core", "product_specific", "conditional", "informational"}
    allowed_applicability = {"applicable", "conditional", "not_applicable"}
    allowed_buckets = {"ce", "non_ce", "framework", "future", "informational"}

    for idx, row in enumerate(legislations, start=1):
        if not isinstance(row, dict):
            raise KnowledgeBaseError(f"legislation_catalog.yaml legislation #{idx} must be a mapping.")
        for field in ("code", "title", "family", "directive_key"):
            value = row.get(field)
            if not isinstance(value, str) or not value.strip():
                raise KnowledgeBaseError(f"legislation_catalog.yaml entry #{idx} is missing a valid '{field}'.")

        code = row["code"]
        if code in seen_codes:
            raise KnowledgeBaseError(f"Duplicate legislation code in merged legislation catalog: {code}")
        seen_codes.add(code)

        if row.get("priority", "conditional") not in allowed_priorities:
            raise KnowledgeBaseError(f"Legislation '{code}' has invalid priority '{row.get('priority')}'.")
        if row.get("applicability", "conditional") not in allowed_applicability:
            raise KnowledgeBaseError(f"Legislation '{code}' has invalid applicability '{row.get('applicability')}'.")
        if row.get("bucket", "non_ce") not in allowed_buckets:
            raise KnowledgeBaseError(f"Legislation '{code}' has invalid bucket '{row.get('bucket')}'.")

        for field in (
            "triggers",
            "doc_impacts",
            "all_of_traits",
            "any_of_traits",
            "none_of_traits",
            "all_of_functional_classes",
            "any_of_functional_classes",
            "none_of_functional_classes",
            "any_of_product_types",
            "exclude_product_types",
            "any_of_genres",
            "exclude_genres",
        ):
            value = row.get(field, [])
            if not isinstance(value, list):
                raise KnowledgeBaseError(f"Legislation '{code}' field '{field}' must be a list.")

        for trait_field in ("all_of_traits", "any_of_traits", "none_of_traits"):
            for trait in row.get(trait_field, []):
                if trait not in trait_ids:
                    raise KnowledgeBaseError(f"Legislation '{code}' references unknown trait '{trait}'.")

        for product_field in ("any_of_product_types", "exclude_product_types"):
            for pid in row.get(product_field, []):
                if pid not in product_ids:
                    raise KnowledgeBaseError(f"Legislation '{code}' references unknown product id '{pid}'.")

        for genre_field in ("any_of_genres", "exclude_genres"):
            for genre in row.get(genre_field, []):
                if genre not in genre_ids:
                    raise KnowledgeBaseError(f"Legislation '{code}' references unknown genre '{genre}'.")

    return legislations


def _validate_standard_metadata(code: str, row: dict[str, Any]) -> None:
    bool_fields = ("is_harmonized",)
    list_fields = ("test_focus", "evidence_hint", "keywords", "applies_if_genres", "exclude_if_genres")
    str_fields = (
        "standard_family",
        "harmonized_under",
        "harmonized_reference",
        "version",
        "dated_version",
        "supersedes",
        "harmonization_status",
        "selection_group",
        "required_fact_basis",
    )

    for field in bool_fields:
        if field in row and not isinstance(row[field], bool):
            raise KnowledgeBaseError(f"Standard '{code}' field '{field}' must be boolean.")
    for field in list_fields:
        if field in row and not isinstance(row[field], list):
            raise KnowledgeBaseError(f"Standard '{code}' field '{field}' must be a list.")
        for item in row.get(field, []):
            if not isinstance(item, str):
                raise KnowledgeBaseError(f"Standard '{code}' field '{field}' must contain only strings.")
    for field in str_fields:
        if field in row and row[field] is not None and not isinstance(row[field], str):
            raise KnowledgeBaseError(f"Standard '{code}' field '{field}' must be a string or null.")

    harmonization_status = row.get("harmonization_status")
    if harmonization_status and harmonization_status not in ALLOWED_HARMONIZATION_STATUSES:
        raise KnowledgeBaseError(f"Standard '{code}' has invalid harmonization_status '{harmonization_status}'.")

    required_fact_basis = row.get("required_fact_basis")
    if required_fact_basis and required_fact_basis not in ALLOWED_FACT_BASIS:
        raise KnowledgeBaseError(f"Standard '{code}' has invalid required_fact_basis '{required_fact_basis}'.")

    if "selection_priority" in row and not isinstance(row["selection_priority"], int):
        raise KnowledgeBaseError(f"Standard '{code}' field 'selection_priority' must be an integer.")

    test_focus = row.get("test_focus", [])
    invalid_test_focus = [item for item in test_focus if item not in ALLOWED_TEST_FOCUS]
    if invalid_test_focus:
        raise KnowledgeBaseError(f"Standard '{code}' has invalid test_focus values: {', '.join(invalid_test_focus)}.")

    is_harmonized = row.get("is_harmonized")
    if is_harmonized is True and not (row.get("harmonized_under") or row.get("harmonized_reference")):
        raise KnowledgeBaseError(f"Standard '{code}' is marked harmonized but lacks harmonized_under or harmonized_reference.")
    if row.get("item_type") == "review" and is_harmonized is True:
        raise KnowledgeBaseError(f"Standard '{code}' cannot be both a review item and harmonized.")
    if harmonization_status == "harmonized" and is_harmonized is False:
        raise KnowledgeBaseError(f"Standard '{code}' has harmonization_status='harmonized' but is_harmonized=false.")
    if harmonization_status == "review" and row.get("item_type") != "review":
        raise KnowledgeBaseError(f"Standard '{code}' has harmonization_status='review' but item_type is not 'review'.")


def _validate_standards(data: dict[str, Any], product_ids: set[str], trait_ids: set[str], legislation_keys: set[str], genre_ids: set[str]) -> list[dict[str, Any]]:
    standards = _require_list(data, "standards", "standards.yaml")
    seen: set[str] = set()

    for idx, row in enumerate(standards, start=1):
        if not isinstance(row, dict):
            raise KnowledgeBaseError(f"standards.yaml standard #{idx} must be a mapping.")
        for field in ("code", "title", "category"):
            value = row.get(field)
            if not isinstance(value, str) or not value.strip():
                raise KnowledgeBaseError(f"standards.yaml entry #{idx} is missing a valid '{field}'.")

        code = row["code"]
        if code in seen:
            raise KnowledgeBaseError(f"Duplicate standard code in merged standards catalog: {code}")
        seen.add(code)

        directives = row.get("directives", [])
        if not isinstance(directives, list):
            raise KnowledgeBaseError(f"Standard '{code}' must have a directives list.")
        for directive in directives:
            if not isinstance(directive, str) or not directive.strip():
                raise KnowledgeBaseError(f"Standard '{code}' has an invalid directive entry.")

        legislation_key = row.get("legislation_key")
        if legislation_key is not None:
            if not isinstance(legislation_key, str) or not legislation_key.strip():
                raise KnowledgeBaseError(f"Standard '{code}' has invalid legislation_key.")
            if legislation_key not in legislation_keys:
                raise KnowledgeBaseError(f"Standard '{code}' references unknown legislation_key '{legislation_key}'.")

        for field in ("applies_if_all", "applies_if_any", "exclude_if", "applies_if_products", "exclude_if_products"):
            value = row.get(field, [])
            if not isinstance(value, list):
                raise KnowledgeBaseError(f"Standard '{code}' field '{field}' must be a list.")
            if field.endswith("_products"):
                for pid in value:
                    if pid not in product_ids:
                        raise KnowledgeBaseError(f"Standard '{code}' references unknown product id '{pid}'.")
            else:
                for trait in value:
                    if trait not in trait_ids:
                        raise KnowledgeBaseError(f"Standard '{code}' references unknown trait '{trait}'.")

        for genre_field in ("applies_if_genres", "exclude_if_genres"):
            for genre in row.get(genre_field, []):
                if genre not in genre_ids:
                    raise KnowledgeBaseError(f"Standard '{code}' references unknown genre '{genre}'.")

        item_type = row.get("item_type")
        if item_type is not None and item_type not in {"standard", "review"}:
            raise KnowledgeBaseError(f"Standard '{code}' has invalid item_type '{item_type}'.")

        _validate_standard_metadata(code, row)

    return standards

def _normalize_likely_standard_refs(row: dict[str, Any], owner: str) -> list[dict[str, str]]:
    raw_refs = row.get("likely_standard_refs")
    if raw_refs is None:
        return [{"ref": ref, "kind": "unspecified"} for ref in _string_list(row.get("likely_standards"))]
    if not isinstance(raw_refs, list):
        raise KnowledgeBaseError(f"{owner} field 'likely_standard_refs' must be a list when present.")

    refs: list[dict[str, str]] = []
    for item in raw_refs:
        if isinstance(item, str) and item.strip():
            refs.append({"ref": item.strip(), "kind": "unspecified"})
            continue
        if not isinstance(item, dict):
            raise KnowledgeBaseError(f"{owner} field 'likely_standard_refs' must contain strings or mappings.")
        ref = item.get("ref")
        kind = item.get("kind") or "unspecified"
        if not isinstance(ref, str) or not ref.strip():
            raise KnowledgeBaseError(f"{owner} field 'likely_standard_refs' contains an item without a valid 'ref'.")
        if not isinstance(kind, str) or not kind.strip():
            raise KnowledgeBaseError(f"{owner} field 'likely_standard_refs' contains an item without a valid 'kind'.")
        refs.append({"ref": ref.strip(), "kind": kind.strip()})
    return refs


def _materialize_likely_standard_refs(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    materialized: list[dict[str, Any]] = []
    for row in rows:
        enriched = dict(row)
        enriched["likely_standard_refs"] = [
            ref if isinstance(ref, LikelyStandardRef) else LikelyStandardRef.model_validate(ref)
            for ref in enriched.get("likely_standard_refs", [])
        ]
        materialized.append(enriched)
    return materialized


__all__ = [
    "ALLOWED_FACT_BASIS",
    "ALLOWED_HARMONIZATION_STATUSES",
    "ALLOWED_TEST_FOCUS",
    "_dedupe_keep_order",
    "_materialize_likely_standard_refs",
    "_merge_records",
    "_normalize_likely_standard_refs",
    "_optional_list",
    "_string_list",
    "_validate_genres",
    "_validate_legislations",
    "_validate_products",
    "_validate_standard_metadata",
    "_validate_standards",
    "_validate_traits",
]
