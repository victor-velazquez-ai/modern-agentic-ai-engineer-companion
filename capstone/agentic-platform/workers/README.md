# `workers/` — Celery async runs + schedules (Ch 31)

Background execution for the platform. The operational insight the whole subsystem encodes
(Ch 31): **agent runs belong in the background.** The API stays thin and *enqueues*; the worker
does the long, retryable work and checkpoints. The worker shares the backend's `app/` code — one
image, two entrypoints (Appendix C's `Dockerfile`).

> Built in Ch 31 (§31 Build — async runs + beat schedules). Idempotency/outbox patterns come
> from Ch 29. See the capstone [`PLAN.md`](../../PLAN.md) row for `workers/`.

## Layout

```text
workers/
├── celery_app.py        # the Celery app: Redis broker/result, reliability conf, beat schedule
├── runtime.py           # bridge from sync task bodies to the app's async services/sessions
└── tasks/
    ├── agent_runs.py     # execute a queued AgentRun end to end, idempotently
    ├── ingestion.py      # chunk → embed → index a registered document (composes rag/)
    ├── schedules.py      # beat-driven automations: nightly evals, reindex stale docs
    └── outbox.py         # transactional-outbox relay + idempotency-key guard (Ch 29)
```

## Reliability shape (Ch 29)

- **acks-late** (`celery_app.conf.task_acks_late`) — a task is acknowledged only after it
  finishes, so a crashed worker's job is redelivered, not lost.
- **idempotency** — `tasks/agent_runs.py` and `tasks/ingestion.py` short-circuit when the entity
  is already terminal/indexed, so a redelivery never double-executes. `tasks/outbox.py` adds a
  first-write-wins key guard for side effects.
- **transactional outbox** — write the intent to emit a side effect in the *same* transaction as
  the state change; a beat-scheduled relay (`relay_outbox`) delivers it later. No dual-write race.

## Running it (MOCK by default)

```bash
uv run celery -A workers.celery_app worker --loglevel=info   # the worker
uv run celery -A workers.celery_app beat   --loglevel=info   # the scheduler
```

With `COMPANION_MOCK=1` (the default) every task runs the offline engine and the mock ingest
pipeline — no model call, no vector store required. Tasks call the **same** domain services the
API uses (via `workers.runtime`), so there is one definition of each operation, not two. The
broker/result backend is Redis (`REDIS_URL`); only `celery_app`/runtime read it.
