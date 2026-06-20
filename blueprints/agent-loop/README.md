# Blueprint — Agent Loop

> **Pattern blueprint.** Realizes book **Ch 12** (Tool Use & Function Calling) and **Ch 16**
> (Agent Reasoning Patterns). Mirrors capstone [`agents/raw/`](../../capstone). Runs **free and
> offline in `MOCK=1`** (the default) — no key, no spend.

A framework-free, tool-using **agent loop** you can read top to bottom: the
`observe → decide → act → observe` cycle implemented directly against a model port, with **no
orchestration library hiding the control flow**. It owns the message ledger, the tool-call
dispatch, the stop conditions, and the failure handling that every higher-level agent reuses.

This is the **hardened** version of the toy loop the
[Ch 12 walkthrough](../../learn/part-04-building-blocks-of-agents/12-tool-use-and-function-calling/)
builds — the one a senior would actually ship, and the one four later chapters (20/25/46/47)
build on.

---

## The loop

```text
                 ┌───────────────────────────────────────────────┐
   task ─────────▶  Transcript  (system · user · assistant · tool) │  ◀── the only mutable state
                 └───────────────────────────────────────────────┘
                                  │
                                  ▼
          ┌────────────── DECIDE ──────────────┐     ask the model for the next
          │  model.complete(transcript, tools) │     assistant turn (text and/or tool calls)
          └────────────────────────────────────┘
                                  │
                     has tool calls?  ──── no ──▶  STOP: COMPLETED  (the text is the answer)
                                  │ yes
                                  ▼
          ┌─────────────── ACT ────────────────┐     repair malformed calls, then dispatch
          │  repair → ToolRegistry.execute_all │     every call; isolate each failure
          └────────────────────────────────────┘
                                  │
                                  ▼
          ┌───────────── OBSERVE ──────────────┐     append each ToolResult as a `tool` turn
          │  transcript.append(tool results)   │     and loop
          └────────────────────────────────────┘
                                  │
              guards each iteration: turn cap · recovery policy · cancel
```

Every terminal path names itself with a `StopReason` — `COMPLETED`, `MAX_TURNS`,
`RECOVERY_EXHAUSTED`, or `CANCELLED` — so a run is never a mystery.

---

## Run it

```bash
cd blueprints/agent-loop
python demo.py            # MOCK=1 by default: free, offline, deterministic

# tests (no install needed — tests put src/ on the path):
pip install pytest        # already pinned in the repo-root requirements.txt
pytest tests/

# or install the package and use it elsewhere:
pip install -e .
```

`demo.py` wires two real tools (a safe `calculator` and a `clock`) into the loop and prints the
cycle as it resolves a multi-tool turn — with zero API spend.

---

## Use it

```python
from agent_loop import AgentLoop, ToolRegistry, tool, MockModel, assistant, ToolCall

@tool("add", "Add two integers.",
      {"type": "object",
       "properties": {"a": {"type": "integer"}, "b": {"type": "integer"}},
       "required": ["a", "b"]})
def add(a: int, b: int) -> int:
    return a + b

# A scripted mock model (default path): call the tool, then answer from its result.
model = MockModel([
    assistant(tool_calls=(ToolCall(id="1", name="add", arguments={"a": 2, "b": 3}),)),
    lambda transcript: assistant(text=f"The sum is {transcript[-1].text}."),
])

loop = AgentLoop(model=model, tools=ToolRegistry([add]), max_turns=8)
result = loop.run("what is 2 + 3?")

print(result.output)        # 'The sum is 5.'
print(result.stop_reason)   # StopReason.COMPLETED
print(result.transcript)    # the full ledger — your trace / replay input
```

`AgentLoop()` with **no arguments** uses the offline mock and runs free.

---

## Module map

| File | Responsibility |
|---|---|
| [`messages.py`](src/agent_loop/messages.py) | The typed, append-only **ledger** (`Transcript`) and turn types (`Message`, `ToolCall`, `ToolResult`). |
| [`model.py`](src/agent_loop/model.py) | The **model port** (`ModelPort` Protocol) and the scriptable, offline `MockModel`. The injection seam. |
| [`tools.py`](src/agent_loop/tools.py) | The `Tool` schema + safe **dispatch** (`ToolRegistry`): unknown-tool / bad-arg / tool-raised all become readable results, never crashes. |
| [`errors.py`](src/agent_loop/errors.py) | **Malformed-call repair** (stringified JSON, code fences) and the `RetryPolicy`. Pure, unit-tested. |
| [`loop.py`](src/agent_loop/loop.py) | The **core loop** (`AgentLoop`): the cycle plus the turn cap, recovery wiring, and cancellation. |

