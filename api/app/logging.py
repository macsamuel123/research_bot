"""Logging setup and secret redaction (INV-6)."""

from __future__ import annotations

import logging
from collections.abc import Iterable

from app.config import Settings, secret_values

REDACTED = "***"
NOISY_LOGGERS: tuple[str, ...] = ("httpx", "httpcore", "telegram")
_FILTERED_LOGGERS: tuple[str, ...] = ("", "uvicorn", "uvicorn.error", "uvicorn.access")
_HANDLER_NAME = "research-bot-root"


class SecretRedactingFilter(logging.Filter):
    """Replace every occurrence of a secret value with `***` in message, args and tracebacks."""

    def __init__(self, secrets: Iterable[str]) -> None:
        super().__init__()
        self.secrets: list[str] = sorted({s for s in secrets if s}, key=len, reverse=True)

    def redact(self, text: str) -> str:
        for secret in self.secrets:
            if secret in text:
                text = text.replace(secret, REDACTED)
        return text

    def filter(self, record: logging.LogRecord) -> bool:
        if record.name == "uvicorn.access" and isinstance(record.args, tuple):
            # uvicorn's AccessFormatter unpacks record.args, so keep them (redacted).
            record.msg = self.redact(str(record.msg))
            record.args = tuple(self.redact(a) if isinstance(a, str) else a for a in record.args)
            return True
        try:
            message = record.getMessage()
        except Exception:  # noqa: BLE001 - a bad format string must not break logging
            message = str(record.msg)
        record.msg = self.redact(message)
        record.args = None
        if record.exc_info:
            if not record.exc_text:
                record.exc_text = logging.Formatter().formatException(record.exc_info)
            record.exc_text = self.redact(record.exc_text)
            # exc_text is used by formatters when present; drop the raw exception.
            record.exc_info = None
        elif record.exc_text:
            record.exc_text = self.redact(record.exc_text)
        if record.stack_info:
            record.stack_info = self.redact(record.stack_info)
        return True


def _install(logger: logging.Logger, flt: SecretRedactingFilter) -> None:
    for existing in list(logger.filters):
        if isinstance(existing, SecretRedactingFilter):
            logger.removeFilter(existing)
    logger.addFilter(flt)
    for handler in logger.handlers:
        for existing in list(handler.filters):
            if isinstance(existing, SecretRedactingFilter):
                handler.removeFilter(existing)
        handler.addFilter(flt)


def setup_logging(settings: Settings, level: int = logging.INFO) -> SecretRedactingFilter:
    """Configure logging idempotently; returns the installed redaction filter."""
    root = logging.getLogger()
    if not any(h.get_name() == _HANDLER_NAME for h in root.handlers):
        handler = logging.StreamHandler()
        handler.set_name(_HANDLER_NAME)
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
        root.addHandler(handler)
    root.setLevel(level)

    flt = SecretRedactingFilter(secret_values(settings))
    for name in _FILTERED_LOGGERS:
        _install(logging.getLogger(name), flt)
    for name in NOISY_LOGGERS:
        logger = logging.getLogger(name)
        if logger.level < logging.WARNING:  # NOTSET (0) would inherit root's INFO
            logger.setLevel(logging.WARNING)
    return flt
