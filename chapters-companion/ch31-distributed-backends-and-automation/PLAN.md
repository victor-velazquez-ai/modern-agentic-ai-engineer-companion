# Ch 31 — Distributed Backends, Task Queues & Automation

> Companion plan · Part VII · book file `chapters/31-distributed-backends-and-automation.typ`
> Status: 📋 planned (Phase 1)

## Role in the companion
This chapter gives the capstone its spine: a thin API in front, a fleet of background
**workers** behind a queue. The notebooks build that shape with **Celery** — define a task,
`.delay()` it, make it idempotent under `acks_late`, schedule it with **Beat** — then do the
chapter's 🔧 Build: an **async agent run** (`/runs` enqueues, a worker runs the loop and
checkpoints each step, the client subscribes) plus a **scheduled "morning digest" automation**.
Redis (broker) and a worker run via **docker compose**, but every notebook also runs with
Celery's `task_always_eager` / an in-process fake broker so it executes free and green in CI
with no services. This is where the capstone's `workers/` directory is born.

## Planned notebooks

### 31-01 · `31-01-celery-tasks-retries-and-beat.ipynb` — Move slow work off the request path
- **Type:** walkthrough
- **Maps to:** §31.1 (modular monolith vs microservices, revisited), §31.2 (message queues &
  streaming), §31.3 (Celery in depth: producer/broker/worker/result backend/Beat)
- **Objective:** define a Celery task, enqueue it with `.delay()` so the API returns
  immediately, make it survive transient failures with retry+backoff and `acks_late`, and
  schedule a periodic run with Beat.
