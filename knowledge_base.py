from __future__ import annotations

from functools import lru_cache
from pathlib import Path
import os
import re
from typing import Any

import yaml

from env_config import init_env

init_env()


class KnowledgeBaseError(RuntimeError):
    pass


BASE_DIR = Path(__file__).resolve().parent
KB_META_VERSION = "7.0.0"
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
OPTIONAL_EXTENSION_FILES = {
    "trait_extensions.yaml": "traits",
    "product_genres.yaml": "genres",
    "product_extensions.yaml": "products",
    "legislation_extensions.yaml": "legislations",
    "standard_extensions.yaml": "standards",
}


# ---------- path helpers ----------

def _candidate_dirs() -> list[Path]:
    dirs: list[Path] = []

    env_dir = os.getenv("REGCHECK_DATA_DIR")
    if env_dir:
        dirs.append(Path(env_dir).resolve())

    cwd = Path.cwd().resolve()
    dirs.extend(
        [
            BASE_DIR,
            BASE_DIR / "data",
            BASE_DIR.parent,
            BASE_DIR.parent / "data",
            cwd,
            cwd / "data",
            cwd / "app",
            cwd / "app" / "data",
            cwd / "backend",
            cwd / "backend" / "data",
        ]
    )

    unique: list[Path] = []
    seen: set[str] = set()
    for d in dirs:
        key = str(d)
        if key not in seen:
            seen.add(key)
            unique.append(d)

    return unique


def _resolve_data_path(filename: str, *, required: bool = True) -> Path | None:
    for directory in _candidate_dirs():
        candidate = directory / filename
        if candidate.exists() and candidate.is_file():
            return candidate

    if not required:
        return None

    tried = "\n".join(str(directory / filename) for directory in _candidate_dirs())
    raise KnowledgeBaseError(f"Missing knowledge-base file: {filename}. Tried:\n{tried}")


def _load_yaml_raw(filename: str, *, required: bool = True) -> dict[str, Any]:
    path = _resolve_data_path(filename, required=required)
    if path is None:
        return {}

    try:
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
    except yaml.YAMLError as exc:
        raise KnowledgeBaseError(f"Invalid YAML in {path.name}: {exc}") from exc
    except OSError as exc:
        raise KnowledgeBaseError(f"Could not read knowledge-base file: {path}") from exc

    if data is None:
        return {}
    if not isinstance(data, dict):
        raise KnowledgeBaseError(f"{path.name} must contain a top-level mapping.")
    return data


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


# ---------- low-level merge helpers ----------

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


# ---------- enrich ----------

def _normalize_standard_code(code: str) -> str:
    value = re.sub(r"\s+", " ", (code or "").strip())
    if value.startswith("EN EN "):
        value = value.replace("EN EN ", "EN ", 1)
    return value


def _derive_harmonization_status(row: dict[str, Any]) -> str:
    explicit = row.get("harmonization_status")
    if explicit in ALLOWED_HARMONIZATION_STATUSES:
        return explicit
    if row.get("item_type") == "review":
        return "review"
    if row.get("is_harmonized") is True:
        return "harmonized"
    if row.get("is_harmonized") is False:
        return "state_of_the_art"
    return "unknown"


