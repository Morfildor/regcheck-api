from __future__ import annotations

from typing import TYPE_CHECKING, Any


if TYPE_CHECKING:
    from .routing import AnalysisTrace
    from .service import analyze, ENGINE_VERSION
    from .legacy import analyze_v1


__all__ = ["AnalysisTrace", "ENGINE_VERSION", "analyze", "analyze_v1"]


def __getattr__(name: str) -> Any:
    if name == "AnalysisTrace":
        from .routing import AnalysisTrace

        return AnalysisTrace
    if name in {"ENGINE_VERSION", "analyze"}:
        from .service import ENGINE_VERSION, analyze

        return {"ENGINE_VERSION": ENGINE_VERSION, "analyze": analyze}[name]
    if name == "analyze_v1":
        from .legacy import analyze_v1

        return analyze_v1
    raise AttributeError(name)
