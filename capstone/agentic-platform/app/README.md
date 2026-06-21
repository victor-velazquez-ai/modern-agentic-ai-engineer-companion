# `app/` — FastAPI backend (Ch 25–26, 28, 30)

The platform's HTTP surface and its modular-monolith core. This is the **assembled** service the
[`fastapi-agent-service`](../../../templates/fastapi-agent-service) template is the seed of: the
template is the smallest copy-into-your-job scaffold; this is the full backend the book grows
across Part VII.

> Built across Ch 25 (the API), Ch 26 (auth, rate limits, multi-tenancy), Ch 28 (hexagonal
> seams + 12-factor config + DI + graceful shutdown), Ch 30 (the data layer). See the
> capstone [`PLAN.md`](../../PLAN.md) row for `app/`.

## Layout

```text
app/
├── main.py            # app factory + lifespan (pool open/close, local schema bootstrap)
├── api/               # transport only — routes + schemas + error→HTTP mapping
│   ├── __init__.py    #   router aggregation (/health, /readyz, /v1/*)
│   ├── health.py      #   liveness (/health) + readiness (/readyz, checks the DB)
│   ├── runs.py        #   POST/GET runs + GET /{id}/stream (SSE via StreamingResponse)
│   ├── chats.py       #   conversations + messages
│   ├── documents.py   #   RAG catalog: register + list + fetch
│   ├── schemas.py     #   Pydantic boundary models (from_domain mappers)
│   └── errors.py      #   domain-error → HTTP status translation
├── core/              # cross-cutting frame (no business rules)
│   ├── config.py      #   Pydantic Settings — 12-factor, fail-fast (Ch 4, 28)
│   ├── auth.py        #   bearer-auth Principal + tenant scoping + require_scope (Ch 26)
│   ├── ratelimit.py   #   in-process token-bucket limiter (Ch 26)
│   └── deps.py        #   DI providers: session → repositories → services
├── domain/            # framework-free core — imports nothing web/db (Ch 28)
│   ├── models.py      #   entities + the AgentRun state machine
│   ├── ports.py       #   Protocol seams (repositories, AgentEngine)
│   └── errors.py      #   domain exception hierarchy
├── db/                # persistence adapter (Ch 30)
│   ├── base.py        #   declarative Base + tenant/timestamp mixins
│   ├── models.py      #   ORM rows (distinct from domain entities)
│   ├── session.py     #   async engine + session dependency + create_all
│   ├── repositories.py#   adapters satisfying the domain ports (row ↔ entity)
│   └── migrations/    #   Alembic env + the initial schema version
└── services/          # use-case layer — orchestrates domain ↔ adapters (Ch 28)
    ├── agent_service.py    # the AgentEngine seam: MockAgentEngine + live RawLoopAgentEngine
    ├── run_service.py      # create / fetch / list / inline-run / stream
    ├── chat_service.py     # conversations + messages
    └── document_service.py # register + list documents
```

## The one rule (modular monolith)

Dependencies point **inward**. `domain/` imports nothing from `api`, `db`, or `services`;
`services/` wires the domain's *ports* to concrete adapters; `api/` is pure transport. That is
the seam the book's "extract this" advice pays off at — you could lift `domain/` + `services/`
into a separate package without touching a route.

## Running it (MOCK by default)

With `COMPANION_MOCK=1` (the default) the whole backend runs **offline** — no API key, no spend.
The agent engine is `MockAgentEngine` (canned tokens) and the database defaults to in-memory
SQLite, so the schema is created at startup in `local` mode.

```bash
uv run fastapi dev app/main.py          # or: uvicorn app.main:app --reload
curl localhost:8000/health              # {"status":"ok"}
curl -N "localhost:8000/v1/runs/r1/stream?input=hello"   # watch the SSE tokens
```

Set `COMPANION_MOCK=0` and `ANTHROPIC_API_KEY` (and `DATABASE_URL`) to run live; the live agent
engine wires to the capstone `agents/raw` loop (`services/agent_service.py`). Secrets are read
from the environment only — never hard-coded.
