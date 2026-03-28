from __future__ import annotations

from app.core.settings import get_settings, reset_settings_cache


def init_env() -> None:
    reset_settings_cache()
    get_settings()
