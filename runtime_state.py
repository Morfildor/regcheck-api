from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Literal

APP_VERSION = "6.1.0"
API_VERSION = "1.0"

StartupState = Literal["starting", "warming_up", "ready", "failed", "reloading"]


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


@dataclass(slots=True)
class KnowledgeBaseWarmupSnapshot:
    counts: dict[str, int] = field(default_factory=dict)
    meta: dict[str, Any] = field(default_factory=dict)
    duration_ms: int | None = None
    loaded_at: str | None = None

    @property
    def catalog_version(self) -> str | None:
        version = self.meta.get("version")
        return version if isinstance(version, str) and version else None


@dataclass(slots=True)
class AppRuntimeState:
    startup_state: StartupState = "starting"
    knowledge_base_loaded: bool = False
    warmup_error: str | None = None
    warmup_counts: dict[str, int] = field(default_factory=dict)
    warmup_meta: dict[str, Any] = field(default_factory=dict)
    warmup_duration_ms: int | None = None
    ready_timestamp: str | None = None
    started_timestamp: str = field(default_factory=utc_now_iso)
    last_reload_timestamp: str | None = None

    @property
    def catalog_version(self) -> str | None:
        version = self.warmup_meta.get("version")
        return version if isinstance(version, str) and version else None

    @property
    def is_ready(self) -> bool:
        return self.startup_state == "ready" and self.knowledge_base_loaded and bool(self.catalog_version)

    def mark_warming(self, state: StartupState = "warming_up") -> None:
        self.startup_state = state
        self.knowledge_base_loaded = False
        self.warmup_error = None

    def mark_ready(self, snapshot: KnowledgeBaseWarmupSnapshot, *, reloaded: bool = False) -> None:
        self.startup_state = "ready"
        self.knowledge_base_loaded = True
        self.warmup_error = None
        self.warmup_counts = dict(snapshot.counts)
        self.warmup_meta = dict(snapshot.meta)
        self.warmup_duration_ms = snapshot.duration_ms
        self.ready_timestamp = snapshot.loaded_at or utc_now_iso()
        if reloaded:
            self.last_reload_timestamp = self.ready_timestamp

    def mark_failed(self, error: str, *, state: StartupState = "failed", reloaded: bool = False) -> None:
        self.startup_state = state
        self.knowledge_base_loaded = False
        self.warmup_error = error
        self.warmup_counts = {}
        self.warmup_meta = {}
        self.warmup_duration_ms = None
        self.ready_timestamp = None
        if reloaded:
            self.last_reload_timestamp = utc_now_iso()

