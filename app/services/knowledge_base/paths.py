from __future__ import annotations

from dataclasses import dataclass
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


@dataclass(frozen=True, slots=True)
class CatalogSourceBundle:
    filename: str
    data_dir: Path | None = None
    file_path: Path | None = None
    fragment_dir: Path | None = None
    fragment_paths: tuple[Path, ...] = ()

    @property
    def paths(self) -> tuple[Path, ...]:
        ordered: list[Path] = []
        if self.file_path is not None:
            ordered.append(self.file_path)
        ordered.extend(self.fragment_paths)
        return tuple(ordered)

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


def _catalog_fragment_dir(filename: str, data_dir: Path) -> Path:
    return data_dir / Path(filename).stem


def _fragment_paths(fragment_dir: Path) -> tuple[Path, ...]:
    if not fragment_dir.exists() or not fragment_dir.is_dir():
        return ()
    return tuple(
        sorted(
            (path.resolve() for path in fragment_dir.rglob("*.yaml") if path.is_file()),
            key=lambda path: path.relative_to(fragment_dir).as_posix(),
        )
    )


def _bundle_for_candidate(filename: str, data_dir: Path) -> CatalogSourceBundle | None:
    raw_file_path = (data_dir / filename).resolve()
    file_path: Path | None = raw_file_path if raw_file_path.exists() and raw_file_path.is_file() else None
    fragment_dir = _catalog_fragment_dir(filename, data_dir).resolve()
    fragment_paths = _fragment_paths(fragment_dir)
    if file_path is None and not fragment_paths:
        return None
    return CatalogSourceBundle(
        filename=filename,
        data_dir=data_dir.resolve(),
        file_path=file_path,
        fragment_dir=fragment_dir if fragment_paths else None,
        fragment_paths=fragment_paths,
    )


@lru_cache(maxsize=1)
def _resolved_catalog_sources() -> dict[str, CatalogSourceBundle | None]:
    resolved: dict[str, CatalogSourceBundle | None] = {}
    candidates = _data_dir_candidates()
    for filename in ALL_DATA_FILES:
        bundle: CatalogSourceBundle | None = None
        for directory in candidates:
            bundle = _bundle_for_candidate(filename, directory)
            if bundle is not None:
                break
        resolved[filename] = bundle
    return resolved


@lru_cache(maxsize=1)
def _resolved_data_paths() -> dict[str, Path | None]:
    return {
        filename: (bundle.file_path if bundle is not None else None)
        for filename, bundle in _resolved_catalog_sources().items()
    }


def _resolved_data_paths_for_logging() -> dict[str, str]:
    out: dict[str, str] = {}
    for name, bundle in _resolved_catalog_sources().items():
        if bundle is None or not bundle.paths:
            out[name] = "<missing optional>"
            continue
        out[name] = "; ".join(str(path) for path in bundle.paths)
    return out


def _resolve_catalog_sources(filename: str, *, required: bool = True) -> CatalogSourceBundle | None:
    bundle = _resolved_catalog_sources().get(filename)
    if bundle is not None and bundle.paths:
        return bundle

    if not required:
        return None

    tried: list[str] = []
    for directory in _data_dir_candidates():
        tried.append(str(directory / filename))
        tried.append(str(_catalog_fragment_dir(filename, directory)))
    raise KnowledgeBaseError(f"Missing knowledge-base source: {filename}. Tried:\n" + "\n".join(tried))


def _resolve_data_path(filename: str, *, required: bool = True) -> Path | None:
    bundle = _resolve_catalog_sources(filename, required=required)
    if bundle is None:
        return None
    return bundle.file_path or (bundle.paths[0] if bundle.paths else None)


def clear_resolved_data_paths_cache() -> None:
    _resolved_catalog_sources.cache_clear()
    _resolved_data_paths.cache_clear()


__all__ = [
    "ALL_DATA_FILES",
    "CatalogSourceBundle",
    "KnowledgeBaseError",
    "REQUIRED_DATA_FILES",
    "_data_dir_candidates",
    "_resolve_catalog_sources",
    "_resolve_data_path",
    "_resolved_catalog_sources",
    "_resolved_data_paths",
    "_resolved_data_paths_for_logging",
    "clear_resolved_data_paths_cache",
]
