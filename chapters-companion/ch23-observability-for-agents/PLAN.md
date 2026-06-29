# Ch 23 — Observability for Agentic Systems

> Companion plan · Part VI · book file `chapters/23-observability-for-agents.typ`
> Status: 📋 planned (Phase 1)

## Role in the companion
Evaluation says *how good*; observability says *what it actually did* — and for an agent the
3 a.m. failure may never reproduce, so the trace is the only evidence that will ever exist.
These notebooks build the *instrument* and *observe* stations of the flywheel: the reader
instruments an agent run as an OpenTelemetry **span tree** (using the GenAI semantic
conventions), computes **cost per run** from span attributes, then debugs a non-deterministic
multi-step failure *from the trace alone* and aggregates run- and **session**-level metrics.
The OTel emission layer is real; the exporter/backend is treated as swappable, mirroring the
chapter's core architectural advice.

## Planned notebooks

### 23-01 · `23-01-tracing-agent-runs-otel.ipynb` — A flight recorder for one agent run
- **Type:** walkthrough
- **Maps to:** §23.1 (🔧 tracing agent runs with OpenTelemetry — spans, the GenAI semantic
  conventions, context propagation, deliberate payload capture), §23.3 (logging, metrics &
  cost accounting — RED + agentic vital signs, the cost incident, the "capture from day one"
  wish list), §23.2 (platforms — OTel as a swappable backend)
- **Objective:** instrument an agent loop so one user request becomes one trace — every model
  call, tool call, and retrieval a span with the right attributes — and compute per-run cost
  from those spans.
- **Prereqs:** Ch 12 (the tool-use loop being instrumented); §21.1's idea that every run must
  emit a trace.
- **Cell arc:**
  - 🧠 mental model: a trace is a *flight recorder for one agent run* — design instrumentation
    by asking "if this misbehaves once and never again, does the trace alone explain it?"
  - Set up an OTel `TracerProvider` with an **in-memory/console exporter** (no backend, no
    network) so spans are inspectable in-notebook.
  - Instrument the book's three spans: `agent.run` (root: `agent.name`, `user.id` *id not PII*,
    `session.id`, `agent.steps`, `agent.outcome`), `llm.call`, and `tool.call`, using the OTel
    **GenAI semantic conventions** (`gen_ai.request.model`, `gen_ai.usage.input_tokens`,
    `gen_ai.usage.output_tokens`, `gen_ai.response.finish_reason`) — the book's `telemetry.py`
    shapes.
  - Run a tiny mock agent (≥1 model call + ≥1 tool call, **one tool call fails and retries**);
    print the resulting **span tree** and read it like the chapter's `agent-trace` figure —
    including the failed `send_report` + retry a final-answer-only log would have hidden.
  - 🔮 *predict* which span dominates latency, then read the timings.
  - **Record exceptions on the failing span** (`record_exception`, `StatusCode.ERROR`) and see
    the error captured in-tree rather than swallowed.
  - **Cost accounting:** build the book's `span_cost` from `gen_ai.usage.*` + a prices table;
    sum per-run cost and call out the **cost incident** failure mode (a looping agent burns
    hundreds of dollars with *no error in the logs*) → in-code per-run token ceiling, not the
    invoice.
  - **Context propagation:** show carrying trace context across an async/sub-agent (or simulated
    Celery, Ch 31) boundary so the distributed run stays *one tree*.
  - ⚠️ pitfall: logging the prompt **template** but not the **rendered prompt** — store what the
    model actually saw (the single highest-value attribute); also the day-one capture wish list
    (rendered prompt + version, model id + every sampling param, retrieved chunks with scores,
    full tool args + raw results, plan/reasoning summary, git SHA, feedback/eval verdict).
  - ⚠️ pitfall: payloads are bulky and sensitive — capture with **truncation, PII/secret
    redaction, and a retention policy**, not "log nothing" or "log everything forever."
  - 🎯 senior lens: instrument once with OTel, treat the platform as a swappable backend — the
    asset is the instrumentation and the habits, not the dashboard.
- **Datasets/fixtures:** a seeded mock agent + mock tools (one designed to fail then succeed);
  a small illustrative `PRICES` dict loaded from an in-notebook config (prices change). No
  external collector.
- **APIs & cost:** none for tracing (in-memory/console exporter, fully offline); the agent it
  traces is mockable (`MOCK=1` canned). Live agent run optional on `MOCK=0`.
- **You'll be able to:** instrument any agent loop as an OTel span tree with GenAI attributes,
  read a span tree to see what a run actually did, and compute per-run cost — the *instrument*
  station of the flywheel.

### 23-02 · `23-02-debugging-and-dashboards.ipynb` — Debug from the trace; watch runs and sessions
- **Type:** walkthrough
- **Maps to:** §23.4 (debugging non-deterministic, multi-step failures — read the trace before
  theorizing, reproduce at the right granularity, fix in the eval suite), §23.5 (dashboards,
  alerting & on-call — operational vs quality altitudes, **session-level** metrics, page-vs-
  ticket), §23.2 (what platforms add: trace/session search, datasets, annotation queues), the
  §23 observability readiness checklist
- **Objective:** debug an agent failure you *cannot* reproduce by investigating from trace
  evidence, then aggregate the right run- and session-level metrics and route signals correctly
  (page vs ticket).
- **Prereqs:** 23-01 (you need traces to debug and aggregate); 22-03 (the eval suite a fixed
  bug lands in).
