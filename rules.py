from __future__ import annotations

from app.services import classifier as _classifier
from app.services import standards_engine as _standards
from app.services.rules import legacy as _legacy
from app.services.rules import routing as _routing
from app.services.rules import service as _service
from app.services.rules import summary as _summary
from app.services.rules import facts as _facts

AnalysisTrace = _service.AnalysisTrace
ENGINE_VERSION = _service.ENGINE_VERSION
ENABLE_ENGINE_V2_SHADOW: bool | None = None

extract_traits = _classifier.extract_traits
find_applicable_items = _standards.find_applicable_items
_build_summary = _summary._build_summary
_build_legislation_sections = _routing._build_legislation_sections
_apply_post_selection_gates = _routing._apply_post_selection_gates
_missing_information = _facts._missing_information
_current_date = _routing._current_date

_base_shadow_enabled = _service._shadow_enabled


def _sync_compat_overrides() -> None:
    _routing.extract_traits = extract_traits
    _routing._build_legislation_sections = _build_legislation_sections
    _routing._current_date = _current_date
    _legacy._build_legislation_sections = _build_legislation_sections
    _legacy._missing_information = _missing_information
    _service.find_applicable_items = find_applicable_items
    _service._build_summary = _build_summary
    _service._missing_information = _missing_information
    if ENABLE_ENGINE_V2_SHADOW is None:
        _service._shadow_enabled = _base_shadow_enabled
    else:
        _service._shadow_enabled = lambda: bool(ENABLE_ENGINE_V2_SHADOW)


def analyze(*args, **kwargs):
    _sync_compat_overrides()
    return _service.analyze(*args, **kwargs)


def analyze_v1(*args, **kwargs):
    _sync_compat_overrides()
    return _legacy.analyze_v1(*args, **kwargs)


def _pick_legislations(*args, **kwargs):
    _sync_compat_overrides()
    return _routing._pick_legislations(*args, **kwargs)


__all__ = [
    "AnalysisTrace",
    "ENABLE_ENGINE_V2_SHADOW",
    "ENGINE_VERSION",
    "_apply_post_selection_gates",
    "_build_legislation_sections",
    "_build_summary",
    "_current_date",
    "_missing_information",
    "_pick_legislations",
    "analyze",
    "analyze_v1",
    "extract_traits",
    "find_applicable_items",
]