- **Prereqs:** Ch 4 (async), Ch 29 (at-least-once, idempotency, retries/backoff).
- **Cell arc:**
  - 🧠 the rule: if a user waits for it and it needn't happen now, it shouldn't happen now —
    queues buy responsiveness, resilience, elasticity.
  - Queue-vs-stream map: SQS / RabbitMQ / Redis (discrete tasks) vs Kafka (replayable log);
    when many consumers need the same events, reach for a stream.
  - Build the book's `reindex_documents` task (`bind=True, max_retries=3, acks_late=True`);
    call `.delay("kb-42")`; show it returns instantly while the worker runs it.
  - 🔮 *predict*: a `TransientError` raises `self.retry(countdown=2 ** retries)` — what's the
    delay sequence? (1s, 2s, 4s) Watch the backoff.
  - Explain the two correctness-bearing settings: `max_retries`+backoff (transient failures are
    *guaranteed* in a distributed system) and `acks_late` (ack only *after* completion, so a
    crashed worker's message returns to the queue).
  - Beat: register the `nightly-reindex` schedule via `crontab(hour=3, minute=0)`.
  - ⚠️ pitfall: `acks_late` ⇒ a task can run **more than once** (worker dies after finishing,
    before acking) — at-least-once again, so tasks must be **idempotent** (Ch 29).
  - 🎯 senior lens: a monolith + a task queue handles the vast majority of "do this slow thing
    later"; you do *not* need microservices for background work.
- **Datasets/fixtures:** none — `reindex` is a stubbed slow function (a seeded sleep/counter).
- **APIs & cost:** none (no model calls). **Docker:** optional Redis broker + a worker via
  compose; default uses Celery `task_always_eager=True` (or an in-process fake broker) so tasks
  execute inline in CI — call out where eager mode hides real broker/ack behaviour.
- **You'll be able to:** push slow work to a worker with correct retries/acks and schedule it
  with Beat.

### 31-02 · `31-02-idempotent-tasks-and-orchestration-choices.ipynb` — Make re-execution safe; pick the right tool
- **Type:** walkthrough
- **Maps to:** §31.4 (background jobs / long-running agent tasks; Dramatiq/RQ/arq field),
  §31.5 (durable workflow orchestration; Temporal/Prefect/Airflow), §31.5.1 (durable execution
  meets non-determinism), §31.7 (event-driven architecture, briefly)
- **Objective:** make a Celery task idempotent so the `acks_late` double-run can't corrupt
  data, then learn to *choose* between a task queue, a durable-execution engine, and a DAG
  orchestrator — and why an agent's non-determinism breaks naive replay.
- **Prereqs:** 31-01; Ch 29 (idempotency keys, outbox); Ch 16 (agent loop) referenced.
- **Cell arc:**
  - 🔮 *predict*: run a non-idempotent "send email" / "charge" task twice (simulating the
    `acks_late` re-run) — how many side effects? Show the duplicate.
  - Fix it: an idempotency key + an "already done?" check (the Ch 29 ledger pattern) so the
    second execution is a no-op; re-run to confirm "effectively once."
  - Tool-fit decision cell: fire-and-forget / periodic → **Celery**; long, stateful, resumable
    with waits & human steps → **Temporal-style durable execution**; scheduled DAG of data
    transforms → **Prefect/Airflow**. Note Dramatiq (simpler), RQ (Redis-only), arq (asyncio).
  - 🧠 durable execution = **event-sourced replay**: after a crash the workflow re-runs from the
    top, fed recorded step results — which assumes determinism.
  - ⚠️ pitfall: point replay at an **agent** and the LLM returns something different on
    re-call, so live execution *diverges* from its recorded history and replay corrupts state.
  - The fix (book's `record_activity` shape): treat each model/tool call as a **recorded
    activity** whose result is persisted once; on replay return the recorded output (model is
    never re-called). Pin side effects **exactly-once** with an `idempotency_key` per step.
  - Event-driven aside: components emit events ("document.indexed", "agent.run.completed");
    the outbox/saga/idempotent-consumer machinery from Ch 29 keeps it correct.
  - 🎯 senior lens: know when *not* to write code (next notebook) and when *not* to hand-roll a
    resumable multi-day workflow in Celery — reach for the orchestrator built for it.
- **Datasets/fixtures:** in-memory ledger + a mock "activity log" to demo replay; seeded RNG.
- **APIs & cost:** the agent/model step is **mocked** (a canned plan/result) so replay and
  idempotency are deterministic; no live calls.
- **You'll be able to:** guarantee a task is safe to re-run and pick queue vs durable-execution
  vs DAG for a given workload.

### 31-03 · `31-03-build-async-agent-runs-and-scheduled-automation.ipynb` — 🔧 Build the capstone `workers/`
- **Type:** walkthrough  *(this is the chapter's 🔧 Build, §31.8)*
- **Maps to:** §31.8 (🔧 Build: async agent runs + a scheduled automation), §31.4 (agent runs
  belong in the background), §31.6 (integration/automation platforms — n8n/Zapier as triggers
  & actions)
- **Objective:** build the platform spine — a `/runs` endpoint enqueues a Celery `run_agent`
  task and returns a `run_id` immediately; a worker executes the agent loop, **checkpoints**
  each step (Ch 14) so it survives a restart, and **publishes progress** the client subscribes
  to; plus a Beat **"morning digest"** automation that runs an agent with no human in the loop.
- **Prereqs:** 31-02; Ch 25 (FastAPI, WebSocket/SSE) for the dispatch + subscribe path; Ch 14
  (checkpointing); Ch 16 (the agent loop being run).
- **Cell arc:**
  - 🧠 the pattern to internalize: **the request layer accepts and dispatches; the worker layer
    does the slow, stateful work** — thin fast API in front, scalable workers behind a queue.
  - Build the book's `run_agent` task (`bind=True, acks_late=True, max_retries=3`):
    `load_or_create(run_id, goal)` to resume on retry, loop the agent, `checkpoint(run_id,
    step)` and `publish_progress(run_id, step)` each step, `self.retry` with backoff on
    `TransientError`.
  - The dispatch half: `/runs` enqueues and returns `run_id` instantly; the client polls or
    subscribes (WebSocket/SSE) for progress and the final result — agent runs never block HTTP.
  - 🔮 *predict*: kill the worker at step 3, then restart — does the run resume from the
    checkpoint or restart from zero? Show durable resume.
  - Scheduled automation: register `morning-digest` via `crontab(hour=7, minute=0)` to run a
    "summarize last 24h of docs; post to Slack" agent — the platform working autonomously.
  - Integration platforms: n8n/Zapier/Make as **triggers** that kick off agents and **actions**
    agents reach (often the same tools exposed over MCP, Ch 19); when to let ops own a visual
    automation instead of bespoke code.
  - ⚠️ pitfall: re-runs (the `acks_late` reality) — `run_agent` must be idempotent per step so a
    resumed run reuses recorded outcomes (idempotency keys, Ch 29) and doesn't double its side
    effects.
  - 🎯 senior lens: this shape — not any clever prompt — is what makes an agentic system
    production-grade; scale the expensive agent work by simply adding workers. Ends by pointing
    at the capstone `workers/` (the real, deployable version; deployed on AWS in Part VIII).
- **Datasets/fixtures:** a mock agent loop (canned steps) + an in-memory checkpoint store and
  progress channel; the "Slack post" is a dry-run log line.
- **APIs & cost:** the agent loop and the digest are **mocked** (`MOCK=1` canned steps) so the
  whole build runs free/deterministically; `MOCK=0` would do a short real agent run. **Docker:**
  optional Redis + worker via compose; default runs eager/in-process. The Slack/automation
  side effect is **dry-run by default**, opt-in and ⚠️-flagged.
- **You'll be able to:** stand up async, durable, idempotent agent runs behind a queue and a
  scheduled automation — the capstone's production spine.

## Feeds (cross-pillar)
- **Blueprint(s):** the `run_agent` worker wraps the agent loop from
  [`blueprints/agent-loop/`](../../blueprints/agent-loop/) (idempotent, retried, checkpointed).
- **Template(s):** the worker + broker services extend
  [`templates/fastapi-agent-service/`](../../templates/fastapi-agent-service/)'s docker-compose
  (api + worker + Redis).
- **Capstone:** **builds `capstone-project/workers/`** (Celery app, `run_agent`, Beat schedules,
  idempotent task patterns) and the async `/runs` dispatch in `capstone-project/app/`; advances the
  checkpoint/resume integration with `capstone-project/` checkpointing (Ch 14). Checkpoint
  `checkpoints/ch31-workers-and-automation`.

## Dependencies
- Ch 29 (idempotency, at-least-once, retries/backoff, outbox/saga) · Ch 14 (checkpointing) ·
  Ch 16 (agent loop) · Ch 25 (FastAPI, WebSocket/SSE dispatch) · Ch 30 (workers persist
  state/checkpoints in the data layer). Deployed in Part VIII (AWS).

## Phase-2 definition of done
- [ ] All three notebooks run top-to-bottom in `MOCK=1` with **no services** (eager/in-process
  broker, mocked agent loop) and no errors; the live docker-compose + `MOCK=0` path is documented.
- [ ] Celery task shape (`acks_late`, `max_retries`, backoff), Beat schedules, `record_activity`
  replay, and the `run_agent` checkpoint/publish loop match the book's §31 code.
- [ ] The automation/Slack side effect defaults to dry-run, is ⚠️-flagged, and is opt-in.
- [ ] Each ends with recap + exercises and links to `blueprints/agent-loop/` and the capstone
  `workers/`; secrets/broker URLs from env only; no keys in committed outputs.
