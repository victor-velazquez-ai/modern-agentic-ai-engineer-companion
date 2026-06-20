# 🧭 Multi-Agent Supervisor — pattern blueprint

> Realizes book **Ch 17 — Multi-Agent Systems** · mirrors capstone `agents/` (`supervisor.py`)
> · Pattern blueprint · runs **free & offline in `MOCK=1`** (no API key, no spend)

A **supervisor that plans and delegates** to specialist workers. It decomposes a task, routes
each sub-task to the right worker, runs them sequentially or **in parallel**, isolates worker
failures, aggregates the results into one answer, and **decides when the job is done**. Each
worker is an agent-loop with a *scoped* toolset and a role.

This is the standalone reference for *"orchestrate several agents without it turning into chaos."*
The Ch 17 notebook shows the *shape*; the working orchestrator — routing policy, parallel
fan-out, result aggregation, failure isolation, loop-guard — is the real code here, asserted in
tests rather than narrated.

---

## The topology

```text
                          ┌──────────────────────────────┐
            task ───────▶ │          SUPERVISOR          │
                          │  1. plan   → sub-tasks       │
                          │  2. route  → pick a worker   │
                          │  3. run    → seq / parallel  │
                          │  5. aggregate → one answer   │
                          │  6. decide-done → why stop?  │
                          └───────┬───────────────┬──────┘
                       delegate   │   (4) isolate │   delegate
                         ┌────────▼─────┐   ┌─────▼────────┐
                         │  researcher  │   │    writer    │   ← each worker IS an agent-loop
                         │  role+tools  │   │  role+tools  │     with a SCOPED toolset
                         │  [search]    │   │  [count]     │
                         └────────┬─────┘   └─────┬────────┘
                                  │  WorkerResult  │
                                  └───────┬────────┘
                                          ▼
                                    aggregate  ──▶  final answer (+ provenance, cost, failures)
```

Numbers map to the six supervisor steps in `src/multi_agent_supervisor/supervisor.py`.

---

## Quick start

Runs offline and deterministically by default — no key, no spend.

```bash
cd blueprints/multi-agent-supervisor
python demo.py
# or give it your own task:
python demo.py "Compare RAG and fine-tuning, then write a short recommendation"

# run the tests (uses the bundled mock; never spends):
pytest tests/
```

In code:

```python
from multi_agent_supervisor import Supervisor

sup = Supervisor.from_team(mock=True)               # researcher + writer
result = sup.run("Explain vector databases and write a two-sentence summary")

print(result.reason)    # DoneReason.COMPLETED
print(result.answer)    # the aggregated final answer
print(result.report.total_tokens, result.report.failures)
```

The live path: `COMPANION_MOCK=0` plus `ANTHROPIC_API_KEY` in your environment (`.env` is
auto-loaded if `python-dotenv` is installed). Secrets come **only** from the environment.

---

## What's inside

```text
multi-agent-supervisor/
├── README.md
├── pyproject.toml                  # installable; zero runtime deps in MOCK (stdlib only)
├── demo.py                         # 2-worker team on a task, MOCK; also shows degradation
├── src/multi_agent_supervisor/
│   ├── __init__.py                 # public surface
│   ├── supervisor.py               # plan → delegate → aggregate → decide-done (+ guards)
│   ├── worker.py                   # a specialist: agent-loop + scoped toolset + role
│   ├── routing.py                  # which worker gets which sub-task (keyword + model)
│   ├── aggregate.py                # combine worker outputs into one answer (3 strategies)
│   ├── guards.py                   # iteration/depth caps + worker-failure isolation
│   └── model.py                    # the model port (MOCK default; live + gateway seam)
└── tests/
    ├── test_routing.py             # sub-task → correct specialist
    ├── test_parallel.py            # independent sub-tasks fan out and rejoin
    └── test_failure.py             # one worker fails → supervisor degrades, doesn't crash
```

---

## Design trade-offs (the part worth reading)

### When multi-agent beats a single loop
A single agent-loop is the right default — it's cheaper, simpler, and easier to debug. Reach for
a supervisor only when the task has **distinct sub-skills** (research vs. writing vs. coding),
each wanting its **own scoped tools and prompt**, and the sub-tasks are **separable**. The win is
specialization + parallelism + capability confinement; the cost is more model calls and
coordination surface. If your "team" is one worker doing everything, delete the supervisor.

### Routing policy — keyword vs. model
`routing.py` ships two policies behind one interface:

- **`KeywordRouter` (default)** — deterministic capability-tag matching. Free, offline, and its
  decisions are *assertable* in tests. Two-stage: exact capability match, then a token scan
  fallback. Use it whenever you can describe "which worker" with tags.
