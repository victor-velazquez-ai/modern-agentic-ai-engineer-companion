# `agents/pydantic_ai/` — the Pydantic AI variant (Ch 18)

The third of the "one agent, three ways" builds. Where [`raw`](../raw/) is a hand-written loop and
[`graph`](../graph/) is a state graph, Pydantic AI gives you a typed **agent object**: tools are
decorated functions (schema inferred from type hints), the result is an optional validated type, and
the framework owns the loop. The trade-off this build surfaces: the least code and the strongest
typing, in exchange for the most framework magic between you and the control flow.

## MOCK-runnable: framework optional

`pydantic-ai` is an optional dependency. This package runs **with or without it**:

- **With `pydantic_ai`** — `PydanticAgent` builds a real `Agent`, registers the platform tools, and
  runs it against the injected model.
- **Without it** (the default offline path and CI) — `PydanticAgent` drives the *same tools and the
  same model port* through a minimal typed loop with identical semantics.

`PydanticAgent.tool(...)` mirrors the framework's `@agent.tool` decorator, so reader code written
against this object ports to the real framework with minimal change.

## Surface

```python
from agents.pydantic_ai import PydanticAgent
agent = PydanticAgent(model=..., tools=...)   # defaults: offline mock + platform toolset
result = agent.run("...")                     # AgentRunResult(.data/.output, .transcript, .turns, .used_framework)
```

`AgentRunResult.output` aliases `.data` so the result lines up with `raw` and `graph` for
side-by-side comparison — the Ch 18 exercise. `HAS_PYDANTIC_AI` reports which path ran.
