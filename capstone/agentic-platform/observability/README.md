# `observability/` — OTel tracing + cost accounting

> Capstone subsystem · Appendix C `observability/` · built in **Ch 23** · mirrors the
> [`observability-stack`](../../../blueprints/observability-stack/) blueprint.

The platform's nervous system. One agent run becomes a tree of spans (a RUN root with LLM /
TOOL / RETRIEVAL / CHAIN children); each model-call span carries token usage; the cost layer
rolls that up into per-span and per-run dollars; an exporter ships the tree to the console
(default), JSON, or a real OTLP / Phoenix / Langfuse backend. This is what makes a run's
behavior and **dollar cost** answerable per tenant, not a mystery.

Runs **free and offline** by default (`COMPANION_MOCK=1`): the console path and the cost
roll-up are pure stdlib — **zero import-time dependency on OpenTelemetry**. The OTel-backed
exporters import their heavy deps lazily inside `export`, so the package imports and the tests
pass even when `opentelemetry` is not installed. Endpoints and keys come from the environment
only.

## Layout

```
observability/
├── attributes.py   span-attribute conventions (OTel-shaped keys) as plain constants
├── tracing.py      Tracer / Span tree, @traced decorator, run/model/tool/retrieval spans
├── cost.py         token → USD price book + per-run roll-up + CostSummary
├── exporters.py    console (default) / json / lazy otlp·phoenix·langfuse adapters
└── setup.py        read env → pick an exporter; configure_observability() at app startup
```

## Use it

```python
import observability as obs

# At app/worker startup: install a tracer + the env-selected exporter.
tracer, exporter = obs.configure_observability(run_id="agent-run-123")

with tracer.run("support-agent", attributes={obs.attributes.TENANT_ID: "acme"}):
    with tracer.retrieval_span(query="reset password", k=4):
        ...                                  # rag/ does the search
    with tracer.model_span("answer", model="claude-haiku-4-5",
                           input_tokens=1200, output_tokens=180, provider="anthropic"):
        ...                                  # llm/ gateway makes the call

exporter.export(tracer.trace)                # indented tree + per-span cost + run total
summary = obs.summarize(tracer.trace)        # total_usd, tokens, per-model breakdown
```

Or wrap any function in a span without touching its body:

```python
from observability import traced, SpanKind

@traced(kind=SpanKind.TOOL)
def search_docs(query: str) -> list[str]: ...
```

## Cost accounting

`cost.py` prices each LLM span from a per-million-token table (`PRICES`) that **mirrors the
`llm/` gateway price book** so the two subsystems agree on what a model costs. `roll_up_cost`
walks the tree and writes `agent.cost.usd` on each LLM span and `agent.cost.rollup_usd` on
every span — so a dashboard can answer "what did the retrieval phase cost?", not just "what
did the run cost?". Unknown model ids price at `$0` *and are surfaced* by `unknown_models()`,
so a newly added model never silently costs nothing. Update the table from the provider's
pricing page before trusting a real bill.

## Choosing a backend (env only)

`setup.py` resolves the exporter from the environment, in order:

| Condition | Exporter |
|---|---|
| `COMPANION_MOCK=1` (default) | `console` (offline, stdlib) |
| `OBSERVABILITY_EXPORTER=<name>` | that exporter (explicit override) |
| `OTEL_EXPORTER_OTLP_ENDPOINT` set | `otlp` → that endpoint |
| otherwise | `console` |

`phoenix` and `langfuse` are OTLP exporters pre-pointed at those backends. Sampling lives at
the exporter boundary — export every trace while learning, sample in production. The
instrumentation in `tracing.py` never changes when you swap backends.

## Dashboards & alerts (what the spans feed)

The span/cost attributes are the source for the four dashboards a senior watches — *up /
fast / good / cost* — and for symptom-based alerts (SLO burn, spend rate, eval-score drops),
not per-blip noise. The eval-score signal comes from [`evals/`](../evals/); the cost signal
comes from `summarize()` here, attributed per tenant via `attributes.TENANT_ID`.
