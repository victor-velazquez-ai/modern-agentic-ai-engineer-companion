"""The model port: the single seam every supervisor/worker call goes through.

Why this exists
---------------
The supervisor plans and routes; the workers reason. Both need to *call a model*.
Rather than scatter ``client.messages.create(...)`` through the orchestration code,
everything goes through one tiny port (:class:`ModelPort`). That gives us:

* **Standalone-by-default.** :class:`MockModel` returns deterministic, realistic
  text so the whole team runs in CI and for readers with **no API key and no spend**
  (``COMPANION_MOCK=1``, the default).
* **A clean composition seam.** In the full repo this port is implemented by the
  ``llm-gateway`` blueprint (routing, caching, metering, guards) and each worker is
  an ``agent-loop``. Those packages are planned siblings; until they ship, this module
  carries a faithful local mock so the pattern is real and testable today. See
  :func:`build_model` for exactly where they plug in.

This mirrors the book's "single door to every model call" lesson (Ch 11) and the
``agent-loop`` ``model.py`` injection seam (Ch 12).
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable

# Default Anthropic model used only on the live path (COMPANION_MOCK=0). The book's
# stack is Anthropic-first; keep examples on a current, capable Claude model.
DEFAULT_LIVE_MODEL = "claude-sonnet-4-5"


@dataclass(frozen=True)
class ModelResponse:
    """A single model reply plus the usage we meter on."""

    text: str
    model: str
    input_tokens: int = 0
    output_tokens: int = 0
    mock: bool = True

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens


@runtime_checkable
class ModelPort(Protocol):
    """The one method the orchestration depends on.

    A real ``llm-gateway`` client satisfies this Protocol, so the supervisor can be
    handed a production gateway with zero code change. Keeping the surface this small
    is the point: the team coordinates against an interface, not a vendor SDK.
    """

    def complete(self, prompt: str, *, system: str | None = ..., role: str | None = ...) -> ModelResponse:
        """Return a completion for ``prompt``. ``role`` lets the mock specialize."""
        ...


# Rough token estimate (~4 chars/token) — good enough for mock metering and tests.
def _estimate_tokens(text: str) -> int:
    return max(1, len(text) // 4)


@dataclass
class MockModel:
    """Deterministic, offline stand-in for a real model.

    It is intentionally *not* random: given the same prompt and role it returns the
    same text, so tests assert behavior and the demo reads the same every run. The
    canned responses are role-aware so a researcher worker "sounds like" research and
    a writer "sounds like" prose — enough to show aggregation doing real work.
    """

    name: str = "mock-supervisor-model"
    # Per-instance call counter, handy in tests that assert how often the model ran.
    calls: int = field(default=0)

    def complete(
        self,
        prompt: str,
        *,
        system: str | None = None,
        role: str | None = None,
    ) -> ModelResponse:
        self.calls += 1
        text = self._canned(prompt=prompt, role=role)
        return ModelResponse(
            text=text,
            model=self.name,
            input_tokens=_estimate_tokens((system or "") + prompt),
            output_tokens=_estimate_tokens(text),
            mock=True,
        )

    @staticmethod
    def _topic(prompt: str) -> str:
        """Pull a short topic phrase out of the task text for realistic canned output."""
        # Use the last clause after a colon if present, else the first line.
        tail = prompt.rsplit(":", 1)[-1].strip()
        first_line = tail.splitlines()[0] if tail else prompt
        topic = first_line.strip().strip(".")
        return topic[:80] if topic else "the task"

    def _canned(self, *, prompt: str, role: str | None) -> str:
        topic = self._topic(prompt)
        r = (role or "generalist").lower()
        if "research" in r:
            return (
                f"Findings on {topic}:\n"
                f"- Fact 1: established baseline for {topic}.\n"
                f"- Fact 2: a key trade-off worth flagging.\n"
                f"- Fact 3: one credible source to cite."
            )
        if "writ" in r or "edit" in r:
            return (
                f"{topic.capitalize()} - a clear, concrete summary that turns the "
                f"research into prose a reader can act on, in three tight sentences. "
                f"It states the point, gives the trade-off, and ends with the takeaway."
            )
        if "cod" in r or "engineer" in r:
            return f"def solve():\n    # implements {topic}\n    return 'ok'"
        if "plan" in r or "supervis" in r:
            return f"Plan for {topic}: split into research then synthesis."
        return f"Response regarding {topic}."


@dataclass
class AnthropicModel:
    """Live path (``COMPANION_MOCK=0``). Imported lazily so MOCK runs need no SDK/key.

    This is deliberately thin. In the full repo you would inject the ``llm-gateway``
    client here instead — it adds routing/fallbacks, caching, metering, and guards
    around this same call. Kept minimal so the *pattern* (delegation/aggregation)
    stays the lesson, not provider plumbing.
    """

    model: str = DEFAULT_LIVE_MODEL
    max_tokens: int = 1024

    def complete(
        self,
        prompt: str,
        *,
        system: str | None = None,
        role: str | None = None,
    ) -> ModelResponse:
        # Lazy import: only required when actually hitting the API.
        import anthropic  # noqa: PLC0415  (intentional lazy import)

        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            raise RuntimeError(
                "COMPANION_MOCK=0 but ANTHROPIC_API_KEY is not set. "
                "Export your key or run in MOCK mode (the default)."
            )
        client = anthropic.Anthropic(api_key=api_key)
        sys_prompt = system or (f"You are a {role} agent." if role else None)
        resp = client.messages.create(
            model=self.model,
            max_tokens=self.max_tokens,
            system=sys_prompt or anthropic.NOT_GIVEN,
            messages=[{"role": "user", "content": prompt}],
        )
        # Concatenate text blocks from the response.
        text = "".join(
            getattr(block, "text", "") for block in resp.content if getattr(block, "type", "") == "text"
        )
        usage = getattr(resp, "usage", None)
        return ModelResponse(
            text=text,
            model=self.model,
            input_tokens=getattr(usage, "input_tokens", 0) if usage else 0,
            output_tokens=getattr(usage, "output_tokens", 0) if usage else 0,
            mock=False,
        )


def mock_enabled() -> bool:
    """Whether we run offline. Default is ON — no key, no spend, deterministic."""
    return os.getenv("COMPANION_MOCK", "1").strip().lower() not in {"0", "false", "no"}


def build_model(*, mock: bool | None = None) -> ModelPort:
    """Factory that honors the ``COMPANION_MOCK`` switch.

    Composition seam
    ----------------
    When the sibling blueprints are present you would build the model here from the
    real gateway, e.g.::

        from llm_gateway import Gateway            # ../../llm-gateway/src
        return Gateway.from_env()                  # satisfies ModelPort

    and each worker would wrap an ``agent_loop.AgentLoop`` around it. Until those
    packages ship, MOCK returns the deterministic stand-in and the live path uses a
    thin Anthropic client. Either way the orchestration code is unchanged.
    """
    use_mock = mock_enabled() if mock is None else mock
    if use_mock:
        return MockModel()
    return AnthropicModel()


# A small, mock-only safety net: detect obviously-injected instructions in a task.
_INJECTION = re.compile(
    r"ignore\s+(?:all\s+)?(?:previous\s+|prior\s+)?instructions"
    r"|disregard\s+(?:the\s+)?(?:system|above)"
    r"|leak\s+the\s+system\s+prompt",
    re.I,
)


def looks_like_injection(text: str) -> bool:
    """Cheap heuristic the supervisor uses to refuse hostile task text in MOCK mode.

    The real defense lives in ``llm-gateway`` guards (Ch 41); this keeps the blueprint
    honest about *where* that check belongs without pulling in the whole gateway.
    """
    return bool(_INJECTION.search(text or ""))
