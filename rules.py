from __future__ import annotations

# Root-level re-export shim kept for test and tooling compatibility.
# All analysis logic lives in app.services.rules.
# No monkeypatching or global mutation is performed here.

from app.services.rules import legacy as _legacy
from app.services.rules import routing as _routing
from app.services.rules import service as _service

AnalysisTrace = _service.AnalysisTrace
ENGINE_VERSION = _service.ENGINE_VERSION


def analyze(*args, **kwargs):
    return _service.analyze(*args, **kwargs)


def analyze_v1(*args, **kwargs):
    return _legacy.analyze_v1(*args, **kwargs)


def _pick_legislations(*args, **kwargs):
    return _routing._pick_legislations(*args, **kwargs)


__all__ = [
    "AnalysisTrace",
    "ENGINE_VERSION",
    "_pick_legislations",
    "analyze",
    "analyze_v1",
]
