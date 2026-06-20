#!/usr/bin/env python3
"""Runnable demo — a 2-tool agent (calculator + clock) driven by the loop, in MOCK mode.

    python demo.py

Runs **free, offline, and deterministically** (``COMPANION_MOCK`` defaults to ``1``). It wires
two real tools into the loop and a scripted mock "brain" that picks the right tool for the ask,
then watches the ``observe -> decide -> act -> observe`` cycle resolve a multi-tool turn.

The point of the demo is the *loop*, not the model: the mock is deliberately boring so the
control flow is what you see. For the live path, set ``COMPANION_MOCK=0`` and inject an
``llm-gateway``-backed :class:`ModelPort` (see the README) — the tools and the loop don't change.
"""

from __future__ import annotations

import os
import sys
from datetime import datetime, timezone
from pathlib import Path

# Let the demo run straight from a clone (before `pip install -e .`).
sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from agent_loop import (  # noqa: E402  (after sys.path tweak)
    AgentLoop,
    MockModel,
    ToolError,
    ToolRegistry,
    assistant,
    echo_calculator_clock,
    tool,
)

MOCK = os.getenv("COMPANION_MOCK", "1") != "0"

# A fixed clock so the demo output is deterministic (the standards want reproducible cells).
_FIXED_NOW = datetime(2026, 6, 20, 14, 30, 0, tzinfo=timezone.utc)

_ALLOWED = set("0123456789+-*/.() ")


@tool(
    "calculator",
    "Evaluate a basic arithmetic expression (+ - * / and parentheses).",
    {
        "type": "object",
        "properties": {"expression": {"type": "string", "description": "e.g. '2 + 3 * 4'"}},
        "required": ["expression"],
    },
)
def calculator(expression: str) -> str:
    """A *safe* tiny calculator — character-allowlisted, no general ``eval`` of model input.

    Letting a model's text reach ``eval`` unfiltered is a classic injection foot-gun (Ch 41). We
    allow only arithmetic characters and raise a clean :class:`ToolError` otherwise, so the loop
    reports it back to the model instead of executing something dangerous.
    """
    expr = expression.strip()
    if not expr or any(ch not in _ALLOWED for ch in expr):
        raise ToolError(f"unsafe or empty expression: {expression!r}. Use digits and + - * / ( ).")
    try:
        # nosec: input is allowlisted to arithmetic characters only.
        value = eval(expr, {"__builtins__": {}}, {})  # noqa: S307
    except (SyntaxError, ZeroDivisionError, NameError) as exc:
        raise ToolError(f"could not evaluate {expr!r}: {exc}") from exc
    return str(value)


@tool("clock", "Return the current UTC time as an ISO-8601 string.")
def clock() -> str:
    return _FIXED_NOW.isoformat()


def build_model() -> object:
    """The model the loop will drive.

    In MOCK mode (default) we use a scripted brain that calls the right tool for the prompt and
    then phrases an answer from the tool results. In live mode we fail loud rather than spend —
    wire an ``llm-gateway`` port here.
    """
    if MOCK:
        return MockModel(
            [
                # turn 1: look at the user's ask and call the matching tool(s)
                echo_calculator_clock,
                # turn 2: read the tool result(s) and answer
                lambda transcript: assistant(text=_summarize(transcript)),
            ]
        )
    raise SystemExit(
        "COMPANION_MOCK=0 set, but this demo ships only the mock model. Inject an "
        "llm-gateway-backed ModelPort here to run live (see README -> Live path)."
    )


def _summarize(transcript: list) -> str:
    """Phrase a final answer from the tool results in the transcript (mock 'reasoning')."""
    results = [m for m in transcript if m.role == "tool"]
    parts = [f"{r.tool_result.name} -> {r.text}" for r in results]
    return "Here is what my tools returned: " + "; ".join(parts) + "." if parts else "No tools were needed."


def main() -> int:
    tools = ToolRegistry([calculator, clock])

    # An on_event hook prints the cycle so you can *see* observe->decide->act->observe.
    def trace(name: str, payload: dict) -> None:
        print(f"  [{name}] {payload}")

    loop = AgentLoop(model=build_model(), tools=tools, max_turns=6, on_event=trace)

    task = "What is 2 + 3 * 4, and what time is it now?"
    print(f"MOCK={'1' if MOCK else '0'}  |  tools: {tools.names()}")
    print(f"\nUser: {task}\n")

    result = loop.run(task)

    print(f"\nAgent: {result.output}")
    print(f"\nstop_reason={result.stop_reason.value}  turns={result.turns}")
    print(f"transcript: {[m.role for m in result.transcript]}")

    # A blueprint demo should also be a smoke test: assert the happy path actually happened.
    assert result.ok, f"demo did not complete cleanly: {result.stop_reason}"
    assert "14" in result.output and "2026-06-20T14:30:00" in result.output
    print("\nOK — multi-tool turn resolved end to end with no API spend.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