def _genre_map(genres: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {row["id"]: row for row in genres}


def _expand_genre_product_ids(target_genres: list[str], products: list[dict[str, Any]]) -> list[str]:
    wanted = set(target_genres)
    return [row["id"] for row in products if wanted & set(_string_list(row.get("genres")))]


def _enrich_products(rows: list[dict[str, Any]], genres: list[dict[str, Any]]) -> list[dict[str, Any]]:
    genre_index = _genre_map(genres)
    out: list[dict[str, Any]] = []
    for row in rows:
        enriched = dict(row)
        enriched["product_family"] = enriched.get("product_family") or enriched["id"]
        enriched["product_subfamily"] = enriched.get("product_subfamily") or enriched["id"]
        enriched.setdefault("required_clues", [])
        enriched.setdefault("preferred_clues", [])
        enriched.setdefault("exclude_clues", [])
        enriched.setdefault("confusable_with", [])
        enriched.setdefault("family_traits", [])
        enriched.setdefault("subtype_traits", list(enriched.get("implied_traits", [])))
        enriched.setdefault("family_keywords", [])
        enriched.setdefault("genres", [])
        enriched.setdefault("genre_keywords", [])
        enriched.setdefault("genre_traits", [])
        enriched.setdefault("genre_default_traits", [])
        enriched.setdefault("genre_functional_classes", [])
        enriched.setdefault("genre_likely_standards", [])

        for genre_id in enriched["genres"]:
            genre = genre_index.get(genre_id)
            if not genre:
                continue
            enriched["genre_keywords"] = _dedupe_keep_order(_string_list(enriched.get("genre_keywords")) + _string_list(genre.get("keywords")))
            enriched["genre_traits"] = _dedupe_keep_order(_string_list(enriched.get("genre_traits")) + _string_list(genre.get("traits")))
            enriched["genre_default_traits"] = _dedupe_keep_order(_string_list(enriched.get("genre_default_traits")) + _string_list(genre.get("default_traits")))
            enriched["genre_functional_classes"] = _dedupe_keep_order(
                _string_list(enriched.get("genre_functional_classes")) + _string_list(genre.get("functional_classes"))
            )
            enriched["genre_likely_standards"] = _dedupe_keep_order(
                _string_list(enriched.get("genre_likely_standards")) + _string_list(genre.get("likely_standards"))
            )
            enriched["family_keywords"] = _dedupe_keep_order(_string_list(enriched.get("family_keywords")) + _string_list(genre.get("keywords")))
            enriched["family_traits"] = _dedupe_keep_order(_string_list(enriched.get("family_traits")) + _string_list(genre.get("traits")))
            enriched["default_traits"] = _dedupe_keep_order(_string_list(enriched.get("default_traits")) + _string_list(genre.get("default_traits")))

        core_traits = list(enriched.get("core_traits") or [])
        default_traits = list(enriched.get("default_traits") or [])
        if not core_traits and enriched.get("family_traits"):
            core_traits.extend(list(enriched.get("family_traits") or []))
        if not core_traits and enriched.get("subtype_traits"):
            core_traits.extend(list(enriched.get("subtype_traits") or []))
        if not core_traits:
            core_traits.extend(list(enriched.get("implied_traits") or []))
        if not default_traits:
            default_traits.extend(list(enriched.get("implied_traits") or []))
        enriched["core_traits"] = list(dict.fromkeys(core_traits))
        enriched["default_traits"] = [trait for trait in dict.fromkeys(default_traits) if trait not in enriched["core_traits"]]
        out.append(enriched)
    return out


def _enrich_legislations(rows: list[dict[str, Any]], products: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [dict(row) for row in rows]


def _enrich_standards(rows: list[dict[str, Any]], products: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    seen_normalized_codes: set[str] = set()
    for row in rows:
        enriched = dict(row)
        enriched["code"] = _normalize_standard_code(enriched.get("code", ""))
        if enriched["code"] in seen_normalized_codes:
            raise KnowledgeBaseError(f"Duplicate normalized standard code in merged standards catalog: {enriched['code']}")
        seen_normalized_codes.add(enriched["code"])
        enriched["standard_family"] = enriched.get("standard_family") or enriched["code"].split(":", 1)[0].strip()
        enriched["harmonization_status"] = _derive_harmonization_status(enriched)
        enriched.setdefault("test_focus", [])
        enriched.setdefault("evidence_hint", [])
        enriched.setdefault("keywords", [])
        enriched.setdefault("selection_group", None)
        enriched.setdefault("selection_priority", 0)
        enriched["required_fact_basis"] = enriched.get("required_fact_basis") or "inferred"
        out.append(enriched)
    return out


def _post_validate_product_standard_links(
    products: list[dict[str, Any]],
    genres: list[dict[str, Any]],
    standards: list[dict[str, Any]],
) -> None:
    known_references = {row["code"] for row in standards} | {
        row.get("standard_family") for row in standards if isinstance(row.get("standard_family"), str)
    }

    for product in products:
        pid = product["id"]
        for reference in _string_list(product.get("likely_standards")):
            if reference not in known_references:
                raise KnowledgeBaseError(
                    f"Product '{pid}' references likely_standard '{reference}' that does not match any standard code or family."
                )

    for genre in genres:
        gid = genre["id"]
        for reference in _string_list(genre.get("likely_standards")):
            if reference not in known_references:
                raise KnowledgeBaseError(
                    f"Genre '{gid}' references likely_standard '{reference}' that does not match any standard code or family."
                )


def _kb_meta(counts: dict[str, int], standards: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        **counts,
        "harmonized_standards": sum(1 for row in standards if row.get("harmonization_status") == "harmonized"),
        "state_of_the_art_standards": sum(1 for row in standards if row.get("harmonization_status") == "state_of_the_art"),
        "review_items": sum(1 for row in standards if row.get("item_type") == "review"),
        "product_gated_standards": sum(1 for row in standards if row.get("applies_if_products") or row.get("applies_if_genres")),
        "version": KB_META_VERSION,
    }


# ---------- public loaders ----------

def _load_traits_catalog() -> list[dict[str, Any]]:
    base = _load_yaml_raw("traits.yaml")
    ext = _load_yaml_raw("trait_extensions.yaml", required=False)
    merged = {"traits": _merge_records(_require_list(base, "traits", "traits.yaml"), _optional_list(ext, "traits"), "id")}
    return _validate_traits(merged)


def _load_genres_catalog(trait_ids: set[str]) -> list[dict[str, Any]]:
    raw = _load_yaml_raw("product_genres.yaml", required=False)
    return _validate_genres(raw, trait_ids)


def _load_products_catalog(trait_ids: set[str], genre_ids: set[str]) -> list[dict[str, Any]]:
    base = _load_yaml_raw("products.yaml")
    ext = _load_yaml_raw("product_extensions.yaml", required=False)
    merged = {"products": _merge_records(_require_list(base, "products", "products.yaml"), _optional_list(ext, "products"), "id")}
    return _validate_products(merged, trait_ids, genre_ids)


def _load_legislations_catalog(product_ids: set[str], trait_ids: set[str], genre_ids: set[str]) -> list[dict[str, Any]]:
    base = _load_yaml_raw("legislation_catalog.yaml")
    ext = _load_yaml_raw("legislation_extensions.yaml", required=False)
    merged = {"legislations": _merge_records(_require_list(base, "legislations", "legislation_catalog.yaml"), _optional_list(ext, "legislations"), "code")}
    return _validate_legislations(merged, product_ids, trait_ids, genre_ids)


def _load_standards_catalog(product_ids: set[str], trait_ids: set[str], legislation_keys: set[str], genre_ids: set[str]) -> list[dict[str, Any]]:
    base = _load_yaml_raw("standards.yaml")
    ext = _load_yaml_raw("standard_extensions.yaml", required=False)
    merged = {"standards": _merge_records(_require_list(base, "standards", "standards.yaml"), _optional_list(ext, "standards"), "code")}
    return _validate_standards(merged, product_ids, trait_ids, legislation_keys, genre_ids)


@lru_cache(maxsize=1)
def load_all() -> dict[str, Any]:
    traits = _load_traits_catalog()
    trait_ids = {row["id"] for row in traits}

    genres = _load_genres_catalog(trait_ids)
    genre_ids = {row["id"] for row in genres}

    products = _enrich_products(_load_products_catalog(trait_ids, genre_ids), genres)
    product_ids = {row["id"] for row in products}

    legislations = _enrich_legislations(_load_legislations_catalog(product_ids, trait_ids, genre_ids), products)
    legislation_keys = {row["directive_key"] for row in legislations} | {
        "CRA",
        "GDPR",
        "AI_Act",
        "ESPR",
        "OTHER",
        "GPSR",
        "WEEE",
        "TOY",
        "UAS",
        "MDR",
    }

    standards = _enrich_standards(_load_standards_catalog(product_ids, trait_ids, legislation_keys, genre_ids), products)
    _post_validate_product_standard_links(products, genres, standards)

    counts = {
        "traits": len(traits),
        "genres": len(genres),
        "products": len(products),
        "legislations": len(legislations),
        "standards": len(standards),
    }

    return {
        "traits": traits,
        "genres": genres,
        "products": products,
        "legislations": legislations,
        "standards": standards,
        "counts": counts,
        "meta": _kb_meta(counts, standards),
    }


def load_traits() -> list[dict[str, Any]]:
    return load_all()["traits"]


def load_genres() -> list[dict[str, Any]]:
    return load_all()["genres"]


def load_products() -> list[dict[str, Any]]:
    return load_all()["products"]


def load_legislations() -> list[dict[str, Any]]:
    return load_all()["legislations"]


def load_standards() -> list[dict[str, Any]]:
    return load_all()["standards"]


def load_meta() -> dict[str, Any]:
    return load_all()["meta"]


def warmup_knowledge_base() -> dict[str, Any]:
    return load_all()["meta"]


def reset_cache() -> None:
    load_all.cache_clear()
    from classifier import reset_classifier_cache

    reset_classifier_cache()
