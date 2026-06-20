# 🔭 observability-stack — tracing + cost accounting for agent runs

> **Pattern blueprint** · realizes book **Ch 23 — Observability for Agents** · mirrors capstone
> [`observability/`](../../capstone/) · runs **free & offline in `MOCK=1`**

You shipped an agent. It answered three questions, called two tools, did a retrieval, and cost
some money. **What actually happened, and what did it cost?** This blueprint answers that. It
wraps an agent run in spans so the run becomes a readable **trace tree**, attaches **token usage
and cost** to the model-call spans, and **rolls the cost up** so the root span carries the total
for the whole run. Export it to your console (default) or to a real backend (OTLP / Phoenix /
Langfuse).

It is **instrumentation you wrap around other code**, which is exactly why it's a package and not
a notebook: its value is the helpers, decorators, and span conventions — and the cost roll-up is a
tested calculation, not a snippet.

```text
run support-agent
|- [llm] plan    claude-sonnet-4 (1200->300 tok)  $0.008100
|- [tool] search_docs
|  `- [ret] retrieval
`- [llm] answer  claude-haiku-4 (2000->450 tok)   $0.003400

run demo-0001 · 5 spans · $0.011500 total
```

---

## Quickstart

```bash
cd blueprints/observability-stack
python demo.py          # MOCK=1 by default: offline, deterministic, no API spend
pytest tests/           # span nesting, cost roll-up, console exporter
```

`demo.py` traces a scripted support-agent run (plan → retrieve → tool → answer) and prints the
tree plus a cost/token summary. Nothing here reads a key or touches the network.

```python
from observability_stack import Tracer, ConsoleExporter

tracer = Tracer()
with tracer.run("support-agent"):
    with tracer.model_span("plan", model="claude-sonnet-4",
                           input_tokens=1200, output_tokens=300):
        ...                      # your model call
    with tracer.tool_span("search_docs"):
        with tracer.retrieval_span(query="refund policy", k=4):
            ...                  # your retrieval
    with tracer.model_span("answer", model="claude-haiku-4",
                           input_tokens=2000, output_tokens=450):
        ...

ConsoleExporter().export(tracer.trace)   # prints the tree + total cost
```

Prefer decorators? `@traced(kind=SpanKind.TOOL)` wraps any function call in a span on the default
tracer.

---

## What's inside

| Module | Responsibility |
|---|---|
| [`tracing.py`](src/observability_stack/tracing.py) | The `Tracer`, the `Span` tree, the `run` / `model_span` / `tool_span` / `retrieval_span` context managers, and the `@traced` decorator. Tracks the active span with `contextvars`, so nesting follows your call stack. **stdlib only.** |
| [`attributes.py`](src/observability_stack/attributes.py) | The span-attribute **conventions** — run id, model, token counts, cost, tool/retrieval/error keys — as constants every producer agrees on. Borrows OTel semantic-convention key shapes. |
| [`cost.py`](src/observability_stack/cost.py) | Token → USD pricing table + `token_cost()`, and `roll_up_cost()` which sums descendant model-call costs into every ancestor span (root roll-up = run total). `summarize()` gives a per-model breakdown. |
| [`exporters.py`](src/observability_stack/exporters.py) | `ConsoleExporter` (default, stdlib) renders the tree + cost; `JSONExporter` for snapshots; `OTLPExporter` / `PhoenixExporter` / `LangfuseExporter` bridge to real backends with a **lazy** OTel import. |

### Span kinds

`run` (the trace root) · `llm` (a model call, priced) · `tool` (a tool/function call) ·
`retrieval` (a vector search / lookup) · `chain` (a grouping step). Costs only attach to `llm`
spans; every other span gets a **subtree roll-up** so you can ask "what did the retrieval phase
cost?", not just "what did the run cost?".

---

## Why no hard OpenTelemetry dependency?

The book's stack is OTel-shaped, and the optional exporters *do* bridge to a real OTel SDK. But
the **core is stdlib-only on purpose**:

- it must run **free and offline in `MOCK=1`** with only `requirements.txt` + stdlib — and
  `opentelemetry-sdk` may not even be installed where you're reading;
- the *concepts* — a span tree, parent/child links, attributes, timing, status, a cost roll-up —
  are the thing to learn; OTel is one serialization of them;
- a self-contained tree is trivially testable (assert on structure, not on a global provider).

The OTel imports live **inside** the exporter methods, so importing the package, running the demo,
and running the tests never require the optional dependency. Install it only to ship to a live
backend: `pip install -e ".[otel]"`.

---

