from __future__ import annotations

from dataclasses import dataclass, field
import logging
from typing import TypeVar

T = TypeVar("T")


@dataclass(slots=True)
class DegradationCollector:
    degraded_reasons: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def record(self, *, reason: str, warning: str) -> None:
        if reason not in self.degraded_reasons:
            self.degraded_reasons.append(reason)
        if warning not in self.warnings:
            self.warnings.append(warning)


def guarded_step(
    *,
    logger: logging.Logger,
    collector: DegradationCollector,
    step: str,
    reason: str,
    warning: str,
    fallback: T,
    operation,
    handled_exceptions: tuple[type[BaseException], ...] = (ValueError, TypeError, KeyError, AttributeError, RuntimeError),
) -> T:
    try:
        return operation()
    except handled_exceptions:
        logger.exception("analysis_degraded step=%s", step)
        collector.record(reason=reason, warning=warning)
        return fallback
