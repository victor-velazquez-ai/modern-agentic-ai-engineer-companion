# Template — Dockerfile & Compose
> Realizes book Ch 35 · Status: 📋 planned (Phase 1)

## What it scaffolds
A multi-stage Dockerfile for a Python agent service plus a `docker-compose.yml` that brings
up the whole local stack — **api + worker + postgres + redis + chroma** — so one command
gives you the dependencies an agentic backend actually needs to run.

## When to copy it
You want to containerize a service and run its full local environment (DB, cache, vector
store, async worker) reproducibly — for local dev, CI, or as the base of a deploy. Copy these
files to your repo root and `docker compose up`.

## Planned file tree
```text
dockerfile-and-compose/
├── README.md                  # build/run, prod vs dev profiles; "copy me"
├── Dockerfile                 # multi-stage (builder → slim runtime); non-root; HEALTHCHECK
├── .dockerignore              # keep build context small (.venv, .git, caches, tests)
├── docker-compose.yml         # api · worker · postgres(pgvector) · redis · chroma
├── compose.override.example.yml  # ▢ local dev: bind-mounts + hot reload
└── .env.example               # DATABASE_URL, REDIS_URL, CHROMA_URL, ANTHROPIC_API_KEY ; COMPANION_MOCK=1
```

`docker-compose.yml` services:
```yaml
# api      → builds Dockerfile; depends_on db+redis+chroma (healthy); ${ANTHROPIC_API_KEY}
# worker   → same image, Celery command; shares db+redis
# postgres → pgvector image; named volume; healthcheck
# redis    → broker + cache; healthcheck
# chroma   → local vector store; named volume
```

## Defaults baked in
- **Multi-stage build:** a builder stage compiles deps, a slim runtime carries only what runs;
  small final image, **non-root** user, pinned base tag.
- **api + worker share one image** (different commands) — the capstone's pattern, so the build
  is defined once.
- **Whole stack in one file:** Postgres (pgvector), Redis (broker + cache), Chroma — the
  services an agent platform needs — each with a **healthcheck** and `depends_on … healthy`.
- **`HEALTHCHECK` in the Dockerfile** hits the service's `/health` (pairs with the FastAPI template).
- **Env-driven, secrets from `.env`:** every connection string and key is a variable; values in
  `.env.example` are local-only defaults — **no real secret committed**.
- **Dev override:** an example override file adds bind-mounts/hot-reload without touching the base.

## Maps to the book
- **Ch 35 — Containers & Kubernetes:** Dockerize a service + the local stack (🔧 Build).
- **Notebook:** the [`learn/part-08-…/35-containers-and-kubernetes/`](../../learn/) walkthrough
  builds toward exactly this. **Templates:** the `api` service builds
  [`../fastapi-agent-service/`](../fastapi-agent-service/PLAN.md); the worker prefigures the
  capstone `workers/`. **Capstone:** generalizes the root `Dockerfile` +
  `docker-compose.yml` in
  [`../../../chapters/92-appendix-capstone.typ`](../../../chapters/92-appendix-capstone.typ)
  (api · worker · postgres · redis · chroma — the same five services).

## Phase-2 definition of done
- [ ] `docker compose up --build` brings all five services up and they reach **healthy**.
- [ ] The `api` container's `HEALTHCHECK`/`/health` is green; `worker` connects to redis+db.
- [ ] Final image is multi-stage, non-root, and small; `.dockerignore` trims the context.
- [ ] All connection strings/keys are env vars; `.env.example` only — **no secret committed**.
