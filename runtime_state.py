from __future__ import annotations

from app.core import runtime_state as _runtime_state

API_VERSION = _runtime_state.API_VERSION
APP_VERSION = _runtime_state.APP_VERSION
AppRuntimeState = _runtime_state.AppRuntimeState
KnowledgeBaseWarmupSnapshot = _runtime_state.KnowledgeBaseWarmupSnapshot
RuntimeSnapshot = _runtime_state.RuntimeSnapshot
StartupState = _runtime_state.StartupState
utc_now_iso = _runtime_state.utc_now_iso

__all__ = [
    "API_VERSION",
    "APP_VERSION",
    "AppRuntimeState",
    "KnowledgeBaseWarmupSnapshot",
    "RuntimeSnapshot",
    "StartupState",
    "utc_now_iso",
]