---

## Trade-offs (the senior lens)

### When the raw loop beats a framework
Reach for *this* — not LangGraph / a framework — when you need to **see and own the control
flow**: when the failure modes are yours to debug, when you're teaching the mechanism, when the
agent is small enough that a graph engine is more concept-tax than leverage, or when you must
embed the loop somewhere a heavyweight runtime won't fit. Reach for a **framework** once you need
durable state across processes, a visual graph of many nodes, checkpoint/resume across restarts,
or a team-standard substrate. The two aren't enemies: a framework *is* a loop like this with more
machinery — knowing the loop is what lets you debug the framework.

### Turn-cap tuning (`max_turns`)
The single most important safety bound: it's what stops a confused model from looping forever.
Set it to the **longest legitimate plan** your task needs, plus a small margin — then watch how
often real runs approach it. Too low silently truncates good work (you'll see `MAX_TURNS` on
tasks that were *almost* done); too high lets a stuck model burn tokens. It is a per-task knob,
not a global constant; a research agent and a "format this string" agent want very different caps.

### Tool-error-recovery policy
A failed tool call is **not** an exception here — it's a `ToolResult(ok=False)` threaded back to
the model so it can *read its mistake and retry*. That's the cheapest, most robust recovery
there is (the model is already good at fixing a call it can see is wrong). The `RetryPolicy`
bounds the flailing: after *N* **consecutive** all-failing turns the loop stops with
`RECOVERY_EXHAUSTED`, and the counter resets the moment a turn makes progress — so a single
hiccup costs nothing, but a model stuck on the same broken call can't drain the whole budget.
Malformed JSON arguments are *repaired where safe* (a JSON string, code fences) before they ever
reach a tool; only the truly unrepairable becomes an error the model is asked to fix.

### Parallel tool calls
One assistant turn may request several tools; `execute_all` runs them **in emission order**, each
failure isolated, which keeps a run deterministic and replayable by default. When calls are
independent and slow (two network tools), you can run them concurrently — swap `execute_all` for
a thread/async fan-out — at the cost of nondeterministic interleaving in your traces. Default to
order; opt into concurrency where latency demands it.

### The `model.py` injection seam
The loop never imports an SDK; it depends only on the `ModelPort` Protocol. The mock satisfies it
for free/offline runs, and a **real model drops in as one constructor argument** — no loop change.
That seam is why this package is importable by `multi-agent-supervisor` (its workers are agent
loops), the solution blueprints, and the capstone.

---

## The live path (`MOCK=0`)

This blueprint ships **only the mock model**, so it runs standalone with zero keys. For real
calls, inject a port backed by the [`llm-gateway`](../llm-gateway/) blueprint (Anthropic-first):

```python
from agent_loop import AgentLoop, ModelPort
# from llm_gateway import GatewayModelPort   # once llm-gateway is built

class GatewayModelPort:                       # satisfies ModelPort structurally
    def complete(self, transcript, tools): ...

loop = AgentLoop(model=GatewayModelPort(), tools=my_tools)
```

`default_model()` reads `COMPANION_MOCK` (default `"1"`). Under `MOCK=0` with no port wired in it
**fails loud** rather than silently spending — secrets come only from the environment
([`.env`](../../.env.example)), never the code.

---

## Where this sits

- **Book — Ch 12 (Tool Use & Function Calling):** the tool schema, the call/result protocol, the
  loop. Makes §12's 🔧 *Build* sections real.
- **Book — Ch 16 (Agent Reasoning Patterns):** ReAct / plan-execute / reflection are *strategies
  layered on this loop* — this blueprint is the substrate those patterns drive.
- **Walkthrough:** [`learn/.../12-tool-use-and-function-calling/`](../../learn/part-04-building-blocks-of-agents/12-tool-use-and-function-calling/)
  builds the toy loop and ends by pointing here.
- **Composes:** the model port comes from [`llm-gateway`](../llm-gateway/) (injected; mock by
  default). Otherwise foundational — most other blueprints build on this one.
- **Capstone:** the standalone version of [`agents/raw/`](../../capstone) — the no-framework loop,
  isolated. The capstone wires the same core to real tools and the gateway.

See [`PLAN.md`](PLAN.md) for the Phase-2 definition of done.