## Trade-offs a senior weighs

- **Span granularity vs. overhead.** Span-per-tool-call and span-per-model-call is the sweet spot:
  enough to debug and cost a run, cheap enough to leave on. Going finer (span-per-token, span-per-
  loop-iteration) buys little and clutters the tree; going coarser (one span per run) loses the
  "what cost what" attribution that makes this worth having. Start at the kinds here.
- **Attribute conventions over cleverness.** The value of a trace is only as good as its
  attributes, and only if **every** producer names them the same way. That's why the keys live in
  `attributes.py` as shared constants (run id, `gen_ai.*` usage, `agent.cost.*`) — so a dashboard,
  the roll-up, or a CI assertion reads any trace without special-casing who emitted it.
- **Sampling lives at the exporter boundary.** While learning or in CI, export every trace. In
  production, sample (head- or tail-based) to control cost and volume — you change the *exporter*,
  not the instrumentation. The console/JSON exporters here export everything by design.
- **Choosing & swapping an exporter.** The console exporter is for humans and CI — no collector,
  no network. A real backend (OTLP collector, Arize Phoenix, Langfuse) adds search, retention, and
  dashboards at the cost of a dependency and a running collector. `get_exporter("phoenix")` (or
  `"otlp"` / `"langfuse"`) swaps targets without touching a line of instrumentation; point it with
  `OTEL_EXPORTER_OTLP_ENDPOINT` (see `.env.example`).
- **Cost numbers are only as fresh as the table.** `cost.PRICES` is an *illustrative* default;
  update it from the provider's pricing page before trusting a bill. Unknown models price at `$0`
  and are **flagged** (`unknown_models()`, and a `! unpriced models` line in the console output) so
  a new model never silently costs nothing.

---

## How it composes (cross-cutting, not dependent)

This stack **instruments** other blueprints rather than depending on them — integration is via
decorators/context, so it stays importable on its own:

- [`agent-loop`](../agent-loop/PLAN.md) — wrap the loop in a `run` span and each tool/model call in
  child spans to see the `observe → decide → act` cycle as a tree.
- [`llm-gateway`](../llm-gateway/PLAN.md) — **complementary**: the gateway's metering layer *counts*
  tokens/cost; this stack *attributes* them to spans and *visualizes* the run. Feed
  `record_usage(...)` (or `model_span(...)`) from the gateway's usage object.
- [`rag-pipeline`](../rag-pipeline/PLAN.md) — emit a `retrieval` span per lookup (query, `k`, hits).
- [`multi-agent-supervisor`](../multi-agent-supervisor/PLAN.md) — each worker run nests under the
  supervisor's `run` span, so a delegated run is one tree.

---

## How to adapt it

1. **Read usage from your gateway, not canned numbers.** In `demo.py` the token counts are mocked;
   in real code, pass the gateway response's input/output tokens into `model_span(...)` /
   `record_usage(...)`.
2. **Keep the attribute keys.** If you add attributes, namespace them and add the constant to
   `attributes.py` so every producer and consumer agrees.
3. **Pick an exporter per environment.** `console` for CI and local; `otlp`/`phoenix`/`langfuse`
   (with `[otel]` installed and an endpoint set) for staging/prod. Add sampling at that boundary.
4. **Update `cost.PRICES`** when you adopt a new model, and watch the `unpriced models` flag.

---

## Maps to the book & capstone

- **Ch 23 — Observability for Agents:** tracing agent runs with OTel, span design for tool/model
  calls, cost and token accounting, dashboards/exporters. This makes §23's 🔧 Build sections real.
- **`learn/` walkthrough:**
  [`../../learn/part-06-evaluation-observability-quality/23-observability-for-agents/`](../../learn/part-06-evaluation-observability-quality/23-observability-for-agents/)
  traces an agent run with OTel in isolation and **ends by pointing here**.
- **Capstone:** the standalone version of the capstone
  [`observability/`](../../capstone/) — the OTel setup, dashboards, and alerts the capstone uses to
  trace and cost every agent run.

---

## Definition of done (Phase 2)

- [x] `pytest tests/` passes; span nesting, cost roll-up, and the console exporter are covered.
- [x] `python demo.py` traces a mock agent run and prints the span tree + total cost in **`MOCK=1`**
      (console exporter, no external collector, no API spend).
- [x] README explains the trade-offs: span granularity vs. overhead, attribute conventions,
      sampling, and choosing/swapping an exporter.
- [x] Cross-links (`agent-loop`, `llm-gateway`, the Ch 23 walkthrough, capstone `observability/`)
      resolve.
