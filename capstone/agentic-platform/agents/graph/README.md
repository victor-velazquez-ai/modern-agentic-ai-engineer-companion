# `agents/graph/` — the LangGraph variant (Ch 18)

The same agent as [`agents/raw`](../raw/), expressed as an explicit **state graph** instead of a
`while` loop. Two nodes (`agent` = think, `tools` = act) and a conditional edge that loops back to
`agent` while the model keeps calling tools. The graph makes control flow a *declared object*,
which is what buys checkpointing, streaming, and visualization — at the cost of a dependency and a
layer of indirection over the plain loop. That trade-off is the Ch 18 lesson.

## MOCK-runnable: framework optional

`langgraph` is an optional dependency. This package runs **with or without it**:

- **With `langgraph`** — `build_graph(nodes)` compiles a real `StateGraph` (`START → agent`,
  conditional edge to `tools`/`END`, `tools → agent`); `GraphAgent` invokes it.
- **Without it** (the default offline path and CI) — `GraphAgent` executes the *same* nodes and
  edges via a tiny built-in scheduler. Identical semantics, zero dependency.

The state (`GraphState`), the node functions (`GraphNodes.agent_node` / `tools_node`), and the
routing predicate (`should_continue`) are framework-agnostic and shared by both paths — which is
itself the insight: the agent is the nodes and edges, not the runner.

## Surface

```python
from agents.graph import GraphAgent
agent = GraphAgent(model=..., tools=...)     # defaults: offline mock + platform toolset
result = agent.run("...")                    # GraphResult(.output, .transcript, .turns, .used_framework)
```

`GraphResult` mirrors the `raw` and `pydantic_ai` result surfaces so the three builds compare
directly. `HAS_LANGGRAPH` tells you which path ran; `prefer_framework=False` forces the fallback
even when the package is installed (handy for deterministic tests).
