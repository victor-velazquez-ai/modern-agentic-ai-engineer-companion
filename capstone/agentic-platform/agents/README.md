# `agents/` — the platform's reasoning engines

This is the capstone's agent subsystem: the framework-free loop everything grows around, three
interchangeable framework variants over one toolset, a multi-agent supervisor that owns the goal
and budget, and the human-in-the-loop approval gate that fronts risky tools. It is the *assembled*
counterpart to two blueprints — [`agent-loop`](../../../blueprints/agent-loop/) (the loop in
isolation) and [`multi-agent-supervisor`](../../../blueprints/multi-agent-supervisor/) (the
orchestration in isolation). Build your own from the chapters' 🔧 Build sections first; read this
to compare. See the capstone [README](../../README.md) for that discipline.

## Layout (matches Appendix C)

| Path | What it is | Chapter |
|---|---|---|
| [`tools/`](tools/) | Tool schemas + **risk tiers** + safe executors; the typed ledger, model port, dispatch registry | 12, 19, 20 |
| [`raw/`](raw/) | The **no-framework** loop: observe → decide → gate → act → observe | 12, 20 |
| [`graph/`](graph/) | The **LangGraph** variant — the same agent as a state graph | 18 |
| [`pydantic_ai/`](pydantic_ai/) | The **Pydantic AI** variant — the same agent as a typed agent object | 18 |
| `supervisor.py` | The **multi-agent supervisor**: plan → delegate → aggregate → decide-done | 17 |
| `approvals.py` | The **approval gate**: risk-tier table → pause → resume (human-in-the-loop) | 20 |

## The two ideas to take away

1. **One substrate, many runners.** `tools/` owns the model port, the typed transcript, the tool
   registry, and the safe executors. `raw/`, `graph/`, and `pydantic_ai/` are three *runners* over
   that one substrate — and they produce the same answer. The agent is the tools + state, not the
   framework (Ch 18). The supervisor is a fourth consumer: each worker is a confined `raw` loop.

2. **Risk is structural, not a prompt.** Every tool declares a `RiskTier` (`READ` / `WRITE` /
   `EXTERNAL` / `ADMIN`) next to its schema. The `ApprovalGate` reads that tier and decides
   *allow / hold / deny* before a call runs. A held call pauses the run (the transcript is
   snapshot-able), surfaces an approval request to the API/UI, and resumes when a human decides.
   "Prompts ask; structure enforces" (Ch 20).

## Run it offline (no keys, no spend)

Everything defaults to `COMPANION_MOCK=1`: a deterministic offline model, identical every run.

```python
from agents.raw import AgentLoop
from agents.tools import default_toolset, MockModel, assistant, ToolCall

model = MockModel([
    assistant(tool_calls=(ToolCall(id="1", name="calculator", arguments={"expression": "2+3"}),)),
    lambda t: assistant(text=f"The answer is {t[-1].text}."),
])
print(AgentLoop(model=model, tools=default_toolset()).run("what is 2 + 3?").output)
# -> "The answer is 5."
```

The same `MockModel` script drives `agents.graph.GraphAgent` and `agents.pydantic_ai.PydanticAgent`
to the same result — that side-by-side is the Ch 18 exercise.

### Approval gate in one snippet

```python
from agents.raw import AgentLoop, StopReason
from agents.approvals import ApprovalGate, ApprovalPolicy, ApprovalResolution
from agents.tools import default_toolset, MockModel, assistant, ToolCall

tools = default_toolset()
gate = ApprovalGate(policy=ApprovalPolicy(), tools=tools)   # gate EXTERNAL+ by default
model = MockModel([
    assistant(tool_calls=(ToolCall(id="1", name="send_email",
              arguments={"to": "x@y.co", "subject": "hi", "body": "..."}),)),
    lambda t: assistant(text="Email handled."),
])
loop = AgentLoop(model=model, tools=tools, approval_gate=gate)
held = loop.run("email the customer")
assert held.stop_reason is StopReason.NEEDS_APPROVAL      # paused for a human
done = loop.resume_with_approval(held, ApprovalResolution(held.pending_approval.id, approved=True))
print(done.output)                                         # -> "Email handled."
```

## The live path

The only seam to a real model is `agents.tools.model.ModelPort`. Set `COMPANION_MOCK=0` and inject
the platform's `llm/gateway.py` client (it satisfies the protocol structurally). Secrets —
`ANTHROPIC_API_KEY` — are read from the environment only; nothing here hard-codes a key.

## Optional framework extras

`graph/` and `pydantic_ai/` import their frameworks *lazily* and fall back to a no-dependency runner
with identical semantics, so the whole subsystem `py_compile`s and runs with **only the standard
library**. Install `langgraph` / `pydantic-ai` to exercise the real-framework paths.
