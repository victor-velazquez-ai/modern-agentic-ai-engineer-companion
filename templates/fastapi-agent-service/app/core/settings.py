"""Application configuration (12-factor, Ch 28).

All configuration is read from the environment (and a local, git-ignored
``.env`` file). Secrets live **only** in ``.env`` — never in committed code.
Settings are constructed once at startup and injected via ``Depends`` so the
rest of the app never reaches for ``os.environ`` directly.

Fail-fast: required fields with no default will raise a ``ValidationError`` on
startup if they are missing, so a misconfigured deploy never boots half-working.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Strongly-typed application settings.

    ▢ TODO: add your own fields here (database URL, vector-store URL, model name,
    rate-limit window, etc.). Give optional settings a default; leave secrets and
    truly-required values without one so startup fails fast when they are unset.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # --- Runtime ------------------------------------------------------------
    app_name: str = "fastapi-agent-service"
    app_env: Literal["local", "dev", "staging", "prod"] = "local"
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"

    # --- Mock mode ----------------------------------------------------------
    # When true, the agent service yields canned tokens instead of calling a real
    # model. Lets you exercise the full request/stream path with no API spend.
    companion_mock: bool = Field(
        default=True,
        validation_alias="COMPANION_MOCK",
        description="If true, stream canned tokens instead of calling the model.",
    )

    # --- Secrets (read from .env only; do NOT hard-code) --------------------
    # Optional here so the service boots in MOCK mode without a key. Make this
    # required (drop the default) once you wire a real provider in live mode.
    # ▢ TODO: set ANTHROPIC_API_KEY in your .env for live (non-mock) runs.
    anthropic_api_key: str | None = Field(default=None, repr=False)

    # Shared secret used by the bearer-auth stub in `security.py`.
    # ▢ TODO: replace this stub with your real IdP / JWT verification.
    auth_secret: str | None = Field(default=None, repr=False)

    @property
    def is_mock(self) -> bool:
        """True when the service should avoid any real model/API call."""
        return self.companion_mock


@lru_cache
def get_settings() -> Settings:
    """Return a process-wide, cached ``Settings`` instance.

    Cached so the ``.env`` file and environment are read exactly once. Tests can
    override this via FastAPI dependency overrides (see ``core/deps.py``).
    """
    return Settings()
