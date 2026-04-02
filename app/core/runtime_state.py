from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timezone
from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as _pkg_version
from threading import Lock, RLock
from typing import Any, Iterator, Literal


def _resolve_app_version() -> str:
    # Single source of truth: pyproject.toml [project] version.
    try:
        return _pkg_version("rulegrid-backend")
    except PackageNotFoundError:
        return "0.0.0+dev"


APP_VERSION = _resolve_app_version()
API_VERSION = "1.0"

StartupState = Literal["starting", "warming_up", "ready", "failed", "reloading"]


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


@dataclass(frozen=True, slots=True)
class KnowledgeBaseWarmupSnapshot:
    counts: dict[str, int] = field(default_factory=dict)
    meta: dict[str, Any] = field(default_factory=dict)
    duration_ms: int | None = None
    loaded_at: str | None = None

    @property
    def catalog_version(self) -> str | None:
        version = self.meta.get("version")
        return version if isinstance(version, str) and version else None


@dataclass(frozen=True, slots=True)
class RuntimeSnapshot:
    startup_state: StartupState
    knowledge_base_loaded: bool
    warmup_error: str | None
    last_reload_error: str | None
    warmup_counts: dict[str, int]
    warmup_meta: dict[str, Any]
    warmup_duration_ms: int | None
    ready_timestamp: str | None
    started_timestamp: str
    last_reload_timestamp: str | None

    @property
    def catalog_version(self) -> str | None:
        version = self.warmup_meta.get("version")
        return version if isinstance(version, str) and version else None

    @property
    def is_ready(self) -> bool:
        return self.startup_state in {"ready", "reloading"} and self.knowledge_base_loaded and bool(self.catalog_version)


@dataclass(slots=True)
class AppRuntimeState:
    startup_state: StartupState = "starting"
    knowledge_base_loaded: bool = False
    warmup_error: str | None = None
    last_reload_error: str | None = None
    warmup_counts: dict[str, int] = field(default_factory=dict)
    warmup_meta: dict[str, Any] = field(default_factory=dict)
    warmup_duration_ms: int | None = None
    ready_timestamp: str | None = None
    started_timestamp: str = field(default_factory=utc_now_iso)
    last_reload_timestamp: str | None = None
    _state_lock: RLock = field(default_factory=RLock, init=False, repr=False)
    _reload_lock: Lock = field(default_factory=Lock, init=False, repr=False)

    @property
    def catalog_version(self) -> str | None:
        with self._state_lock:
            version = self.warmup_meta.get("version")
            return version if isinstance(version, str) and version else None

    @property
    def is_ready(self) -> bool:
        return self.snapshot().is_ready

    def snapshot(self) -> RuntimeSnapshot:
        with self._state_lock:
            return RuntimeSnapshot(
                startup_state=self.startup_state,
                knowledge_base_loaded=self.knowledge_base_loaded,
                warmup_error=self.warmup_error,
                last_reload_error=self.last_reload_error,
                warmup_counts=dict(self.warmup_counts),
                warmup_meta=dict(self.warmup_meta),
                warmup_duration_ms=self.warmup_duration_ms,
                ready_timestamp=self.ready_timestamp,
                started_timestamp=self.started_timestamp,
                last_reload_timestamp=self.last_reload_timestamp,
            )

    @contextmanager
    def reload_guard(self) -> Iterator[None]:
        self._reload_lock.acquire()
        try:
            yield
        finally:
            self._reload_lock.release()

    def mark_warming(self, state: StartupState = "warming_up", *, preserve_snapshot: bool = False) -> None:
        with self._state_lock:
            self.startup_state = state
            self.warmup_error = None
            if not preserve_snapshot:
                self.knowledge_base_loaded = False
                self.warmup_counts = {}
                self.warmup_meta = {}
                self.warmup_duration_ms = None
                self.ready_timestamp = None

    def mark_ready(self, snapshot: KnowledgeBaseWarmupSnapshot, *, reloaded: bool = False) -> None:
        with self._state_lock:
            timestamp = snapshot.loaded_at or utc_now_iso()
            self.startup_state = "ready"
            self.knowledge_base_loaded = True
            self.warmup_error = None
            self.last_reload_error = None
            self.warmup_counts = dict(snapshot.counts)
            self.warmup_meta = dict(snapshot.meta)
            self.warmup_duration_ms = snapshot.duration_ms
            self.ready_timestamp = timestamp
            if reloaded:
                self.last_reload_timestamp = timestamp

    def mark_failed(self, error: str, *, state: StartupState = "failed", reloaded: bool = False) -> None:
        with self._state_lock:
            self.startup_state = state
            self.knowledge_base_loaded = False
            self.warmup_error = error
            if reloaded:
                self.last_reload_error = error
                self.last_reload_timestamp = utc_now_iso()
            self.warmup_counts = {}
            self.warmup_meta = {}
            self.warmup_duration_ms = None
            self.ready_timestamp = None

    def mark_reload_failed(self, error: str) -> None:
        with self._state_lock:
            has_snapshot = bool(self.warmup_meta.get("version"))
            self.startup_state = "ready" if has_snapshot else "failed"
            self.knowledge_base_loaded = has_snapshot
            self.warmup_error = None if has_snapshot else error
            self.last_reload_error = error
            self.last_reload_timestamp = utc_now_iso()
