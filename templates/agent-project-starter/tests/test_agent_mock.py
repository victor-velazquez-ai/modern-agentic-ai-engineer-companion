"""The agent loop runs end-to-end in MOCK mode — no API key, no network, no spend."""

from __future__ import annotations

from app.agent import run
from app.config import Settings
from app.llm import complete


def _mock_settings() -> Settings:
    # Explicit MOCK settings, independent of any .env on the machine running tests.
    return Settings(_env_file=None, companion_mock=True, anthropic_api_key=None)


def test_llm_complete_is_canned_in_mock_mode() -> None:
    reply = complete("ping", settings=_mock_settings())
    assert reply.startswith("[MOCK]")
    assert "ping" in reply  # the mock echoes a preview of the prompt


def test_agent_run_returns_a_string_without_a_key() -> None:
    answer = run("What is 21 + 21?", settings=_mock_settings())
    assert isinstance(answer, str)
    assert answer  # non-empty
    assert "[MOCK]" in answer
