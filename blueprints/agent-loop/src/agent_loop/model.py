"""The model port — the seam between the loop and a concrete LLM (Ch 11/12).

The loop never imports an SDK. It talks to a :class:`ModelPort`: given the transcript and the
available tool schemas, return the next assistant turn (text and/or tool calls). That one seam is
what makes the loop testable, provider-agnostic, and cheap to run.

Two implementations ship here:

* :class:`MockModel` — **the default**. A deterministic, offline, *scriptable* model. It spends
  no tokens and produces the same turns every run, which is what makes the tests and the demo
  reproducible. You drive it with a small script of canned turns (and, for recovery tests, with
  deliberately malformed tool calls).
* A live model is **not** vendored here. In production you inject a port backed by the
  ``llm-gateway`` blueprint (``../../llm-gateway/``); :func:`default_model` documents that seam
  and fails loud under ``MOCK=0`` rather than silently importing a not-yet-built dependency or
  spending money. This mirrors how :mod:`memory_module.summarize` handles the same seam.

Why a port and not just "call Anthropic here"? Because four later chapters (20/25/46/47) reuse
this loop with *different* models, and the eval-harness drives it with a stub. A loop welded to
one SDK can't be any of those things.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Callable, Protocol, runtime_checkable

from .messages import Message, ToolCall, assistant

if TYPE_CHECKING:  # only for type hints; no runtime cost / import cycle
    from .tools import ToolSpec


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
    """The single method the loop needs from any model.

    Given the running ``transcript`` and the ``tools`` the model is allowed to call, return the
    next assistant turn. Implementations translate the typed ledger to/from their wire format; the
    loop stays vendor-neutral. A real gateway client satisfies this Protocol structurally — no
    inheritance required, so injection is one constructor argument.
    """

    def complete(self, transcript: list[Message], tools: "list[ToolSpec]") -> ModelResponse:
        """Return the model's next assistant turn for this transcript + toolset."""
        ...


# A scripted step is either a ready-made assistant Message, or a callable that builds one from
# the live transcript (so a mock can *react* — e.g. answer using the last tool result).
ScriptStep = Message | Callable[[list[Message]], Message]


class MockModel:
    """A deterministic, offline model you script with canned turns.

    The mock pops one ``ScriptStep`` per :meth:`complete` call. A step is either a literal
    assistant :class:`Message` or a callable that receives the current transcript and returns one
    — the callable form lets a mock *use* a tool result (e.g. read the calculator's answer and
    phrase a final reply), which is exactly what a real model does.

    When the script is exhausted, the mock emits a terminal text turn (no tool calls), so a loop
    driven by a too-short script terminates cleanly instead of hanging.

    Convenience: pass ``answer=`` instead of a script to get a trivial one-shot model that just
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


def echo_calculator_clock(transcript: list[Message]) -> Message:
    """A tiny scripted 'brain' for the demo: parse the user's ask, call the right tool.

    This is *not* an LLM — it's a deterministic stand-in that picks a tool by keyword so the demo
    shows a real multi-tool turn with zero API spend. The point of the demo is the *loop*, not the
    cleverness of the model; the mock keeps the model boring on purpose.
    """
    last_user = next(
        (m for m in reversed(transcript) if m.role == "user"),
        None,
    )
    ask = (last_user.text if last_user else "").lower()
    calls: list[ToolCall] = []
    if any(k in ask for k in ("+", "plus", "add", "sum", "calculate", "*", "times")):
        expr = _extract_expr(ask)
        calls.append(ToolCall(id="c1", name="calculator", arguments={"expression": expr}))
    if any(k in ask for k in ("time", "clock", "date", "now")):
        calls.append(ToolCall(id="c2", name="clock", arguments={}))
    if calls:
        return assistant(text="Let me use my tools.", tool_calls=tuple(calls))
    return assistant(text="I don't have a tool for that, but I'm here to help.")


def _extract_expr(text: str) -> str:
    """Pull a simple arithmetic expression out of free text (demo-grade).

    Anchored on digits: we find a run that starts and ends with a number and may contain
    operators/spaces between them, so 'what is 2 + 3 * 4, and ...' yields '2 + 3 * 4' rather
    than a stray leading space. Not a real parser — just enough for the demo's mock brain.
    """
    normalized = text.replace("plus", "+").replace("times", "*")
    m = re.search(r"\d[-+*/0-9.\s]*\d|\d", normalized)
    return (m.group(0).strip() if m else "1+1") or "1+1"


def default_model() -> ModelPort:
    """Return the model chosen by the environment.

    ``COMPANION_MOCK`` defaults to ``"1"`` — the offline mock, free and deterministic. Under
    ``MOCK=0`` a live path would construct a gateway-backed port here; we ship only the mock and
    document the seam rather than importing a not-yet-present dependency or spending tokens behind
    the caller's back.
    """
    mock = os.getenv("COMPANION_MOCK", "1") != "0"
    if mock:
        # An unscripted mock answers in one shot; callers wanting tool behaviour pass their own.
        return MockModel(answer="(mock) set COMPANION_MOCK=0 and inject a gateway port for live.")
    raise RuntimeError(
        "COMPANION_MOCK=0 requested a live model, but no llm-gateway client is wired in. "
        "Inject a ModelPort explicitly (see README -> Live path / the model.py seam) or run with "
        "COMPANION_MOCK=1."
    )
