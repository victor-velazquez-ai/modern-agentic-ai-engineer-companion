"""Registry tests: `load()` resolves "latest" and a pinned version deterministically.

These cover the operational guarantees you rely on in production: that pinning a
version is reproducible, that "latest" comes from the `meta.yaml` pointer (not
from whatever sorts highest on disk), and that v1 vs v2 actually differ.

Run from the template root:  pytest -q
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import registry  # noqa: E402

# Variables every version of the example prompt needs.
VARS = {
    "company_name": "Acme Co.",
    "agent_name": "Sam",
    "customer_name": "Jordan",
    "customer_message": "Where is my order?",
    "tone": "warm and concise",
}


def test_example_prompt_is_discoverable() -> None:
    assert "support_reply" in registry.available_prompts()


def test_two_versions_present() -> None:
    # The template ships two versions to demonstrate diff / rollback.
    assert registry.list_versions("support_reply") == ["v1", "v2"]


def test_latest_resolves_from_meta_pointer() -> None:
    # Deterministic: "latest" is whatever meta.yaml's `latest:` points to.
    assert registry.resolve_version("support_reply", "latest") == "v2"


def test_latest_is_deterministic_across_calls() -> None:
    first = registry.load("support_reply", "latest", variables=VARS)
    second = registry.load("support_reply", "latest", variables=VARS)
    assert first.version == second.version
    assert first.messages == second.messages
    assert first.system == second.system


def test_pinned_version_differs_from_latest() -> None:
    v1 = registry.load("support_reply", "v1", variables=VARS)
    v2 = registry.load("support_reply", "v2", variables=VARS)
    # Pinning v1 vs v2 must produce different prompts (else there's nothing to
    # A/B or roll back to).
    assert v1.version == "v1"
    assert v2.version == "v2"
    assert v1.system != v2.system


def test_meta_model_and_params_loaded() -> None:
    rendered = registry.load("support_reply", "latest", variables=VARS)
    assert rendered.model == "claude-opus-4-8"
    assert rendered.params.get("max_tokens") == 1024


def test_unknown_prompt_raises() -> None:
    with pytest.raises(registry.PromptNotFoundError):
        registry.load("does_not_exist", variables={})


def test_unknown_version_raises() -> None:
    with pytest.raises(registry.PromptNotFoundError):
        registry.load("support_reply", "v99", variables=VARS)
