# FastAPI Agent Service — template

> **📋 Copy me.** This is a *template*: copy the folder into your project, fill the
> `TODO` / `▢` markers, wire your agent, and delete this notice. It ships with
> production hygiene (app factory, config, DI, auth hook, SSE streaming, health
> check, Docker) but **no business logic** — the agent is yours to add.
>
> ```bash
> cp -r templates/fastapi-agent-service ~/work/my-agent-api && cd ~/work/my-agent-api
> grep -rn "TODO" .          # find every placeholder
> cp .env.example .env       # fill real values; .env is git-ignored
> ```

A production-shaped FastAPI service that exposes an agent over HTTP: app factory
with lifespan, versioned routers, Pydantic Settings, dependency injection,
**SSE token streaming**, a `/health` endpoint, and a multi-stage Dockerfile.

Realizes book **Ch 25** (Building APIs with FastAPI), **Ch 26** (APIs at
Enterprise Grade), and **Ch 28** (Application Architecture). The agent it wraps
is the hardened [`agent-loop`](../../blueprints/agent-loop/PLAN.md) blueprint;
this is the API shell the capstone's `app/` grows from.

---

## What's inside

```text
app/
├── main.py                # create_app(): lifespan, router mounts, exception handlers
├── core/
│   ├── settings.py        # Pydantic Settings; secrets from .env; fail-fast
│   ├── deps.py            # DI providers (settings, agent service, auth principal)
│   └── security.py        # bearer-token auth stub  (TODO: wire your IdP)
├── api/
│   ├── __init__.py        # router aggregation; runs mounted under /v1
│   ├── health.py          # GET /health -> {"status": "ok"}
│   └── runs.py            # POST /v1/runs (sync) + GET /v1/runs/{id}/stream (SSE)
├── schemas/runs.py        # RunRequest / RunResponse / RunEvent
├── services/agent_service.py   # TODO: call your agent; MOCK yields canned tokens
└── tests/                 # /health is 200; run + SSE work in MOCK (no API spend)
```

**Layering:** `api/` (transport) → `services/` (orchestration) → *your agent*.
`core/` holds settings, DI, and security. Routes never call the agent directly —
they go through `AgentService`, so you swap in your agent without touching `api/`.

---

## Quick start (local)

Requires Python 3.11+.

```bash
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
make install            # pip install -e ".[dev]"
cp .env.example .env    # COMPANION_MOCK=1 by default — runs with no API key
make run                # http://localhost:8000  (docs at /docs)
```

Try it (MOCK mode streams a canned response — no model call, no spend):

```bash
curl http://localhost:8000/health
# {"status":"ok"}

curl -X POST http://localhost:8000/v1/runs \
  -H "Content-Type: application/json" \
  -d '{"input":"hello"}'

# SSE stream (browser EventSource-friendly):
curl -N "http://localhost:8000/v1/runs/run_demo/stream?input=hello"
```

Run the tests (they assert the mock paths work — no key needed):

```bash
make test
```

---

## Run in Docker

```bash
make docker-build
make docker-run        # passes your local .env; container HEALTHCHECK hits /health
# or:
docker build -t my-agent-api .
docker run --rm -p 8000:8000 --env-file .env my-agent-api
```

The image is multi-stage, runs as a **non-root** user, and declares a
`HEALTHCHECK` against `/health`.

---

## Going live: fill the TODOs

Search the tree for `TODO` and `▢`. The load-bearing ones:

1. **`services/agent_service.py`** — replace the mock with a call to *your* agent
   in both `run()` (return final text) and `stream()` (yield tokens). This is the
   only place business logic belongs.
2. **`core/settings.py`** — add your own settings fields; make `ANTHROPIC_API_KEY`
   required once you go live.
3. **`core/security.py`** — replace the bearer-token stub with real IdP/JWT
   verification.
4. **`.env`** — set `COMPANION_MOCK=0` and provide a real API key for live runs.
5. **`pyproject.toml` / `Dockerfile` / `Makefile`** — rename the project/image and
   add your agent SDK dependency.

### Configuration

All config is read from the environment (and the git-ignored `.env`). See
[`.env.example`](.env.example):

| Variable | Default | Purpose |
|---|---|---|
| `APP_ENV` | `local` | Runtime environment label. |
| `LOG_LEVEL` | `INFO` | Logging level. |
| `COMPANION_MOCK` | `1` | `1` = canned tokens, no model call. `0` = call your agent. |
| `ANTHROPIC_API_KEY` | *(unset)* | Your model key; required only when `COMPANION_MOCK=0`. |
| `AUTH_SECRET` | *(unset)* | Shared secret for the auth stub; blank = auth disabled locally. |

> **Never commit secrets.** Only `.env.example` is tracked; `.env` is git-ignored.

---

## Definition of done (this template builds once the TODOs are filled)

- [x] `uvicorn` boots from `create_app()`; `GET /health` returns `{"status":"ok"}`.
- [x] `POST /v1/runs` and the SSE stream return canned output in `COMPANION_MOCK=1`.
- [x] `docker build` succeeds; the container `HEALTHCHECK` goes healthy.
- [x] The agent call is a clear `TODO`; no business logic; no secrets committed.
