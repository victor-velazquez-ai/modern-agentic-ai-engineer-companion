"""The platform's exception hierarchy (Ch 4, hardened in Ch 26/28).

Every failure the platform raises on purpose descends from :class:`AgenticError`,
so the API and worker layers can map exceptions to outcomes (an HTTP status, a
retry decision, an audit entry) by *type* rather than by parsing messages. Each
error carries:

* a stable ``code`` (machine-readable; safe to log, alert, and branch on),
* a human ``message``,
* an HTTP ``status`` hint (the API layer's default mapping — domain code never
  imports a web framework, it just declares intent),
* an optional ``details`` mapping for structured context.

The split between *retryable* and *terminal* failures mirrors the model layer's
:class:`ProviderError` so a caller can decide between backing off and failing
fast without knowing which subsystem raised.
"""

from __future__ import annotations

from typing import Any, Mapping


class AgenticError(Exception):
    """Base class for every error the platform raises deliberately.

    ``code`` is the stable identifier (e.g. ``"not_found"``); ``status`` is the
    HTTP status the API layer maps this to by default. Subclasses set sensible
    defaults; call sites can override per-instance.
    """

    code: str = "error"
    status: int = 500

    def __init__(
        self,
        message: str,
        *,
        code: str | None = None,
        status: int | None = None,
        details: Mapping[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        if code is not None:
            self.code = code
        if status is not None:
            self.status = status
        self.details: dict[str, Any] = dict(details or {})

    def to_dict(self) -> dict[str, Any]:
        """Serialisable error body — what an API layer returns to a client.

        Never includes a stack trace or internal detail beyond ``details``; it is
        safe to send to a caller and to log.
        """

        body: dict[str, Any] = {"error": self.code, "message": self.message}
        if self.details:
            body["details"] = self.details
        return body

    def __str__(self) -> str:  # pragma: no cover - cosmetic
        return f"[{self.code}] {self.message}"


class ConfigError(AgenticError):
    """A required setting is missing or invalid. Fails fast at startup."""

    code = "config_error"
    status = 500


class ValidationError(AgenticError):
    """Input failed validation (bad request shape, schema mismatch)."""

    code = "validation_error"
    status = 422


class NotFoundError(AgenticError):
    """A requested resource does not exist."""

    code = "not_found"
    status = 404


class PermissionDeniedError(AgenticError):
    """The caller is authenticated but not allowed to do this (Ch 26/41)."""

    code = "permission_denied"
    status = 403


class GuardrailError(AgenticError):
    """A guardrail blocked the request or response (Ch 41).

    Fails *closed*: an input that trips an injection/unsafe rule never reaches the
    model. The blocked categories travel in ``details["categories"]``.
    """

    code = "guardrail_blocked"
    status = 400


class ProviderError(AgenticError):
    """A model/provider call failed.

    ``retryable`` lets the client decide between backoff-retry (429/5xx/timeout)
    and failing fast (400/auth). This is the single error the model layer raises
    so routing and retry policy never depend on a vendor SDK's exception types.
    """

    code = "provider_error"
    status = 502

    def __init__(
        self,
        message: str,
        *,
        retryable: bool = False,
        code: str | None = None,
        status: int | None = None,
        details: Mapping[str, Any] | None = None,
    ) -> None:
        super().__init__(message, code=code, status=status, details=details)
        self.retryable = retryable


class RateLimitedError(ProviderError):
    """A provider (or our own limiter) said "slow down". Always retryable."""

    code = "rate_limited"
    status = 429

    def __init__(
        self,
        message: str = "rate limited",
        *,
        retry_after_s: float | None = None,
        details: Mapping[str, Any] | None = None,
    ) -> None:
        merged: dict[str, Any] = dict(details or {})
        if retry_after_s is not None:
            merged["retry_after_s"] = retry_after_s
        super().__init__(message, retryable=True, details=merged)
        self.retry_after_s = retry_after_s


__all__ = [
    "AgenticError",
    "ConfigError",
    "ValidationError",
    "NotFoundError",
    "PermissionDeniedError",
    "GuardrailError",
    "ProviderError",
    "RateLimitedError",
]
