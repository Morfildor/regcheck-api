from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import yaml

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"


def _resolve_data_path(filename: str) -> Path:
    preferred = DATA_DIR / filename
    if preferred.exists():
        return preferred
    fallback = BASE_DIR / filename
    if fallback.exists():
        return fallback
    return preferred


class KnowledgeBaseError(RuntimeError):
    pass


def _load_yaml_raw(filename: str) -> dict:
    path = _resolve_data_path(filename)
    if not path.exists():
        raise KnowledgeBaseError(f"Missing required data file: {path}")
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
    except yaml.YAMLError as exc:
        raise KnowledgeBaseError(f"Invalid YAML in {filename}: {exc}") from exc

    if not isinstance(data, dict):
        raise KnowledgeBaseError(f"{filename} must contain a top-level mapping.")
    return data


def _require_list(parent: dict, key: str, filename: str) -> list:
    value = parent.get(key)
    if not isinstance(value, list):
        raise KnowledgeBaseError(f"{filename} must contain a top-level '{key}' list.")
    return value


def _normalize_text(value: str) -> str:
    return " ".join(value.strip().lower().split())


def _validate_traits(data: dict) -> list[dict]:
    traits = _require_list(data, "traits", "traits.yaml")
    seen: set[str] = set()

    for idx, row in enumerate(traits, start=1):
        if not isinstance(row, dict):
            raise KnowledgeBaseError(f"traits.yaml trait #{idx} must be a mapping.")
        for field in ("id", "label", "description"):
            if not isinstance(row.get(field), str) or not row[field].strip():
                raise KnowledgeBaseError(f"traits.yaml trait #{idx} is missing a valid '{field}'.")
        if row["id"] in seen:
            raise KnowledgeBaseError(f"Duplicate trait id in traits.yaml: {row['id']}")
        seen.add(row["id"])

    return traits


def _validate_products(data: dict, trait_ids: set[str]) -> list[dict]:
    products = _require_list(data, "products", "products.yaml")
    seen: set[str] = set()
    alias_to_id: dict[str, str] = {}

    for idx, row in enumerate(products, start=1):
        if not isinstance(row, dict):
            raise KnowledgeBaseError(f"products.yaml product #{idx} must be a mapping.")

        for field in ("id", "label"):
            if not isinstance(row.get(field), str) or not row[field].strip():
                raise KnowledgeBaseError(f"products.yaml product #{idx} is missing a valid '{field}'.")

        for field in ("aliases", "implied_traits", "functional_classes"):
            if not isinstance(row.get(field), list):
                raise KnowledgeBaseError(
                    f"products.yaml product '{row.get('id', idx)}' must contain list field '{field}'."
                )

        pid = row["id"]
        if pid in seen:
            raise KnowledgeBaseError(f"Duplicate product id in products.yaml: {pid}")
        seen.add(pid)

        for trait in row.get("implied_traits", []):
            if trait not in trait_ids:
                raise KnowledgeBaseError(f"Unknown trait '{trait}' referenced by product '{pid}'.")

        for alias in row.get("aliases", []):
            if not isinstance(alias, str) or not alias.strip():
                raise KnowledgeBaseError(f"Product '{pid}' contains an empty or invalid alias.")
            alias_norm = _normalize_text(alias)
            previous = alias_to_id.get(alias_norm)
            if previous and previous != pid:
                raise KnowledgeBaseError(
                    f"Duplicate alias '{alias}' used by both '{previous}' and '{pid}' in products.yaml."
                )
            alias_to_id[alias_norm] = pid

        likely_standards = row.get("likely_standards", [])
        if not isinstance(likely_standards, list):
            raise KnowledgeBaseError(f"Product '{pid}' has non-list likely_standards.")
        for code in likely_standards:
            if not isinstance(code, str) or not code.strip():
                raise KnowledgeBaseError(f"Product '{pid}' contains invalid likely_standards entries.")

        for fc in row.get("functional_classes", []):
            if not isinstance(fc, str) or not fc.strip():
                raise KnowledgeBaseError(f"Product '{pid}' contains invalid functional_classes entries.")

    return products


def _collect_functional_classes(products: list[dict]) -> set[str]:
    classes: set[str] = set()
    for row in products:
        for fc in row.get("functional_classes", []):
            classes.add(fc)
    return classes


