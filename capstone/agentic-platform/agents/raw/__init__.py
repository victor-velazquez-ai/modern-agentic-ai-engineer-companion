"""agents.raw — the framework-free agent loop (Ch 12, 20).

The no-framework engine everything else in the platform grows around: the
``observe → decide → gate → act → observe`` cycle implemented directly against a model port, with
the parts a senior actually ships (turn cap, tool-error recovery, malformed-call repair,
cancellation) plus the human-in-the-loop approval gate — and **no orchestration library hiding the
control flow**.

The ``graph/`` and ``pydantic_ai/`` packages express *this same agent* in their respective
frameworks (Ch 18); the supervisor delegates to *this* loop per worker (Ch 17). Importing from
``agents.raw`` gives you the canonical engine and its result type.

>>> from agents.raw import AgentLoop, run_agent, StopReason
>>> from agents.tools import default_toolset, MockModel, assistant, ToolCall
>>> model = MockModel([
...     assistant(tool_calls=(ToolCall(id="1", name="calculator", arguments={"expression": "2+3"}),)),
...     lambda t: assistant(text=f"The answer is {t[-1].text}."),
... ])
>>> loop = AgentLoop(model=model, tools=default_toolset())
>>> result = loop.run("what is 2 + 3?")
>>> result.output
'The answer is 5.'
>>> result.stop_reason is StopReason.COMPLETED
True
"""

from __future__ import annotations

from .loop import (
    AgentLoop,
    AgentResult,
    CancelFn,
    StopReason,
    run_agent,
)

__all__ = [
    "AgentLoop",
    "AgentResult",
    "StopReason",
    "CancelFn",
    "run_agent",
]
