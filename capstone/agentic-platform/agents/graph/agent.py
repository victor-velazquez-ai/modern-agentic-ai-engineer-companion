"""The LangGraph variant (Ch 18) — the same agent expressed as an explicit state graph.

This is *the same agent* as ``agents/raw`` — same toolset, same model port, same observe → decide
→ act → observe behaviour — but expressed as a **graph** of nodes and edges instead of a ``while``
loop. The point of Ch 18 is to build one agent three ways and feel the trade-offs: the graph makes
control flow a declared object (nodes: ``agent``, ``tools``; a conditional edge that loops while
the model keeps calling tools), which buys you checkpointing, streaming, and visualization — at
the cost of a dependency and a layer of indirection over the plain loop.

MOCK-runnable design
--------------------
LangGraph is an *optional* dependency. So this module is written to run **with or without it**:

* If ``langgraph`` is importable, :func:`build_graph` compiles a real ``StateGraph`` with two
  nodes and a conditional edge, and :class:`GraphAgent` runs it.
* If it is not (the default offline path, and CI without the extra), :class:`GraphAgent` falls back
  to an equivalent hand-rolled node walk over the *same* state and *same* nodes — identical
  semantics, zero dependency. The fallback is not a toy: it is the literal graph the LangGraph
  version compiles, executed by a tiny scheduler, so the lesson (graph-shaped control flow) holds
  either way.

The state, the node functions, and the routing predicate are framework-agnostic and shared by both
paths — which is itself the Ch 18 insight: the *agent* is the nodes + edges, not the runner.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ..tools.errors import MalformedToolCall, repair_tool_call
from ..tools.messages import Message, Transcript, tool as tool_message
from ..tools.model import ModelPort, default_model
from ..tools.schemas import ToolRegistry

# Whether the real framework is present. We probe once at import; everything still works if not.
try:  # pragma: no cover - presence depends on the environment
    import langgraph  # noqa: F401

    HAS_LANGGRAPH = True
except Exception:  # noqa: BLE001
    HAS_LANGGRAPH = False


# ---------------------------------------------------------------------------------------------
# Shared graph state + nodes (framework-agnostic — both paths use these)
# ---------------------------------------------------------------------------------------------


@dataclass
class GraphState:
    """The state threaded through the graph — the transcript plus the loop counter.

    A LangGraph ``StateGraph`` would type this as a ``TypedDict``; we keep a dataclass so the same
    object serves the no-framework fallback. ``transcript`` is the single source of truth (the same
    ledger the raw loop uses); ``turns`` bounds the loop the way ``max_turns`` does there.
    """

    transcript: Transcript
    turns: int = 0
    finished: bool = False


@dataclass
class GraphNodes:
    """The two node functions every agent graph has: ``agent`` (think) and ``tools`` (act).

    Bound to a concrete model + toolset, these are the same callables whether a real LangGraph
    runtime invokes them or the fallback scheduler does. Keeping them here (not inline in the
    builder) is what lets the two paths share *identical* behaviour.
    """

    model: ModelPort
    tools: ToolRegistry
    max_turns: int = 8

    def agent_node(self, state: GraphState) -> GraphState:
        """The 'think' node: ask the model for the next turn, append it, mark done if no tools."""
        response = self.model.complete(list(state.transcript), self.tools.specs())
        msg = response.message
        state.transcript.append(msg)
        state.turns += 1
        if not msg.has_tool_calls or state.turns >= self.max_turns:
            state.finished = True
        return state

    def tools_node(self, state: GraphState) -> GraphState:
        """The 'act' node: dispatch the last assistant turn's tool calls, append results."""
        last = state.transcript.last
        for raw in last.tool_calls:
            try:
                call = repair_tool_call(id=raw.id, name=raw.name, arguments=raw.arguments)
            except MalformedToolCall as exc:
                from ..tools.messages import ToolResult

                result = ToolResult(call_id=raw.id, name=str(raw.name), content=str(exc), ok=False)
            else:
                result = self.tools.execute(call)
            state.transcript.append(tool_message(result))
        return state

    def should_continue(self, state: GraphState) -> str:
        """The conditional edge: loop back to ``agent`` while the model keeps calling tools."""
        last = state.transcript.last
        if state.finished or state.turns >= self.max_turns:
            return "end"
        return "tools" if last.role == "assistant" and last.has_tool_calls else "end"


