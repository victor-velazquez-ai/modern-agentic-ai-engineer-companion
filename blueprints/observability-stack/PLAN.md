# Blueprint — Observability Stack  (pattern)

> Realizes book Ch 23 · mirrors capstone `observability/` · Status: 📋 planned (Phase 1)

## What it is
**OpenTelemetry tracing for agent runs**, plus **cost/token accounting**. Spans wrap the agent
loop, each tool call, each model call, and each retrieval — so one agent run becomes a readable
trace tree — with token usage and cost attached as span attributes and rolled up per run. An
exporter targets a local collector by default (Phoenix/Langfuse/OTLP as options). The standalone
"so you can actually see what your agent did and what it cost."

## Why a blueprint (not a notebook)
- Tracing is **instrumentation you wrap around other code**; its value is the helpers/decorators
  and span conventions, which only exist as an importable package — a notebook can render one
  trace but can't be the library.
- `agent-loop`, `rag-pipeline`, and the supervisor are instrumented *by* this, and solution
  blueprints reuse it for run visibility, so it needs a stable surface.
- Cost roll-up per run is a tested calculation (sum child model-call costs into the root span),
  not a snippet.

## Planned structure
```text
observability-stack/
├── README.md                  # the trace tree, span conventions, cost roll-up, exporters, adapt
├── pyproject.toml
├── src/observability_stack/
│   ├── __init__.py
│   ├── tracing.py             #   OTel setup; @traced helpers for loop/tool/model/retrieval spans
│   ├── attributes.py          #   span attribute conventions (run id, model, tokens, cost)
│   ├── cost.py                #   token→cost accounting + per-run roll-up
│   └── exporters.py           #   console (default) + OTLP/Phoenix/Langfuse options
├── tests/
│   ├── test_tracing.py        #   spans nest correctly into a run tree
│   ├── test_cost.py           #   child model-call costs roll up to the root span
│   └── test_exporters.py      #   console exporter emits a complete, well-formed trace
└── demo.py                    # runnable: trace a mock agent run, print the tree + cost, MOCK
```

## Composes / depends on
- **Cross-cutting / foundational** — it *instruments* `agent-loop`, `rag-pipeline`,
  `multi-agent-supervisor`, and `llm-gateway` rather than depending on them; integration is via
  decorators/context, so it stays importable on its own.
- Reads token/cost data that the **`llm-gateway`** metering layer produces (complementary: the
  gateway counts, this stack attributes and visualizes).

## Maps to the book
- **Ch 23 — Observability for Agents:** tracing agent runs with OTel, span design for tools/model
  calls, cost and token accounting, dashboards/exporters. Makes §23's 🔧 Build sections real.
- **`learn/` walkthrough:** [`../../learn/part-06-evaluation-observability-quality/23-observability-for-agents/`](../../learn/part-06-evaluation-observability-quality/23-observability-for-agents/)
  traces an agent run with OTel in isolation and **ends by pointing here**.

## Maps to the capstone
Standalone version of capstone **`observability/`** — the OTel setup, dashboards, and alerts
(Ch 23) the capstone uses to trace and cost every agent run.

## Phase-2 definition of done
- [ ] `pytest tests/` passes; span nesting, cost roll-up, and the console exporter covered.
- [ ] `python demo.py` traces a mock agent run and prints the span tree + total cost in
      **`MOCK=1`** (console exporter, no external collector, no API spend).
- [ ] README explains trade-offs: span granularity vs. overhead, attribute conventions, sampling,
      and choosing/swapping an exporter.
- [ ] Cross-links (`agent-loop`, `llm-gateway`, the Ch 23 walkthrough, capstone `observability/`)
      resolve.
