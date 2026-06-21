"""Application configuration — twelve-factor, fail-fast (Ch 4, 28).

All configuration is read from the environment (and a local, git-ignored ``.env`` file).
Secrets live **only** in the environment — never in committed code. ``Settings`` is built once
at startup and injected via ``Depends`` so the rest of the app never reaches for ``os.environ``
directly. This is the capstone's grown-up version of the template's ``core/settings.py``: same
discipline, more fields (DB, Redis, vector store, auth, OTel) as the platform accretes.

Fail-fast: required fields with no default raise a ``ValidationError`` on startup if missing,
so a misconfigured deploy never boots half-working. In MOCK mode (the default) every secret is
optional, so the whole stack runs offline with zero keys.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field, ValidationInfo, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

Environment = Literal["local", "dev", "staging", "prod"]
LogLevel = Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]


class Settings(BaseSettings):
    """Strongly-typed application settings, loaded from env / ``.env``.

    Optional settings carry a default; secrets and truly-required values are left without one so
    startup fails fast when they are unset (in live mode). Mock mode keeps everything optional so
    the service boots offline.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # --- Runtime -----------------------------------------------------------------
    app_name: str = "agentic-platform"
    app_env: Environment = "local"
    log_level: LogLevel = "INFO"

    # --- Mock mode ---------------------------------------------------------------
    # When true, the agent engine yields canned tokens instead of calling a real model, and
    # secret-backed adapters fall back to in-memory stand-ins. Lets the full request/stream
    # path run with no API spend. Read from COMPANION_MOCK to match the repo-wide switch.
    companion_mock: bool = Field(
        default=True,
        validation_alias="COMPANION_MOCK",
        description="If true, run offline: canned model tokens, in-memory adapters.",
    )

    # --- Model providers (read from env only; never hard-code) -------------------
    anthropic_api_key: str | None = Field(default=None, repr=False)
    openai_api_key: str | None = Field(default=None, repr=False)
    default_model: str = "claude-sonnet"

    # --- Data layer (Ch 30) ------------------------------------------------------
    # Async SQLAlchemy DSN. The compose default points at the local Postgres container; the
    # in-memory SQLite default keeps tests and MOCK runs dependency-free.
    database_url: str = Field(
        default="sqlite+aiosqlite:///:memory:",
        description="Async SQLAlchemy DSN (Postgres in prod, SQLite for local/tests).",
    )
    db_pool_size: int = Field(default=5, ge=1, le=100)
    db_echo: bool = False

    # --- Redis (Celery broker/result + cache, Ch 31) -----------------------------
    redis_url: str = Field(
        default="redis://localhost:6379/0",
        description="Celery broker, result backend, and cache.",
    )

    # --- Vector store (Ch 13) ----------------------------------------------------
    chroma_url: str | None = None
    pinecone_api_key: str | None = Field(default=None, repr=False)

    # --- Auth (Ch 26) ------------------------------------------------------------
    # Shared secret used by the bearer-auth stub. When unset (local/MOCK), auth is open so the
    # service runs out of the box; set it to turn enforcement on.
    auth_secret: str | None = Field(default=None, repr=False)
    auth_token_ttl_seconds: int = Field(default=3600, ge=60)

    # --- Rate limiting (Ch 26) ---------------------------------------------------
    rate_limit_per_minute: int = Field(default=60, ge=1)
    rate_limit_burst: int = Field(default=20, ge=1)

    # --- Observability (Ch 23) ---------------------------------------------------
    otel_exporter_otlp_endpoint: str | None = None

    @field_validator("anthropic_api_key")
    @classmethod
    def _require_key_in_live_mode(
        cls, value: str | None, info: ValidationInfo
    ) -> str | None:
        """Enforce a primary key once mock mode is off (fail-fast in live deploys)."""
        if value is None and info.data.get("companion_mock") is False:
            raise ValueError(
                "ANTHROPIC_API_KEY is required when COMPANION_MOCK is false. "
                "Set the key, or run with COMPANION_MOCK=1 for the offline mock."
            )
        return value

    @property
    def is_mock(self) -> bool:
        """True when the service should avoid any real model/API call."""
        return self.companion_mock

    @property
    def auth_enabled(self) -> bool:
        """True when a bearer token is required (``AUTH_SECRET`` is set)."""
        return bool(self.auth_secret)


@lru_cache
def get_settings() -> Settings:
    """Return a process-wide, cached ``Settings`` instance.

    Cached so the ``.env`` file and environment are read exactly once. Tests override this via
    FastAPI dependency overrides (see ``core/deps.py``) or by clearing the cache.
    """
    return Settings()
