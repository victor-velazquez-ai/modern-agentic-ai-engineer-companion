# Template — FastAPI Agent Service
> Realizes book Ch 25, 26, 28 · Status: 📋 planned (Phase 1)

## What it scaffolds
A production-shaped FastAPI service that exposes an agent over HTTP — app factory with
lifespan, versioned routers, Pydantic Settings, dependency injection, **SSE token
streaming**, a `/health` endpoint, and a Dockerfile — with the agent call left as a TODO.

## When to copy it
You need to put an HTTP (and streaming) API in front of an agent — a real backend, not a
notebook — and want auth-ready structure, config, DI, and health checks already wired so you
only add your routes and your agent.

## Planned file tree
```text
fastapi-agent-service/
├── README.md                  # run locally / in Docker; "copy me" notice
├── pyproject.toml             # fastapi, uvicorn, pydantic-settings, sse-starlette, httpx, pytest
├── .env.example               # APP_ENV, LOG_LEVEL, ANTHROPIC_API_KEY, AUTH_SECRET ; COMPANION_MOCK=1
├── .gitignore
├── Dockerfile                 # multi-stage; non-root; uvicorn; HEALTHCHECK → /health
├── .dockerignore
├── Makefile                   # run · test · docker-build · docker-run
└── app/
    ├── __init__.py
    ├── main.py                # create_app(): lifespan, router mounts, exception handlers
    ├── core/
    │   ├── settings.py        # Pydantic Settings; ▢ add fields; fail-fast on missing
    │   ├── deps.py            # DI providers (settings, agent service, auth principal)
    │   └── security.py        # bearer/JWT stub; # TODO: wire your IdP
    ├── api/
    │   ├── __init__.py        # APIRouter aggregation under /v1
    │   ├── health.py          # GET /health → {"status":"ok"} (liveness + readiness)
    │   └── runs.py            # POST /v1/runs (sync) + GET /v1/runs/{id}/stream (SSE) — ▢ agent call
    ├── schemas/
    │   └── runs.py            # RunRequest / RunResponse / RunEvent (Pydantic models)
    ├── services/
    │   └── agent_service.py   # # TODO: call your agent; MOCK mode yields canned tokens
    └── tests/
        ├── test_health.py     # /health is 200
        └── test_runs_mock.py  # POST /v1/runs + SSE stream work in MOCK (TestClient, no API)
```

## Defaults baked in
- **App factory + lifespan:** `create_app()` for testability; startup/shutdown via lifespan.
- **Config & DI:** Pydantic Settings loaded once and injected via `Depends`; **secrets from
  `.env` only**, fail-fast when missing (Ch 28 12-factor config).
- **Streaming:** SSE endpoint via `sse-starlette` yields incremental tokens; mock mode streams
  a canned response so the stream path is testable without spend.
- **Health:** `/health` for liveness/readiness; `Dockerfile` `HEALTHCHECK` hits it.
- **Boundaries:** `api/` (transport) → `services/` (orchestration) → your agent; `core/`
  holds settings/deps/security. Hexagonal-leaning, matches the capstone's `app/` (Ch 28).
- **Container:** multi-stage, non-root user, `.dockerignore`, pinned base; runs with `uvicorn`.
- **Auth:** bearer-token dependency stub so routes are protectable from day one (Ch 26).

## Maps to the book
- **Ch 25 — Building APIs with FastAPI:** app factory, routers, Pydantic models, streaming
  (🔧 Build the backend API).
- **Ch 26 — APIs at Enterprise Grade:** the auth/DI/health hooks for authn/z, rate limits.
- **Ch 28 — Application Architecture:** layered boundaries, 12-factor config, DI.
- **Capstone:** mirrors `app/` in
  [`../../../chapters/92-appendix-capstone.typ`](../../../chapters/92-appendix-capstone.typ)
  (`main.py`, `api/`, `core/`, `services/`). **Blueprint:** the agent the service wraps is
  [`../../blueprints/agent-loop/`](../../blueprints/agent-loop/PLAN.md). Containerization
  generalizes [`../dockerfile-and-compose/`](../dockerfile-and-compose/PLAN.md).

## Phase-2 definition of done
- [ ] `uvicorn` boots from `create_app()`; `GET /health` returns `{"status":"ok"}`.
- [ ] `POST /v1/runs` and the SSE stream return canned output in `MOCK=1` (tests pass, no spend).
- [ ] `docker build` succeeds and the container's `HEALTHCHECK` goes healthy.
- [ ] Agent call is a clear `TODO`; no business logic; **no secrets committed** (`.env.example` only).
