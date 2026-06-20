"""One door to the model SDK.

Every call to the LLM goes through ``complete()`` here. Centralizing it gives you a
single place to add retries, usage logging, timeouts, or a provider swap later —
the chapter calls this "one door to the SDK".

In MOCK mode (the default; ``COMPANION_MOCK=1``) this returns a canned reply with no
network call, so a fresh clone, ``make test``, and ``make run`` all work **free and
offline**. Set ``COMPANION_MOCK=0`` with an ``ANTHROPIC_API_KEY`` to hit the live API.
"""

from __future__ import annotations

import os

from app.config import Settings, get_settings

# The default model id. One constant — change it here to change it everywhere.
# claude-opus-4-8 is the current most-capable model. Override per-process with the
# MODEL environment variable if you need a different one.
MODEL: str = os.environ.get("MODEL", "claude-opus-4-8")

# A deterministic, recognizable canned reply for MOCK mode.
_MOCK_REPLY = "[MOCK] Set COMPANION_MOCK=0 and ANTHROPIC_API_KEY to call the live model."


def complete(prompt: str, *, settings: Settings | None = None, max_tokens: int = 1024) -> str:
    """Send ``prompt`` to the model and return the text reply.

    Args:
        prompt: The user prompt.
        settings: Injected settings (defaults to the process settings). Passing this
            explicitly makes the function easy to test.
        max_tokens: Output cap for the live call.

    Returns:
        The model's text reply (or the canned mock reply in MOCK mode).
    """
    settings = settings or get_settings()

    if settings.companion_mock:
        return _mock_complete(prompt)

    return _live_complete(prompt, settings=settings, max_tokens=max_tokens)


def _mock_complete(prompt: str) -> str:
    """Canned, deterministic reply — no network, no key, no cost."""
    # Echo a little of the prompt so mock runs are self-explanatory in logs.
    preview = prompt.strip().splitlines()[0][:80] if prompt.strip() else "(empty prompt)"
    return f'{_MOCK_REPLY} (you asked: "{preview}")'


def _live_complete(prompt: str, *, settings: Settings, max_tokens: int) -> str:
    """Real call to the Anthropic Messages API.

    Imported lazily so MOCK-mode users don't pay the import cost and so the
    template's tests run without the SDK configured.
    """
    import anthropic

    client = anthropic.Anthropic(api_key=settings.require_api_key())

    response = client.messages.create(
        model=MODEL,
        max_tokens=max_tokens,
        # Adaptive thinking lets the model decide how much to reason per request.
        thinking={"type": "adaptive"},
        messages=[{"role": "user", "content": prompt}],
    )

    # response.content is a list of blocks; take the text blocks.
    return "".join(block.text for block in response.content if block.type == "text")
