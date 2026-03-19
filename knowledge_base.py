from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import yaml

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"


class KnowledgeBaseError(RuntimeError):
    pass


def _load_yaml_raw(filename: str) -> dict:
    path = DATA_DIR / filename
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
                raise KnowledgeBaseError(f"products.yaml product '{row.get('id', idx)}' must contain list field '{field}'.")

        pid = row["id"]
        if pid in seen:
            raise KnowledgeBaseError(f"Duplicate product id in products.yaml: {pid}")
        seen.add(pid)

        for trait in row.get("implied_traits", []):
            if trait not in trait_ids:
                raise KnowledgeBaseError(f"Unknown trait '{trait}' referenced by product '{pid}'.")

        for alias in row.get("aliases", []):
            alias_norm = alias.strip().lower()
            previous = alias_to_id.get(alias_norm)
            if previous and previous != pid:
                raise KnowledgeBaseError(
                    f"Duplicate alias '{alias}' used by both '{previous}' and '{pid}' in products.yaml."
                )
            alias_to_id[alias_norm] = pid

        if "likely_standards" in row and not isinstance(row["likely_standards"], list):
            raise KnowledgeBaseError(f"Product '{pid}' has non-list likely_standards.")

    return products


def _validate_standards(data: dict, product_ids: set[str], trait_ids: set[str]) -> list[dict]:
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


@lru_cache(maxsize=1)
def load_all() -> dict:
    traits_data = _load_yaml_raw("traits.yaml")
    traits = _validate_traits(traits_data)
    trait_ids = {row["id"] for row in traits}

    products_data = _load_yaml_raw("products.yaml")
    products = _validate_products(products_data, trait_ids)
    product_ids = {row["id"] for row in products}

    standards_data = _load_yaml_raw("standards.yaml")
    standards = _validate_standards(standards_data, product_ids, trait_ids)

    return {
        "traits": traits,
        "products": products,
        "standards": standards,
        "counts": {
            "traits": len(traits),
            "products": len(products),
            "standards": len(standards),
        },
    }


def load_traits() -> list[dict]:
    return load_all()["traits"]


def load_products() -> list[dict]:
    return load_all()["products"]


def load_standards() -> list[dict]:
    return load_all()["standards"]


def warmup_knowledge_base() -> dict:
    return load_all()["counts"]


def reset_cache() -> None:
    load_all.cache_clear()
