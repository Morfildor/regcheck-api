from __future__ import annotations

from dataclasses import dataclass, field
from functools import lru_cache
import os
from pathlib import Path

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover
    load_dotenv = None


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_ALLOWED_ORIGINS = (
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "https://rulegrid.net",
    "https://www.rulegrid.net",
)
DEFAULT_ALLOWED_ORIGIN_REGEX = r"https://regcheck-frontend(?:-[a-z0-9-]+)?\.vercel\.app"
ADMIN_RELOAD_TOKEN_ENV = "REGCHECK_ADMIN_RELOAD_TOKEN"


def _as_bool(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _csv_env_list(name: str) -> list[str]:
    return [item.strip() for item in os.getenv(name, "").split(",") if item.strip()]


def _combine_origin_regex(parts: list[str]) -> str | None:
    cleaned = [part.strip() for part in parts if part and part.strip()]
    if not cleaned:
        return None
    if len(cleaned) == 1:
        return cleaned[0]
    return "|".join(f"(?:{part})" for part in cleaned)


def _load_environment() -> None:
    if load_dotenv is None:
        return
    load_dotenv(PROJECT_ROOT / ".env", override=False)


@dataclass(frozen=True, slots=True)
class CorsSettings:
    allow_origins: list[str]
    allow_origin_regex: str | None


@dataclass(frozen=True, slots=True)
class Settings:
    project_root: Path
    data_dir: Path | None
    admin_reload_token_env: str
    admin_reload_token: str
    expose_health_details: bool
    enable_engine_v2_shadow: bool
    cors: CorsSettings
    log_level: str = "INFO"
    build_metadata_env: str = "REGCHECK_BUILD_METADATA"
    catalog_version_env: str = "REGCHECK_CATALOG_VERSION"
    extra: dict[str, str] = field(default_factory=dict)


def _build_settings() -> Settings:
    _load_environment()
    configured_data_dir = os.getenv("REGCHECK_DATA_DIR", "").strip()
    data_dir = Path(configured_data_dir).expanduser().resolve() if configured_data_dir else None
    allow_origins = sorted(set(DEFAULT_ALLOWED_ORIGINS + tuple(_csv_env_list("CORS_ALLOWED_ORIGINS"))))
    allow_origin_regex = _combine_origin_regex(
        [DEFAULT_ALLOWED_ORIGIN_REGEX, os.getenv("CORS_ALLOWED_ORIGIN_REGEX", "").strip()]
    )
    expose_health_details = _as_bool("REGCHECK_EXPOSE_HEALTH_DETAILS", default=False)
    return Settings(
        project_root=PROJECT_ROOT,
        data_dir=data_dir,
        admin_reload_token_env=ADMIN_RELOAD_TOKEN_ENV,
        admin_reload_token=os.getenv(ADMIN_RELOAD_TOKEN_ENV, "").strip(),
        expose_health_details=expose_health_details,
        enable_engine_v2_shadow=_as_bool("REGCHECK_ENGINE_V2_SHADOW", default=False),
        cors=CorsSettings(allow_origins=allow_origins, allow_origin_regex=allow_origin_regex),
        log_level=os.getenv("REGCHECK_LOG_LEVEL", "INFO").strip().upper() or "INFO",
    )


def load_settings() -> Settings:
    return _build_settings()


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return load_settings()


def reset_settings_cache() -> None:
    get_settings.cache_clear()
