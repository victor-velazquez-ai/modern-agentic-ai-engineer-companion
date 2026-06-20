"""Typed settings, loaded from the environment (and .env) with fail-fast validation.

Secrets come **only** from the environment — never hardcoded, never committed.
This mirrors the capstone's ``core/settings``: one ``Settings`` object, validated
once at startup, with a readable error when a required value is missing.

Usage::

    from app.config import get_settings
    settings = get_settings()      # raises a friendly error if misconfigured
"""

from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings.

    Every field maps to an environment variable of the same name (case-insensitive).
    Add your own fields here as your app grows — that's the one place new config
    is declared, so a missing value fails fast instead of surfacing as a None deep
    in the call stack.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",  # ignore unrelated vars in the environment / .env
    )

    # --- Mock switch -----------------------------------------------------------
    # True (default) => llm.py returns a canned reply: free, offline, deterministic.
    # False => hit the live model API (requires anthropic_api_key).
    companion_mock: bool = True

    # --- Model provider --------------------------------------------------------
    # Required only when companion_mock is False. Kept optional so a fresh copy
    # validates and runs in MOCK mode with no key — the live path checks it
    # explicitly (see require_api_key()).
    anthropic_api_key: str | None = None

    # ▢ TODO: add your own settings here, e.g.
    # database_url: str = Field(default="", description="Postgres DSN")
    # my_feature_flag: bool = False

    # Placeholder kept so the example above has something to copy. Safe to delete.
    app_name: str = Field(default="agent-project-starter", description="App display name")

    def require_api_key(self) -> str:
        """Return the API key, or raise a readable error if it's missing.

        Call this on the live path (companion_mock is False) so the failure is a
        clear message at the boundary, not an opaque SDK error later.
        """
        if not self.anthropic_api_key:
            raise RuntimeError(
                "ANTHROPIC_API_KEY is not set, but COMPANION_MOCK=0 (live mode). "
                "Set the key in your .env (copy .env.example), or set COMPANION_MOCK=1 "
                "to use the free offline mock."
            )
        return self.anthropic_api_key


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Load settings once and cache them.

    Cached so the .env is read a single time per process. Tests that need a fresh
    read (e.g. after monkeypatching the environment) can call
    ``get_settings.cache_clear()``.
    """
    return Settings()
