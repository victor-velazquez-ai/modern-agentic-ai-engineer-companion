"""Platform core — config, errors, logging.

The cross-cutting foundations every other module imports but that depend on
nothing above them. Kept deliberately tiny and framework-free:

* :mod:`core.config` — the twelve-factor :class:`Settings` (Pydantic Settings),
  loaded once and shared. Secrets come from the environment only.
* :mod:`core.errors` — the platform's exception hierarchy, so failures are typed
  and an HTTP/worker layer can map them to a status without ``isinstance`` soup.
* :mod:`core.logging` — structured (JSON) logging + a ``request_id`` context so a
  single run is greppable end to end.

First built in book Ch 4 (§4 Build) and made twelve-factor by Ch 28.
"""

from __future__ import annotations

from .config import Settings, get_settings
from .errors import (
    AgenticError,
    ConfigError,
    GuardrailError,
    NotFoundError,
    PermissionDeniedError,
    ProviderError,
    RateLimitedError,
    ValidationError,
)
from .logging import bind_request_id, configure_logging, get_logger

__all__ = [
    "Settings",
    "get_settings",
    "AgenticError",
    "ConfigError",
    "GuardrailError",
    "NotFoundError",
    "PermissionDeniedError",
    "ProviderError",
    "RateLimitedError",
    "ValidationError",
    "configure_logging",
    "get_logger",
    "bind_request_id",
]
