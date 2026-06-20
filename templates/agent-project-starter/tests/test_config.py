"""Settings load from the environment, and the missing-key message is friendly."""

from __future__ import annotations

import pytest

from app.config import Settings


def test_defaults_to_mock_mode() -> None:
    # A fresh copy with no .env should validate and default to MOCK mode (no key needed).
    settings = Settings(_env_file=None)
    assert settings.companion_mock is True
    assert settings.anthropic_api_key is None


def test_reads_values_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("COMPANION_MOCK", "0")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test-123")
    settings = Settings(_env_file=None)
    assert settings.companion_mock is False
    assert settings.anthropic_api_key == "sk-test-123"


def test_require_api_key_returns_key_when_present() -> None:
    settings = Settings(_env_file=None, anthropic_api_key="sk-test-123")
    assert settings.require_api_key() == "sk-test-123"


def test_require_api_key_raises_friendly_error_when_missing() -> None:
    settings = Settings(_env_file=None, companion_mock=False, anthropic_api_key=None)
    with pytest.raises(RuntimeError) as excinfo:
        settings.require_api_key()
    message = str(excinfo.value)
    # Friendly: names the variable and points at the fix.
    assert "ANTHROPIC_API_KEY" in message
    assert "COMPANION_MOCK" in message
