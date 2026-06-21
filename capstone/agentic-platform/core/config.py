"""Application configuration (Ch 4 · twelve-factor by Ch 28).

One :class:`Settings` object, loaded once from the environment (and an optional
``.env``), is the platform's single source of truth for configuration. The rules
the book insists on:

* **Config comes from the environment**, never hard-coded — twelve-factor.
* **Secrets are read from env only** (``ANTHROPIC_API_KEY`` etc.); they are never
  constructor arguments and are never logged. :meth:`Settings.redacted` exists so
  you can log the *shape* of the config without leaking a key.
* **Fail fast.** A required-but-missing or malformed value raises
  :class:`~core.errors.ConfigError` at startup, not on the first request.
* **Mock by default.** ``COMPANION_MOCK=1`` (the repo convention) means the whole
  platform runs offline with zero keys; the model layer reads this to pick the
  mock provider.

Implementation note: this uses **Pydantic Settings** when it is installed (the
production path). If neither ``pydantic-settings`` nor ``pydantic`` is present —
e.g. a bare ``py_compile`` check or a minimal CI image — it transparently falls
back to a small stdlib loader with the *same* public surface (``get_settings()``
returns an object with the same attributes), so importing this module never hard-
fails on a missing dependency. The production deployment always has Pydantic.
"""

from __future__ import annotations

import os
from functools import lru_cache
from typing import Any

from .errors import ConfigError

# --- environment helpers ----------------------------------------------------

_TRUTHY = {"1", "true", "yes", "on"}


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in _TRUTHY


def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None or raw == "":
        return default
    try:
        return int(raw)
    except ValueError as exc:
        raise ConfigError(f"{name} must be an integer, got {raw!r}") from exc


def _env_float(name: str, default: float) -> float:
    raw = os.getenv(name)
    if raw is None or raw == "":
        return default
    try:
        return float(raw)
    except ValueError as exc:
        raise ConfigError(f"{name} must be a number, got {raw!r}") from exc


# Field metadata shared by both the Pydantic and fallback implementations, so the
# two stay in lock-step. (name, env-default-getter, secret?)
_SECRET_FIELDS = frozenset(
    {"anthropic_api_key", "openai_api_key", "pinecone_api_key", "auth_secret"}
)


# ---------------------------------------------------------------------------
# Pydantic Settings path (production)
# ---------------------------------------------------------------------------

try:  # pragma: no cover - import guard exercised by environment, not tests
    from pydantic import Field, ValidationError as _PydanticValidationError
    from pydantic_settings import BaseSettings, SettingsConfigDict

    _HAVE_PYDANTIC = True
except Exception:  # pragma: no cover - fallback path below
    _HAVE_PYDANTIC = False


if _HAVE_PYDANTIC:

    class Settings(BaseSettings):  # type: ignore[no-redef]
        """Twelve-factor settings, validated by Pydantic.

        Loads from process env first, then a local ``.env`` (for dev). Every
        provider key is optional so the mock path needs nothing; the model layer
        enforces "key present" only when ``companion_mock`` is off.
        """

        model_config = SettingsConfigDict(
            env_file=".env",
            env_file_encoding="utf-8",
            case_sensitive=False,
            extra="ignore",
        )

        # --- runtime mode ---
        app_name: str = "agentic-platform"
        environment: str = Field(default="dev")  # dev | staging | prod
        companion_mock: bool = Field(default=True)
        log_level: str = Field(default="INFO")
        log_json: bool = Field(default=True)

        # --- model providers (secrets: env only) ---
        anthropic_api_key: str | None = None
        openai_api_key: str | None = None
        default_model: str = "claude-sonnet-4-6"

        # --- model layer tuning ---
        llm_max_retries: int = 3
        llm_request_timeout_s: float = 60.0
        cache_semantic: bool = True
        cache_threshold: float = 0.95
        daily_cost_cap_usd: float = 0.0  # 0 = no cap

        # --- data + cache services ---
        database_url: str = (
            "postgresql+psycopg://postgres:postgres@localhost:5432/agentic"
        )
        redis_url: str = "redis://localhost:6379/0"
        chroma_url: str | None = None
        pinecone_api_key: str | None = None

        # --- web / auth ---
        auth_secret: str | None = None

        # --- observability ---
        otel_exporter_otlp_endpoint: str | None = None

        @property
        def is_prod(self) -> bool:
            return self.environment.lower() in {"prod", "production"}

        def require_provider_key(self) -> None:
            """Fail fast if a live run is requested without a key."""

            if not self.companion_mock and not self.anthropic_api_key:
                raise ConfigError(
                    "COMPANION_MOCK=0 but ANTHROPIC_API_KEY is not set. "
                    "Set the key in the environment or stay in mock mode."
                )

        def redacted(self) -> dict[str, Any]:
            """Config as a dict with secrets masked — safe to log."""

            out: dict[str, Any] = {}
            for name, value in self.model_dump().items():
                if name in _SECRET_FIELDS and value:
                    out[name] = "***set***"
                else:
                    out[name] = value
            return out

    def _build_settings() -> "Settings":
        try:
            return Settings()
        except _PydanticValidationError as exc:  # malformed env → fail fast
            raise ConfigError(f"invalid configuration: {exc}") from exc


