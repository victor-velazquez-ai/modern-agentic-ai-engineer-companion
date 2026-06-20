# Blueprint — Multi-Agent Supervisor  (pattern)

> Realizes book Ch 17 · mirrors capstone `agents/` (`supervisor.py`) · Status: 📋 planned (Phase 1)

## What it is
A **supervisor that plans and delegates** to specialist workers: it decomposes a task, routes
sub-tasks to the right worker, runs them (sequentially or in parallel), aggregates results, and
decides when the job is done. Each worker is an `agent-loop` with a scoped toolset. The standalone
reference for "orchestrating several agents without it turning into chaos."

## Why a blueprint (not a notebook)
- The Ch 17 notebook shows the *shape* of supervisor/worker; the working orchestrator — routing
  policy, parallel fan-out, result aggregation, failure isolation, loop-guard — is real code.
- Solution blueprints (research/due-diligence, software-engineering agents) **compose** it, so it
  needs a stable surface and tested coordination semantics.
- "How does the supervisor decide it's finished, and what happens when a worker fails?" is a
  behavior you assert in tests, not narrate.

## Planned structure
```text
multi-agent-supervisor/
├── README.md                  # supervisor/worker diagram, routing/aggregation trade-offs, adapt
├── pyproject.toml
├── src/multi_agent_supervisor/
│   ├── __init__.py
│   ├── supervisor.py          #   plan → delegate → aggregate → decide-done
│   ├── worker.py              #   a specialist: an agent-loop + a scoped toolset + a role
│   ├── routing.py             #   which worker gets which sub-task
│   ├── aggregate.py           #   combine worker outputs into one answer
│   └── guards.py              #   recursion/iteration caps, worker-failure isolation
├── tests/
│   ├── test_routing.py        #   sub-task → correct specialist
│   ├── test_parallel.py       #   independent sub-tasks fan out and rejoin
│   └── test_failure.py        #   one worker fails → supervisor degrades, doesn't crash
└── demo.py                    # runnable: a 2-worker team (researcher + writer) on a task, MOCK
```

## Composes / depends on
- **`agent-loop`** — each worker *is* an agent loop (hard dependency).
- **`llm-gateway`** — the supervisor's planning/routing calls (mock keeps it standalone).
- Optionally reads/writes **`memory-module`** for shared team state.

## Maps to the book
- **Ch 17 — Multi-Agent Systems:** supervisor/worker topology, delegation, parallelism,
  aggregation, coordination failure modes. Makes §17's 🔧 Build sections real.
- **`learn/` walkthrough:** [`../../learn/part-05-architectures-and-orchestration/17-multi-agent-systems/`](../../learn/part-05-architectures-and-orchestration/17-multi-agent-systems/)
  builds a supervisor/workers team in isolation and **ends by pointing here**.

## Maps to the capstone
Standalone version of capstone **`agents/`** — specifically `supervisor.py` (Ch 17) plus the
worker agents that reuse `agents/raw/`. This blueprint is that orchestration, isolated.

## Phase-2 definition of done
- [ ] `pytest tests/` passes; routing, parallel fan-out/rejoin, and worker-failure isolation covered.
- [ ] `python demo.py` runs a 2-worker team to a finished answer in **`MOCK=1`** (no API spend).
- [ ] README explains trade-offs: when multi-agent beats a single loop, routing policy, parallel
      vs. sequential, aggregation strategy, and the recursion/iteration guard.
- [ ] Cross-links (`agent-loop`, `llm-gateway`, `memory-module`, the Ch 17 walkthrough, capstone
      `agents/`) resolve.
