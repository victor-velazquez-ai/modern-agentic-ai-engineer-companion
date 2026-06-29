"""The model port — the one seam between every agent variant and a concrete LLM (Ch 11/12).

No agent variant imports an SDK. They all talk to a :class:`ModelPort`: given the transcript and
the available tool schemas, return the next assistant turn (text and/or tool calls). That one
seam is what makes the loop testable, provider-agnostic, and cheap to run — and it is the place
the platform's real ``llm/gateway.py`` client plugs in (routing, fallbacks, caching, metering,
guards) with zero change to the agents that use it.

Two implementations ship here:

* :class:`MockModel` — **the default**. A deterministic, offline, *scriptable* model that spends
  no tokens and produces the same turns every run, which is what makes the tests and demos
  reproducible. You drive it with a small script of canned turns.
* A live model is **not** vendored. Under ``COMPANION_MOCK=0`` the live path constructs the
  gateway-backed port (or, until that directory is built, a thin Anthropic client); :func:`default_model`
  documents that seam and fails loud rather than silently importing a not-yet-built dependency or
  spending money behind the caller's back.

Secrets are read from the environment only (``ANTHROPIC_API_KEY``); nothing here hard-codes a key.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Callable, Protocol, runtime_checkable

from .messages import Message, ToolCall, assistant

if TYPE_CHECKING:  # only for type hints; no runtime cost / import cycle
    from .schemas import ToolSpec

# The book's stack is Anthropic-first; keep examples on a current, capable Claude model.
DEFAULT_LIVE_MODEL = "claude-sonnet-4-5"


@dataclass(frozen=True, slots=True)
class ModelResponse:
    """One model step: the assistant turn it produced, plus best-effort usage.

    ``usage`` is informational (the gateway is the real cost-accounting layer, Ch 40); the loop
    only reads ``message``. Keeping it here lets a caller log tokens without a second round-trip.
    """

    message: Message
    usage: dict[str, int] = field(default_factory=dict)


@runtime_checkable
class ModelPort(Protocol):
    """The single method any agent variant needs from a model.

    Given the running ``transcript`` and the ``tools`` the model is allowed to call, return the
    next assistant turn. Implementations translate the typed ledger to/from their wire format; the
    agents stay vendor-neutral. A real gateway client satisfies this Protocol structurally — no
    inheritance required, so injection is one constructor argument.
    """

    def complete(self, transcript: list[Message], tools: "list[ToolSpec]") -> ModelResponse:
        """Return the model's next assistant turn for this transcript + toolset."""
        ...


# A scripted step is either a ready-made assistant Message, or a callable that builds one from the
# live transcript (so a mock can *react* — e.g. answer using the last tool result).
ScriptStep = Message | Callable[[list[Message]], Message]


class MockModel:
    """A deterministic, offline model you script with canned turns.

    The mock pops one ``ScriptStep`` per :meth:`complete` call. A step is either a literal
    assistant :class:`Message` or a callable that receives the current transcript and returns one —
    the callable form lets a mock *use* a tool result (read the calculator's answer and phrase a
    final reply), which is exactly what a real model does. When the script is exhausted, the mock
    emits a terminal text turn (no tool calls), so a loop driven by a too-short script terminates
    cleanly instead of hanging.

    Convenience: pass ``answer=`` instead of a script for a trivial one-shot model that just
    replies with that text — handy in tests that don't care about tools.
    """

    def __init__(
        self,
        script: list[ScriptStep] | None = None,
        *,
        answer: str | None = None,
        on_exhausted: str = "Done.",
    ) -> None:
        if script is None and answer is not None:
            script = [assistant(text=answer)]
        self._script: list[ScriptStep] = list(script or [])
        self._on_exhausted = on_exhausted
        self.calls: int = 0  # how many times the loop asked us to think (test introspection)

    def complete(self, transcript: list[Message], tools: "list[ToolSpec]") -> ModelResponse:
        self.calls += 1
        if not self._script:
            return ModelResponse(assistant(text=self._on_exhausted))
        step = self._script.pop(0)
        msg = step(list(transcript)) if callable(step) else step
        if msg.role != "assistant":
            raise ValueError("MockModel script steps must produce an 'assistant' turn")
        return ModelResponse(msg, usage={"input_tokens": 0, "output_tokens": 0})


def keyword_tool_picker(transcript: list[Message]) -> Message:
    """A tiny scripted 'brain' for demos: parse the user's ask, call the right platform tool.

    This is *not* an LLM — it's a deterministic stand-in that picks a tool by keyword so a demo
    shows a real tool turn with zero API spend. It recognizes the platform's mock tools
    (``calculator``, ``clock``, ``search_docs``). The point of a demo is the *loop*, not the
    cleverness of the model; the mock keeps the model boring on purpose.
    """
    last_user = next((m for m in reversed(transcript) if m.role == "user"), None)
    ask = (last_user.text if last_user else "").lower()
    calls: list[ToolCall] = []
    if any(k in ask for k in ("+", "plus", "add", "sum", "calculate", "*", "times")):
        calls.append(ToolCall(id="c1", name="calculator", arguments={"expression": _extract_expr(ask)}))
    if any(k in ask for k in ("time", "clock", "date", "now")):
        calls.append(ToolCall(id="c2", name="clock", arguments={}))
    if any(k in ask for k in ("search", "find", "look up", "document", "docs", "policy")):
        calls.append(ToolCall(id="c3", name="search_docs", arguments={"query": ask[:80]}))
    if calls:
        return assistant(text="Let me use my tools.", tool_calls=tuple(calls))
    return assistant(text="I don't have a tool for that, but I'm here to help.")


def _extract_expr(text: str) -> str:
    """Pull a simple arithmetic expression out of free text (demo-grade)."""
    normalized = text.replace("plus", "+").replace("times", "*")
    m = re.search(r"\d[-+*/0-9.\s]*\d|\d", normalized)
    return (m.group(0).strip() if m else "1+1") or "1+1"


def mock_enabled() -> bool:
    """Whether we run offline. Default is ON — no key, no spend, deterministic."""
    return os.getenv("COMPANION_MOCK", "1").strip().lower() not in {"0", "false", "no"}


def default_model() -> ModelPort:
    """Return the model chosen by the environment.

    ``COMPANION_MOCK`` defaults to ``"1"`` — the offline mock, free and deterministic. Under
    ``MOCK=0`` the live path would construct the ``llm/gateway.py`` port here; we ship only the
    mock and document the seam rather than importing a not-yet-present dependency or spending
    tokens behind the caller's back. Inject a real :class:`ModelPort` explicitly for live runs.
    """
    if mock_enabled():
        # An unscripted mock answers in one shot; callers wanting tool behaviour pass their own.
        return MockModel(answer="(mock) set COMPANION_MOCK=0 and inject a gateway port for live.")
    raise RuntimeError(
        "COMPANION_MOCK=0 requested a live model, but no llm/gateway.py client is wired in. "
        "Inject a ModelPort explicitly (see the model.py seam) or run with COMPANION_MOCK=1."
    )