- **Cell arc:**
  - 🧠 mental model: debugging an agent **inverts** the classic loop — you usually can't
    reproduce first, so investigate from evidence.
  - **Read the trace before you theorize:** walk the span tree chronologically to the **first
    divergence point**; the wrong final answer is downstream of the failure that matters. Work
    a planted case through the book's base-rate suspect list (bad retrieval → tool failed and
    model improvised → wrong rendered prompt → silent context truncation → model sampled badly).
  - 🔮 *predict* the divergence point from the symptom, then walk the trace and locate it.
  - **Reproduce at the right granularity:** replay a *single* model call with its recorded
    rendered prompt + params and **resample 10×** to tell a tail event from the norm; note that
    replaying a whole multi-step run needs **recorded tool results** (the fixture pattern from
    API testing) because tools have side effects and the world moved.
  - **Fix it in the eval suite, not just the code:** the investigation *ends* by adding the
    failing case to the golden set (links back to 22-03) — a debugging session that doesn't end
    in an eval case is one you'll repeat.
  - **Dashboards at two altitudes:** *operational* ("is it on fire?": rate, errors, latency
    pctiles, token spend/hour, tool-failure rate, provider status) vs *quality* ("are we getting
    better?": task-success/eval trends, feedback rate, cost per resolved task, slice scores, top
    failure buckets); **every chart drills to traces** — a chart you can't drill into is a rumor.
  - **Session-level metrics** (the conversational tier the capstone needs): turns-to-resolution,
    conversation success rate, abandonment/drop-off, **cost-per-resolved-conversation** —
    stitched from runs via the `session.id` stamped in 23-01; the observability counterpart to
    Ch 22's user-simulator evals. Compute these over a small set of mock multi-run sessions.
  - ⚠️ pitfall: alerting — **page on operational symptoms** (error/latency/cost spikes, provider
    outages, tool-failure storms; a spend-per-hour alert saves months) but **don't page on slow
    quality drift** — a 2-point eval dip is tomorrow's error-analysis ticket, not a 3 a.m. wake.
  - **On-call's new wrinkle:** many incidents are *external behavior changes* (provider model
    update, degraded API, rate-limit shift) that no repo diff explains → runbook starts with
    provider status + recent model/config versions, then failing traces, then mitigation levers
    (model fallback, pinned previous prompt version, scope-narrowing feature flag, graceful
    degradation).
  - **What a platform adds** (§23.2): trace/session **search** ("every run over $5", "every
    trace tagged `refund` that errored yesterday"), one-click add-to-dataset, annotation queues,
    online/offline judge scoring, prompt versioning stamped on every trace — and the
    self-host vs SaaS choice as a **data-governance** decision (traces hold real user prompts).
  - 🎯 senior lens: triage by **distribution, not drama** — spend the week on the biggest
    failure cluster; file the spectacular one-off as an eval case and move on.
  - 📋 the §23 **observability readiness checklist** (every run a trace; context propagated;
    rendered prompt + params + scored chunks + raw tool I/O captured with redaction/retention;
    versions + git SHA stamped; cost per run with budgets; feedback/eval joined by trace id;
    page-vs-ticket discipline; runbook with mitigation levers; every debug session ends in an
    eval case).
- **Datasets/fixtures:** `data/traces/` — a few committed canned span trees as JSON (one with a
  planted retrieval miss, one with a tool-failure-improvised-fact) + a handful of mock
  multi-run sessions for the session metrics; no live collector.
- **APIs & cost:** none — operates on canned traces and offline aggregation; optional `MOCK=0`
  resample of a single live model call to demonstrate tail-vs-norm.
- **You'll be able to:** find a failure's divergence point from a trace, reproduce a single call
  at the right granularity, compute run- and session-level health metrics, and set page-vs-
  ticket alerting — the *observe* station, closing the flywheel back into Ch 22's eval suite.

## Feeds (cross-pillar)
- **Blueprint(s):** [`blueprints/observability-stack/`](../../blueprints/observability-stack/)
  — the production OTel tracing + cost-accounting + dashboards stack (instrument once, swap the
  backend); both notebooks end pointing here. Cross-links to
  [`blueprints/eval-harness/`](../../blueprints/eval-harness/) (Ch 22) for the case a fixed
  bug lands in.
- **Template(s):** — (no new template; reinforces the env-var/secrets conventions and the
  redaction/retention defaults reused across services).
- **Capstone:** advances `capstone-project/telemetry.py` (the instrumented agent loop) and wires the
  *instrument*/*observe* stations into `capstone-project/` that gate and explain every run; checkpoint
  `checkpoints/ch23-observability`. Cost/session metrics here become the SLO signals formalized
  in Ch 42.

## Dependencies
- Ch 12 (the agent loop to instrument) · Ch 22 (the eval suite that debugging feeds; judges/
  scorers join traces by id) · Ch 21 (the *instrument*/*observe* stations of the flywheel).
  Forward: Ch 31 (propagating trace context to Celery workers), Ch 42 (SLOs/error budgets on
  these signals).

## Phase-2 definition of done
- [ ] Both notebooks run top-to-bottom in `MOCK=1` with no errors and **no external collector**
      (in-memory/console OTel exporter; canned traces for debugging).
- [ ] Span names + GenAI attributes (`gen_ai.request.model`, `gen_ai.usage.*`,
      `gen_ai.response.finish_reason`), the `span_cost` shape, the divergence-point suspect
      list, and the run-vs-session + page-vs-ticket distinctions match the book's §23 exactly.
- [ ] Rendered-prompt-not-template capture, truncation/redaction/retention, and "every debug
      session ends in an eval case" are demonstrated, not just mentioned.
- [ ] Each notebook ends with recap + 2–3 change-and-predict exercises and a link to
      `blueprints/observability-stack/` and `capstone-project/telemetry.py`.
- [ ] No secrets/PII in committed trace fixtures; ids only, never PII, on spans.