# ---------------------------------------------------------------------------
# Stdlib fallback path (no pydantic available)
# ---------------------------------------------------------------------------

else:  # pragma: no cover - import-environment dependent

    class Settings:  # type: ignore[no-redef]
        """Stdlib stand-in with the same public surface as the Pydantic version.

        Used only when ``pydantic`` / ``pydantic-settings`` are not installed.
        Reads the same environment variables so behaviour is identical for the
        attributes the platform actually consumes.
        """

        def __init__(self) -> None:
            self.app_name = os.getenv("APP_NAME", "agentic-platform")
            self.environment = os.getenv("ENVIRONMENT", "dev")
            self.companion_mock = _env_bool("COMPANION_MOCK", True)
            self.log_level = os.getenv("LOG_LEVEL", "INFO")
            self.log_json = _env_bool("LOG_JSON", True)

            self.anthropic_api_key = os.getenv("ANTHROPIC_API_KEY") or None
            self.openai_api_key = os.getenv("OPENAI_API_KEY") or None
            self.default_model = os.getenv("DEFAULT_MODEL", "claude-sonnet-4-6")

            self.llm_max_retries = _env_int("LLM_MAX_RETRIES", 3)
            self.llm_request_timeout_s = _env_float("LLM_REQUEST_TIMEOUT_S", 60.0)
            self.cache_semantic = _env_bool("CACHE_SEMANTIC", True)
            self.cache_threshold = _env_float("CACHE_THRESHOLD", 0.95)
            self.daily_cost_cap_usd = _env_float("DAILY_COST_CAP_USD", 0.0)

            self.database_url = os.getenv(
                "DATABASE_URL",
                "postgresql+psycopg://postgres:postgres@localhost:5432/agentic",
            )
            self.redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
            self.chroma_url = os.getenv("CHROMA_URL") or None
            self.pinecone_api_key = os.getenv("PINECONE_API_KEY") or None

            self.auth_secret = os.getenv("AUTH_SECRET") or None
            self.otel_exporter_otlp_endpoint = (
                os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT") or None
            )

        @property
        def is_prod(self) -> bool:
            return self.environment.lower() in {"prod", "production"}

        def require_provider_key(self) -> None:
            if not self.companion_mock and not self.anthropic_api_key:
                raise ConfigError(
                    "COMPANION_MOCK=0 but ANTHROPIC_API_KEY is not set. "
                    "Set the key in the environment or stay in mock mode."
                )

        def model_dump(self) -> dict[str, Any]:
            return {
                k: v for k, v in vars(self).items() if not k.startswith("_")
            }

        def redacted(self) -> dict[str, Any]:
            out: dict[str, Any] = {}
            for name, value in self.model_dump().items():
                if name in _SECRET_FIELDS and value:
                    out[name] = "***set***"
                else:
                    out[name] = value
            return out

    def _build_settings() -> "Settings":
        return Settings()


# ---------------------------------------------------------------------------
# Accessor (shared by both paths)
# ---------------------------------------------------------------------------


@lru_cache(maxsize=1)
def get_settings() -> "Settings":
    """Return the process-wide :class:`Settings`, built once and cached.

    Import this everywhere config is needed rather than reading ``os.environ``
    scattered through the code — one door, twelve-factor.
    """

    return _build_settings()


def reload_settings() -> "Settings":
    """Clear the cache and rebuild — for tests that mutate the environment."""

    get_settings.cache_clear()
    return get_settings()


__all__ = ["Settings", "get_settings", "reload_settings"]
