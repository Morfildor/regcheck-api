from pathlib import Path
import yaml

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"


def _load_yaml(filename: str):
    path = DATA_DIR / filename
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def load_traits():
    data = _load_yaml("traits.yaml")
    return data.get("traits", [])


def load_products():
    data = _load_yaml("products.yaml")
    return data.get("products", [])


def load_standards():
    data = _load_yaml("standards.yaml")
    return data.get("standards", [])

