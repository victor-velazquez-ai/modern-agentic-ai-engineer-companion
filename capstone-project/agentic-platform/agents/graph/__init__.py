"""agents.graph — the LangGraph variant of the platform agent (Ch 18).

The same agent as ``agents/raw``, expressed as an explicit state graph (nodes ``agent`` and
``tools``, a conditional edge that loops while the model keeps calling tools). LangGraph is an
*optional* dependency: with it installed, :func:`build_graph` compiles a real ``StateGraph``;
without it (the default offline path), :class:`GraphAgent` runs the identical graph via a tiny
no-dependency scheduler. Either way the behaviour matches the raw loop — which is the Ch 18 lesson:
the agent is the nodes and edges, not the runner.

>>> from agents.graph import GraphAgent
>>> from agents.tools import default_toolset, MockModel, assistant, ToolCall
>>> model = MockModel([
...     assistant(tool_calls=(ToolCall(id="1", name="calculator", arguments={"expression": "6*7"}),)),
...     lambda t: assistant(text=f"It is {t[-1].text}."),
... ])
>>> GraphAgent(model=model, tools=default_toolset()).run("what is 6 * 7?").output
'It is 42.'
"""

from __future__ import annotations

from .agent import (
    HAS_LANGGRAPH,
    GraphAgent,
    GraphNodes,
    GraphResult,
    GraphState,
    build_graph,
)

__all__ = [
    "GraphAgent",
    "GraphResult",
    "GraphState",
    "GraphNodes",
    "build_graph",
    "HAS_LANGGRAPH",
]