def _validate_legislations(
    data: dict,
    product_ids: set[str],
    trait_ids: set[str],
    functional_classes: set[str],
) -> list[dict]:
    legislations = _require_list(data, "legislations", "legislation_catalog.yaml")
    seen: set[str] = set()

    allowed_legal_forms = {
        "Directive",
        "Regulation",
        "Delegated Regulation",
        "Implementing Decision",
        "Framework",
        "Other",
    }
    allowed_priorities = {"core", "product_specific", "conditional", "informational"}
    allowed_applicability = {"applicable", "conditional", "not_applicable"}

    for idx, row in enumerate(legislations, start=1):
        if not isinstance(row, dict):
            raise KnowledgeBaseError(f"legislation_catalog.yaml legislation #{idx} must be a mapping.")

        for field in ("code", "title", "family", "reason", "directive_key"):
            if not isinstance(row.get(field), str) or not row[field].strip():
                raise KnowledgeBaseError(f"legislation_catalog.yaml entry #{idx} is missing a valid '{field}'.")

        code = row["code"]
        if code in seen:
            raise KnowledgeBaseError(f"Duplicate legislation code in legislation_catalog.yaml: {code}")
        seen.add(code)

        if row.get("legal_form", "Other") not in allowed_legal_forms:
            raise KnowledgeBaseError(f"Legislation '{code}' has invalid legal_form '{row.get('legal_form')}'.")
        if row.get("priority", "conditional") not in allowed_priorities:
            raise KnowledgeBaseError(f"Legislation '{code}' has invalid priority '{row.get('priority')}'.")
        if row.get("applicability", "conditional") not in allowed_applicability:
            raise KnowledgeBaseError(f"Legislation '{code}' has invalid applicability '{row.get('applicability')}'.")

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

        for fc_field in (
            "all_of_functional_classes",
            "any_of_functional_classes",
            "none_of_functional_classes",
        ):
            for fc in row.get(fc_field, []):
                if fc not in functional_classes:
                    raise KnowledgeBaseError(
                        f"Legislation '{code}' references unknown functional class '{fc}'."
                    )

        for product_field in ("any_of_product_types", "exclude_product_types"):
            for pid in row.get(product_field, []):
                if pid not in product_ids:
                    raise KnowledgeBaseError(f"Legislation '{code}' references unknown product id '{pid}'.")

    return legislations


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
            if not isinstance(row.get(field), str) or not row[field].strip():
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
                raise KnowledgeBaseError(f"Standard '{code}' contains invalid directive values.")

        legislation_key = row.get("legislation_key")
        if legislation_key is not None:
            if not isinstance(legislation_key, str) or not legislation_key.strip():
                raise KnowledgeBaseError(f"Standard '{code}' has invalid legislation_key.")
            if legislation_key not in legislation_keys:
                raise KnowledgeBaseError(
                    f"Standard '{code}' references unknown legislation_key '{legislation_key}'."
                )

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

    return standards


def _validate_cross_references(products: list[dict], standards: list[dict]) -> None:
    standard_codes = {row["code"] for row in standards}
    for row in products:
        pid = row["id"]
        for code in row.get("likely_standards", []):
            if code not in standard_codes:
                raise KnowledgeBaseError(
                    f"Product '{pid}' references unknown likely standard '{code}'."
                )


@lru_cache(maxsize=1)
def load_all() -> dict:
    traits_data = _load_yaml_raw("traits.yaml")
    traits = _validate_traits(traits_data)
    trait_ids = {row["id"] for row in traits}

    products_data = _load_yaml_raw("products.yaml")
    products = _validate_products(products_data, trait_ids)
    product_ids = {row["id"] for row in products}
    functional_classes = _collect_functional_classes(products)

    legislations_data = _load_yaml_raw("legislation_catalog.yaml")
    legislations = _validate_legislations(
        legislations_data,
        product_ids,
        trait_ids,
        functional_classes,
    )
    legislation_keys = {row["directive_key"] for row in legislations} | {"CRA", "GDPR", "AI_Act", "ESPR", "OTHER"}

    standards_data = _load_yaml_raw("standards.yaml")
    standards = _validate_standards(standards_data, product_ids, trait_ids, legislation_keys)

    _validate_cross_references(products, standards)

    return {
        "traits": traits,
        "products": products,
        "legislations": legislations,
        "standards": standards,
        "counts": {
            "traits": len(traits),
            "products": len(products),
            "legislations": len(legislations),
            "standards": len(standards),
        },
    }


def load_traits() -> list[dict]:
    return load_all()["traits"]


def load_products() -> list[dict]:
    return load_all()["products"]


def load_legislations() -> list[dict]:
    return load_all()["legislations"]


def load_standards() -> list[dict]:
    return load_all()["standards"]


def warmup_knowledge_base() -> dict:
    return load_all()["counts"]


def reset_cache() -> None:
    load_all.cache_clear()