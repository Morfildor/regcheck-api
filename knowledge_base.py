from __future__ import annotations

from functools import lru_cache
from pathlib import Path
import os
import re

import yaml


class KnowledgeBaseError(RuntimeError):
    pass


BASE_DIR = Path(__file__).resolve().parent
KB_META_VERSION = "5.1.0"
ALLOWED_HARMONIZATION_STATUSES = {"harmonized", "state_of_the_art", "review", "unknown"}
ALLOWED_TEST_FOCUS = {
    "safety",
    "mechanical",
    "electrical",
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


def _resolve_data_path(filename: str) -> Path:
    for directory in _candidate_dirs():
        candidate = directory / filename
        if candidate.exists() and candidate.is_file():
            return candidate

    tried = "\n".join(str(directory / filename) for directory in _candidate_dirs())
    raise KnowledgeBaseError(f"Missing knowledge-base file: {filename}. Tried:\n{tried}")


def _load_yaml_raw(filename: str) -> dict:
    path = _resolve_data_path(filename)

    try:
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
    except yaml.YAMLError as exc:
        raise KnowledgeBaseError(f"Invalid YAML in {path.name}: {exc}") from exc
    except OSError as exc:
        raise KnowledgeBaseError(f"Could not read knowledge-base file: {path}") from exc

    if not isinstance(data, dict):
        raise KnowledgeBaseError(f"{path.name} must contain a top-level mapping.")
    return data


def _require_list(parent: dict, key: str, filename: str) -> list:
    value = parent.get(key)
    if not isinstance(value, list):
        raise KnowledgeBaseError(f"{filename} must contain a top-level '{key}' list.")
    return value


def _validate_traits(data: dict) -> list[dict]:
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
            raise KnowledgeBaseError(f"Duplicate trait id in traits.yaml: {trait_id}")
        seen.add(trait_id)

    return traits


def _validate_products(data: dict, trait_ids: set[str]) -> list[dict]:
    products = _require_list(data, "products", "products.yaml")
    seen: set[str] = set()

    for idx, row in enumerate(products, start=1):
        if not isinstance(row, dict):
            raise KnowledgeBaseError(f"products.yaml product #{idx} must be a mapping.")

        for field in ("id", "label"):
            value = row.get(field)
            if not isinstance(value, str) or not value.strip():
                raise KnowledgeBaseError(f"products.yaml product #{idx} is missing a valid '{field}'.")

        pid = row["id"]
        if pid in seen:
            raise KnowledgeBaseError(f"Duplicate product id in products.yaml: {pid}")
        seen.add(pid)

        aliases = row.get("aliases", [])
        if not isinstance(aliases, list) or not aliases or not all(isinstance(item, str) and item.strip() for item in aliases):
            raise KnowledgeBaseError(f"Product '{pid}' must define a non-empty aliases list.")

        for field in ("product_family", "product_subfamily"):
            value = row.get(field)
            if value is not None and (not isinstance(value, str) or not value.strip()):
                raise KnowledgeBaseError(f"Product '{pid}' field '{field}' must be a non-empty string when provided.")

        for key in ("implied_traits", "functional_classes", "likely_standards"):
            value = row.get(key, [])
            if not isinstance(value, list):
                raise KnowledgeBaseError(f"Product '{pid}' field '{key}' must be a list.")
            if key == "implied_traits":
                for trait in value:
                    if trait not in trait_ids:
                        raise KnowledgeBaseError(f"Product '{pid}' references unknown trait '{trait}'.")
            else:
                for item in value:
                    if not isinstance(item, str):
                        raise KnowledgeBaseError(f"Product '{pid}' field '{key}' must contain only strings.")

        for key in ("required_clues", "preferred_clues", "exclude_clues", "confusable_with"):
            value = row.get(key, [])
            if not isinstance(value, list):
                raise KnowledgeBaseError(f"Product '{pid}' field '{key}' must be a list.")
            for item in value:
                if not isinstance(item, str) or not item.strip():
                    raise KnowledgeBaseError(f"Product '{pid}' field '{key}' must contain only non-empty strings.")

        for key in ("family_traits", "subtype_traits"):
            value = row.get(key, [])
            if not isinstance(value, list):
                raise KnowledgeBaseError(f"Product '{pid}' field '{key}' must be a list.")
            for trait in value:
                if trait not in trait_ids:
                    raise KnowledgeBaseError(f"Product '{pid}' field '{key}' references unknown trait '{trait}'.")

    for row in products:
        pid = row["id"]
        for other in row.get("confusable_with", []):
            if other not in seen:
                raise KnowledgeBaseError(f"Product '{pid}' field 'confusable_with' references unknown product '{other}'.")

    return products


def _validate_legislations(data: dict, product_ids: set[str], trait_ids: set[str]) -> list[dict]:
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
            raise KnowledgeBaseError(f"Duplicate legislation code in legislation_catalog.yaml: {code}")
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

    return legislations


def _validate_standard_metadata(code: str, row: dict) -> None:
    bool_fields = ("is_harmonized",)
    list_fields = ("test_focus", "evidence_hint", "keywords")
    str_fields = (
        "standard_family",
        "harmonized_under",
        "harmonized_reference",
        "version",
        "dated_version",
        "supersedes",
        "harmonization_status",
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


def _validate_standards(
    data: dict,
    product_ids: set[str],
    trait_ids: set[str],
    legislation_keys: set[str],
) -> list[dict]:
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
            raise KnowledgeBaseError(f"Duplicate standard code in standards.yaml: {code}")
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

        item_type = row.get("item_type")
        if item_type is not None and item_type not in {"standard", "review"}:
            raise KnowledgeBaseError(f"Standard '{code}' has invalid item_type '{item_type}'.")

        _validate_standard_metadata(code, row)

    return standards


def _normalize_standard_code(code: str) -> str:
    value = re.sub(r"\s+", " ", (code or "").strip())
    if value.startswith("EN EN "):
        value = value.replace("EN EN ", "EN ", 1)
    return value


def _derive_harmonization_status(row: dict) -> str:
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


def _enrich_standards(rows: list[dict]) -> list[dict]:
    out: list[dict] = []
    seen_normalized_codes: set[str] = set()
    for row in rows:
        enriched = dict(row)
        enriched["code"] = _normalize_standard_code(enriched.get("code", ""))
        if enriched["code"] in seen_normalized_codes:
            raise KnowledgeBaseError(f"Duplicate normalized standard code in standards.yaml: {enriched['code']}")
        seen_normalized_codes.add(enriched["code"])
        enriched["standard_family"] = enriched.get("standard_family") or enriched["code"].split(":", 1)[0].strip()
        enriched["harmonization_status"] = _derive_harmonization_status(enriched)
        enriched.setdefault("test_focus", [])
        enriched.setdefault("evidence_hint", [])
        enriched.setdefault("keywords", [])
        out.append(enriched)
    return out


def _enrich_products(rows: list[dict]) -> list[dict]:
    out: list[dict] = []
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
        out.append(enriched)
    return out


def _post_validate_product_standard_links(products: list[dict], standards: list[dict]) -> None:
    standard_codes = {row["code"] for row in standards}
    standard_families = {row.get("standard_family") for row in standards if isinstance(row.get("standard_family"), str)}

    for product in products:
        pid = product["id"]
        for reference in product.get("likely_standards", []):
            if reference not in standard_codes and reference not in standard_families:
                raise KnowledgeBaseError(
                    f"Product '{pid}' references likely_standard '{reference}' that does not match any standard code or family."
                )


def _kb_meta(counts: dict[str, int], standards: list[dict]) -> dict:
    return {
        **counts,
        "harmonized_standards": sum(1 for row in standards if row.get("harmonization_status") == "harmonized"),
        "state_of_the_art_standards": sum(1 for row in standards if row.get("harmonization_status") == "state_of_the_art"),
        "review_items": sum(1 for row in standards if row.get("item_type") == "review"),
        "product_gated_standards": sum(1 for row in standards if row.get("applies_if_products")),
        "version": KB_META_VERSION,
    }


@lru_cache(maxsize=1)
def load_all() -> dict:
    traits_data = _load_yaml_raw("traits.yaml")
    traits = _validate_traits(traits_data)
    trait_ids = {row["id"] for row in traits}

    products_data = _load_yaml_raw("products.yaml")
    products = _enrich_products(_validate_products(products_data, trait_ids))
    product_ids = {row["id"] for row in products}

    legislations_data = _load_yaml_raw("legislation_catalog.yaml")
    legislations = _validate_legislations(legislations_data, product_ids, trait_ids)
    legislation_keys = {row["directive_key"] for row in legislations} | {"CRA", "GDPR", "AI_Act", "ESPR", "OTHER"}

    standards_data = _load_yaml_raw("standards.yaml")
    standards = _enrich_standards(_validate_standards(standards_data, product_ids, trait_ids, legislation_keys))

    _post_validate_product_standard_links(products, standards)

    counts = {
        "traits": len(traits),
        "products": len(products),
        "legislations": len(legislations),
        "standards": len(standards),
    }

    return {
        "traits": traits,
        "products": products,
        "legislations": legislations,
        "standards": standards,
        "counts": counts,
        "meta": _kb_meta(counts, standards),
    }


def load_traits() -> list[dict]:
    return load_all()["traits"]


def load_products() -> list[dict]:
    return load_all()["products"]


def load_legislations() -> list[dict]:
    return load_all()["legislations"]


def load_standards() -> list[dict]:
    return load_all()["standards"]


def load_meta() -> dict:
    return load_all()["meta"]


def warmup_knowledge_base() -> dict:
    return load_all()["meta"]


def reset_cache() -> None:
    load_all.cache_clear()
    from classifier import reset_classifier_cache

    reset_classifier_cache()
