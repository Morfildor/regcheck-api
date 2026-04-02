from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from app.core.settings import get_settings


class KnowledgeBaseError(RuntimeError):
    pass

REQUIRED_DATA_FILES = (
    "traits.yaml",
    "classifier_signals.yaml",
    "products.yaml",
    "legislation_catalog.yaml",
    "standards.yaml",
    "product_genres.yaml",
)
ALL_DATA_FILES = REQUIRED_DATA_FILES

def _data_dir_candidates() -> list[Path]:
    candidates: list[Path] = []
    settings = get_settings()
    if settings.data_dir is not None:
        candidates.append(settings.data_dir)
    candidates.append((settings.project_root / "data").resolve())

    unique: list[Path] = []
    seen: set[str] = set()
    for candidate in candidates:
        key = str(candidate)
        if key in seen:
            continue
        seen.add(key)
        unique.append(candidate)
    return unique


@lru_cache(maxsize=1)
def _resolved_data_paths() -> dict[str, Path | None]:
    resolved: dict[str, Path | None] = {}
    candidates = _data_dir_candidates()
    for filename in ALL_DATA_FILES:
        path: Path | None = None
        for directory in candidates:
            candidate = directory / filename
            if candidate.exists() and candidate.is_file():
                path = candidate
                break
        resolved[filename] = path
    return resolved


def _resolved_data_paths_for_logging() -> dict[str, str]:
    return {name: (str(path) if path is not None else "<missing optional>") for name, path in _resolved_data_paths().items()}


def _resolve_data_path(filename: str, *, required: bool = True) -> Path | None:
    path = _resolved_data_paths().get(filename)
    if path is not None:
        return path

    if not required:
        return None

    tried = "\n".join(str(directory / filename) for directory in _data_dir_candidates())
    raise KnowledgeBaseError(f"Missing knowledge-base file: {filename}. Tried:\n{tried}")


def clear_resolved_data_paths_cache() -> None:
    _resolved_data_paths.cache_clear()


__all__ = [
    "ALL_DATA_FILES",
    "KnowledgeBaseError",
    "REQUIRED_DATA_FILES",
    "_data_dir_candidates",
    "_resolve_data_path",
    "_resolved_data_paths",
    "_resolved_data_paths_for_logging",
    "clear_resolved_data_paths_cache",
]