- **`ModelRouter`** — asks the model to pick (the `llm-gateway` planning call). More flexible for
  fuzzy tasks, but costs a call and can hallucinate a worker — so it **validates the pick against
  the real roster and falls back to the keyword router**. Never route on an unvalidated string.

### Parallel vs. sequential
The supervisor runs in **dependency waves**: within a wave, independent sub-tasks fan out across a
thread pool and **rejoin in submission order**; a sub-task with `depends_on` waits for its inputs
(the writer always runs after the researchers). Parallelism cuts wall-clock time for independent
work; it adds nothing for a strict pipeline and costs you ordering/Heisenbug risk if your workers
share mutable state — so workers here are isolated and return values, not side effects. Thread
pool (not async) keeps the control flow readable and the blocking model calls simple.

### Aggregation strategy
`aggregate.py` offers three, because the right fold depends on how work is shaped:

| Strategy | Use when | Cost |
|---|---|---|
| `concat_aggregate` | each worker owns a *distinct section* | free, lossless |
| `last_writer_aggregate` *(default)* | later workers *consume* earlier ones (research→write) | free |
| `ModelAggregate` | outputs overlap and need real synthesis | one model call |

All three skip failed workers, so a partial team still yields a usable answer.

### The recursion / iteration guard
Two caps in `guards.py` keep a run finite and legible:
- **`IterationGuard`** bounds orchestration rounds — a runaway planner halts loudly instead of
  billing forever (the supervisor reports `DoneReason.GUARD_TRIPPED`).
- **`DepthGuard`** bounds delegation recursion (supervisor-of-supervisors), so sub-teams can't
  spawn without bound.

### Failure isolation
`run_isolated` turns a crashing worker into a **recorded `Outcome`, not an exception in flight**.
The supervisor inspects `ok` across all workers and **degrades** (`DoneReason.DEGRADED`) — it
still aggregates the survivors and answers. An unroutable sub-task degrades the same uniform way.
"How does the supervisor decide it's finished, and what happens when a worker fails?" is answered
in `_decide_reason` and proven in `tests/test_failure.py`.

---

## How it composes (the seams)

This pattern is designed to **compose two sibling blueprints**. They are planned siblings; until
they ship, this blueprint carries faithful local stand-ins so it is fully runnable and tested
today, behind the same interfaces a real implementation satisfies:

- **[`../agent-loop`](../agent-loop/PLAN.md)** *(hard dependency)* — each `Worker` *is* an agent
  loop. `Worker.run` is the seam: drop in `agent_loop.AgentLoop(model, tools=self.tools)` and the
  supervisor surface (`Worker.handle`) is unchanged.
- **[`../llm-gateway`](../llm-gateway/PLAN.md)** — the supervisor's planning/routing/synthesis
  calls go through the model port. Any `llm-gateway` client satisfies
  `model.ModelPort`, so you build it in `model.build_model()` and get routing, caching, metering,
  and guards for free. (The mock keeps this blueprint standalone.)
- Optionally reads/writes **[`../memory-module`](../memory-module/PLAN.md)** for shared team state.

Solution blueprints compose *this* one — e.g.
[`../research-due-diligence-agent`](../research-due-diligence-agent/) and
[`../software-engineering-agent`](../software-engineering-agent/) are supervisor + workers tuned
for a job. That's why the coordination semantics here are tested, not narrated.

---

## Maps to the book & capstone

- **Ch 17 — Multi-Agent Systems:** supervisor/worker topology, delegation, parallelism,
  aggregation, and coordination failure modes. Makes §17's 🔧 Build sections real.
- **`learn/` walkthrough:**
  [`../../learn/part-05-architectures-and-orchestration/17-multi-agent-systems/`](../../learn/part-05-architectures-and-orchestration/17-multi-agent-systems/)
  builds a supervisor/workers team in isolation and **ends by pointing here**.
- **Capstone:** the standalone version of `agents/` — specifically `supervisor.py` (Ch 17) plus
  the worker agents that reuse `agents/raw/`. This blueprint is that orchestration, isolated.

---

## Adapt it to your system

1. **Add a worker** — `Worker(name=..., role=..., model=model, capabilities=frozenset({...}),
   tools={...})`. Keep its toolset *scoped*: capability confinement is a safety property.
2. **Change the plan** — pass your own `planner` to `Supervisor(...)`; emit `SubTask`s with
   `depends_on` to control sequencing and parallelism.
3. **Swap the router/aggregator** — inject `ModelRouter` or `ModelAggregate` for richer behavior;
   both stay MOCK-safe.
4. **Tune the guards** — set `IterationGuard(max_iterations=...)` / `DepthGuard(max_depth=...)` to
   your latency and cost budget.
5. **Go live** — set `COMPANION_MOCK=0`, export `ANTHROPIC_API_KEY`, or inject a real
   `llm-gateway` client in `build_model`.
