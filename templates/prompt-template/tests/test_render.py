"""Rendering tests: placeholders fill, and unknown/missing vars fail loudly.

These guard the core promise of the registry — that a prompt change which drops
or renames a variable is caught like any other code bug, not shipped silently.

Run from the template root:  pytest -q
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

# Make registry.py importable when running pytest from anywhere.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import registry  # noqa: E402  (import after sys.path tweak)


def test_render_fills_placeholders() -> None:
    out = registry.render(
        "Hello {{name}}, welcome to {{place}}.",
        {"name": "Jordan", "place": "Acme"},
    )
    assert out == "Hello Jordan, welcome to Acme."


def test_render_tolerates_whitespace_in_placeholders() -> None:
    out = registry.render("{{ greeting }} world", {"greeting": "hi"})
    assert out == "hi world"


def test_render_missing_variable_raises() -> None:
    with pytest.raises(registry.MissingVariableError):
        registry.render("Hello {{name}}", {})


def test_render_unknown_variable_raises() -> None:
    # Supplying a variable the template never uses is an error on purpose:
    # it almost always means a typo or a stale call site.
    with pytest.raises(registry.UnknownVariableError):
        registry.render("Hello there", {"name": "Jordan"})


def test_render_repeated_placeholder() -> None:
    out = registry.render("{{x}} and {{x}}", {"x": "ok"})
    assert out == "ok and ok"


def test_load_renders_example_prompt() -> None:
    rendered = registry.load(
        "support_reply",
        "v1",
        variables={
            "company_name": "Acme Co.",
            "agent_name": "Sam",
            "customer_name": "Jordan",
            "customer_message": "Where is my order?",
            "tone": "warm and concise",
        },
    )
    assert "Acme Co." in rendered.system
    assert "Jordan" in rendered.messages[0]["content"]
    assert rendered.messages[0]["role"] == "user"


def test_load_missing_variable_raises() -> None:
    with pytest.raises(registry.MissingVariableError):
        registry.load("support_reply", "v1", variables={"company_name": "Acme Co."})
