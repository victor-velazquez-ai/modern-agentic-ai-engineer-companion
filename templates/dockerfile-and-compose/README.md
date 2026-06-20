# Template — Dockerfile & Compose

> **Copy me.** A multi-stage `Dockerfile` for a Python agent service plus a
> `docker-compose.yml` that brings up the **whole local stack** — `api`, `worker`,
> `postgres` (pgvector), `redis`, and `chroma` — so one command gives you the
> dependencies an agentic backend actually needs to run. Realizes **Ch 35**.

This is a **scaffold**, not a library: copy the files into your repo, fill the
`TODO` / `▢` markers, and never commit a real secret. There is **no business
logic** here — the `api`/`worker` image expects *your* application package.

---

## What you get

| File | Purpose |
|---|---|
| `Dockerfile` | Multi-stage (builder → slim runtime), **non-root**, pinned base, `HEALTHCHECK` → `/health`. Built once; the `api` and `worker` share it. |
| `docker-compose.yml` | The five services, each with a healthcheck and `depends_on: service_healthy`. Named volumes for durable data. |
| `compose.override.example.yml` | Local-dev overlay: bind-mounts + hot reload, without editing the base file. |
| `.dockerignore` | Keeps the build context (and image) small and secret-free. |
| `.env.example` | Every connection string and key as a variable. Copy to `.env` (git-ignored). |

The `api` service is meant to build the
[`../fastapi-agent-service/`](../fastapi-agent-service/PLAN.md) template (an ASGI
app at `app.main:app` exposing `GET /health`); the `worker` prefigures the
capstone's async `workers/`.

---

## Copy and use

```bash
# 1. Copy the scaffold to your repo root (the Dockerfile expects ./app next to it).
cp templates/dockerfile-and-compose/{Dockerfile,docker-compose.yml,.dockerignore} .
cp templates/dockerfile-and-compose/.env.example .env
cp templates/dockerfile-and-compose/compose.override.example.yml compose.override.example.yml

# 2. Fill in the placeholders.
grep -rn "TODO" .            # or search TODO / ▢ in your editor
#   - Dockerfile: dependency file (pyproject vs requirements), COPY paths, CMD
#   - docker-compose.yml: the worker `command` (your Celery app)
#   - .env: change the Postgres credentials before leaving your laptop

# 3. Bring the whole stack up.
docker compose up --build
docker compose ps           # all five services should reach "healthy"

# 4. Hit the API.
curl http://localhost:8000/health     # -> {"status":"ok"}
```

To stop: `docker compose down` (add `-v` to also delete the named volumes / data).

---

## Prod vs dev

**Prod / CI (default).** Plain `docker compose up` uses only `docker-compose.yml`:
the image is built from source, code is baked in, no bind-mounts. This is the
shape you deploy and the shape CI builds.

**Dev (hot reload).** Opt into the override by copying it to the auto-merged name:

```bash
cp compose.override.example.yml compose.override.yml   # git-ignored
docker compose up                                       # base + override merged
```

The override bind-mounts `./app` into the containers and switches the `api` to
`uvicorn --reload` (and the `worker` to a watch-restart), so saved edits take
effect without rebuilding. Because the file is named `compose.override.yml`,
Compose merges it automatically — your prod file stays untouched.

---

## Mock mode (free, offline, deterministic)

`COMPANION_MOCK=1` (the default in `.env.example`) tells the `api`/`worker` to use
canned replies instead of calling a real model — the whole stack comes up and
exercises every path with **no API key and no spend**. Set `COMPANION_MOCK=0` and
provide `ANTHROPIC_API_KEY` in `.env` only when you want live model calls.

---

## The five services

| Service | Image | Role | Host port |
|---|---|---|---|
| `api` | built from `Dockerfile` | HTTP/streaming API in front of your agent | `8000` |
| `worker` | same image | async task processor (Celery) | — |
| `postgres` | `pgvector/pgvector:pg16` | relational store + vector column | `5432` |
| `redis` | `redis:7-alpine` | Celery broker/backend + cache | `6379` |
| `chroma` | `chromadb/chroma:0.5.5` | local vector store | `8001` → 8000 |

Override any host port via `.env` (`API_PORT`, `POSTGRES_PORT`, …) if it clashes
with something already running on your machine.

---

## Secrets

Every connection string and key is an environment variable read from `.env`
(which is git-ignored). The values shipped in `.env.example` are **local-only
development defaults** — there is no real secret in any committed file, and there
should never be one in yours. Change the Postgres credentials before you use this
anywhere that is not your laptop.

---

## Definition of done (after you fill the TODOs)

- [ ] `docker compose up --build` brings all five services up; `docker compose ps` shows **healthy**.
- [ ] `curl localhost:8000/health` returns `{"status":"ok"}`; the `worker` connects to redis + postgres.
- [ ] The final image is multi-stage, non-root, and small; `.dockerignore` trims the context.
- [ ] All connection strings/keys are env vars; `.env` holds your values; **no secret is committed**.
