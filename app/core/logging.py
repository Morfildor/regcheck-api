from __future__ import annotations

from contextvars import ContextVar
import logging

from app.core.settings import get_settings

_request_id_context: ContextVar[str | None] = ContextVar("request_id", default=None)
_configured = False


class RequestIdFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        if not hasattr(record, "request_id"):
            record.request_id = _request_id_context.get() or "-"
        return True


def configure_logging() -> None:
    global _configured
    if _configured:
        return
    settings = get_settings()
    root_logger = logging.getLogger()
    if not root_logger.handlers:
        logging.basicConfig(
            level=getattr(logging, settings.log_level, logging.INFO),
            format="%(asctime)s %(levelname)s %(name)s request_id=%(request_id)s %(message)s",
        )
    request_filter = RequestIdFilter()
    root_logger.addFilter(request_filter)
    _configured = True


def set_request_id(request_id: str | None) -> None:
    _request_id_context.set(request_id)


def clear_request_id() -> None:
    _request_id_context.set(None)
