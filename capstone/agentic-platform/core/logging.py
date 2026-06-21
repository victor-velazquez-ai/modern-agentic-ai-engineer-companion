"""Structured logging (Ch 4 · production-shaped by Ch 23/28).

Logs are an operational interface, not decoration. Two things the platform needs
from day one:

* **Structured (JSON) output** so logs are queryable in aggregation (one event =
  one object), with a plain-text formatter for local dev readability.
* **A request/run id bound to every line** of a single run, so you can ``grep`` a
  trace from API entry through agent loop to model call. The id lives in a
  :class:`contextvars.ContextVar`, which is async- and thread-safe (each task gets
  its own), and is injected by a logging filter — call sites never thread it
  through by hand.

This is intentionally dependency-free (stdlib ``logging``). In production the OTel
layer (Ch 23) attaches trace/span ids alongside ``request_id``; this module is the
seam they share.
"""

from __future__ import annotations

import contextvars
import json
import logging
import sys
import uuid
from typing import Any

# Bound per request/run; empty until a handler/worker binds one.
_request_id: contextvars.ContextVar[str] = contextvars.ContextVar(
    "request_id", default=""
)

_configured = False

# Keys the JSON formatter pulls from the record's standard attributes.
_STANDARD_ATTRS = {
    "name",
    "levelname",
    "levelno",
    "pathname",
    "filename",
    "module",
    "exc_info",
    "exc_text",
    "stack_info",
    "lineno",
    "funcName",
    "created",
    "msecs",
    "relativeCreated",
    "thread",
    "threadName",
    "processName",
    "process",
    "args",
    "msg",
    "message",
    "request_id",
    "taskName",
}


class RequestIdFilter(logging.Filter):
    """Inject the current ``request_id`` onto every record."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = _request_id.get()
        return True


class JsonFormatter(logging.Formatter):
    """One log record → one JSON object.

    Anything passed via ``logger.info("msg", extra={...})`` is merged in as
    top-level keys, so structured fields (``run_id``, ``model``, ``cost_usd``)
    sit next to the message instead of being interpolated into it.
    """

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "ts": self.formatTime(record, "%Y-%m-%dT%H:%M:%S%z"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "request_id": getattr(record, "request_id", ""),
        }
        # Merge structured `extra=` fields (anything not a standard attribute).
        for key, value in record.__dict__.items():
            if key not in _STANDARD_ATTRS and not key.startswith("_"):
                payload[key] = value
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str, ensure_ascii=False)


def configure_logging(
    *,
    level: str = "INFO",
    json_format: bool = True,
    stream: Any = None,
) -> None:
    """Configure the root logger once. Idempotent.

    Pass ``json_format=False`` for human-readable local dev. Reads nothing from
    the environment itself — callers pass values from :class:`core.config.Settings`
    so configuration stays in one place.
    """

    global _configured

    root = logging.getLogger()
    root.setLevel(level.upper())

    # Replace handlers so repeated calls (tests, reloads) don't double-log.
    for handler in list(root.handlers):
        root.removeHandler(handler)

    handler = logging.StreamHandler(stream or sys.stdout)
    if json_format:
        handler.setFormatter(JsonFormatter())
    else:
        handler.setFormatter(
            logging.Formatter(
                "%(asctime)s %(levelname)-7s [%(request_id)s] %(name)s: %(message)s"
            )
        )
    handler.addFilter(RequestIdFilter())
    root.addHandler(handler)
    _configured = True


def get_logger(name: str) -> logging.Logger:
    """Return a module logger, configuring logging on first use with defaults.

    Convenience so a module can ``log = get_logger(__name__)`` at import time and
    still emit sane output even if the app never called
    :func:`configure_logging` explicitly (e.g. a script or a test).
    """

    if not _configured:
        configure_logging()
    return logging.getLogger(name)


def bind_request_id(request_id: str | None = None) -> str:
    """Bind a ``request_id`` for the current context; returns the id used.

    Pass an incoming id (from an HTTP header / Celery task) to continue a trace,
    or omit it to mint a fresh one. The returned value is what subsequent log
    lines in this context will carry.
    """

    rid = request_id or uuid.uuid4().hex
    _request_id.set(rid)
    return rid


def current_request_id() -> str:
    """The ``request_id`` bound to the current context (empty if none)."""

    return _request_id.get()


__all__ = [
    "configure_logging",
    "get_logger",
    "bind_request_id",
    "current_request_id",
    "JsonFormatter",
    "RequestIdFilter",
]
