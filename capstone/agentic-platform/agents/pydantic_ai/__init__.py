"""agents.pydantic_ai — the Pydantic AI variant of the platform agent (Ch 18).

The third "one agent, three ways" build: the same agent as ``agents/raw`` and ``agents/graph``,
expressed as a typed agent object with tools registered as decorated functions. ``pydantic-ai`` is
an *optional* dependency; with it installed :class:`PydanticAgent` builds a real ``Agent``, and
without it (the default offline path) it drives the same tools and model port through a typed loop
with identical behaviour — so the three builds are directly comparable.

>>> from agents.pydantic_ai import PydanticAgent
>>> from agents.tools import default_toolset, MockModel, assistant, ToolCall
>>> model = MockModel([
...     assistant(tool_calls=(ToolCall(id="1", name="calculator", arguments={"expression": "10/2"}),)),
...     lambda t: assistant(text=f"Result: {t[-1].text}."),
... ])
>>> PydanticAgent(model=model, tools=default_toolset()).run("what is 10 / 2?").output
'Result: 5.'
"""

from __future__ import annotations

from .agent import (
    HAS_PYDANTIC_AI,
    AgentRunResult,
    PydanticAgent,
)

__all__ = [
    "PydanticAgent",
    "AgentRunResult",
    "HAS_PYDANTIC_AI",
]