# ---------------------------------------------------------------------------------------------
# Real LangGraph path
# ---------------------------------------------------------------------------------------------


def build_graph(nodes: GraphNodes) -> Any:
    """Compile a real LangGraph ``StateGraph`` from the shared nodes. Requires ``langgraph``.

    The graph is the canonical agent shape: ``START → agent``, a conditional edge from ``agent``
    that routes to ``tools`` (when the model called tools) or ``END`` (when it answered), and
    ``tools → agent`` to close the loop. Raises :class:`RuntimeError` if LangGraph isn't installed,
    so a caller on the live-graph path gets a clear message instead of an ``ImportError`` deep in a
    helper.
    """
    if not HAS_LANGGRAPH:  # pragma: no cover - exercised only with the extra installed
        raise RuntimeError(
            "build_graph requires the 'langgraph' package. Install the graph extra "
            "(pip install langgraph) or use GraphAgent, which falls back to a no-dependency walk."
        )
    from langgraph.graph import END, START, StateGraph  # pragma: no cover

    graph = StateGraph(GraphState)
    graph.add_node("agent", nodes.agent_node)
    graph.add_node("tools", nodes.tools_node)
    graph.add_edge(START, "agent")
    graph.add_conditional_edges("agent", nodes.should_continue, {"tools": "tools", "end": END})
    graph.add_edge("tools", "agent")
    return graph.compile()


# ---------------------------------------------------------------------------------------------
# The agent — runs on either path
# ---------------------------------------------------------------------------------------------


@dataclass
class GraphAgent:
    """The same agent as ``agents/raw``, run through a state graph.

    Construct with a model and toolset (both default to the offline mock / platform toolset). Call
    :meth:`run`; you get back the final transcript and answer. Whether a real LangGraph runtime or
    the built-in fallback drives the nodes is an implementation detail — the result is identical.
    """

    model: ModelPort = field(default=None)  # type: ignore[assignment]
    tools: ToolRegistry = field(default_factory=ToolRegistry)
    max_turns: int = 8
    prefer_framework: bool = True

    def __post_init__(self) -> None:
        if self.model is None:
            self.model = default_model()
        self._nodes = GraphNodes(model=self.model, tools=self.tools, max_turns=self.max_turns)

    def run(
        self,
        task: str,
        *,
        system_prompt: str = "You are a helpful assistant. Use tools when they help.",
    ) -> "GraphResult":
        state = GraphState(transcript=Transcript.start(system_prompt, first_user=task))
        if self.prefer_framework and HAS_LANGGRAPH:
            final = self._run_with_langgraph(state)
        else:
            final = self._run_fallback(state)
        return GraphResult(
            output=_final_text(final.transcript),
            transcript=final.transcript,
            turns=final.turns,
            used_framework=self.prefer_framework and HAS_LANGGRAPH,
        )

    def _run_with_langgraph(self, state: GraphState) -> GraphState:  # pragma: no cover
        """Drive the compiled LangGraph. Exercised only when the extra is installed."""
        compiled = build_graph(self._nodes)
        result = compiled.invoke(state)
        # LangGraph returns the final state (a GraphState here, since we typed it so).
        return result if isinstance(result, GraphState) else state

    def _run_fallback(self, state: GraphState) -> GraphState:
        """Execute the exact same graph by hand: agent → (tools → agent)* → end.

        This is a literal walk of the nodes/edges defined above, so its behaviour matches the
        LangGraph path node-for-node. It is the default offline path and what CI runs.
        """
        next_name = "agent"
        while True:
            if next_name == "agent":
                state = self._nodes.agent_node(state)
                next_name = self._nodes.should_continue(state)
            elif next_name == "tools":
                state = self._nodes.tools_node(state)
                next_name = "agent"
            else:  # "end"
                break
        return state


@dataclass(frozen=True)
class GraphResult:
    """The outcome of a graph run — mirrors ``raw``'s result surface for easy comparison."""

    output: str
    transcript: Transcript
    turns: int
    used_framework: bool

    @property
    def ok(self) -> bool:
        return bool(self.output)


def _final_text(transcript: Transcript) -> str:
    for m in reversed(transcript.messages):
        if m.role == "assistant" and not m.has_tool_calls:
            return m.text
    return ""
