# Ch 28 — Application Architecture & Enterprise Patterns

> Companion plan · Part VII · book file `chapters/28-application-architecture.typ`
> Status: 📋 planned (Phase 1)

## Role in the companion
Chapter 27 was architecture in the large; this one is the *inside* of one service. The
notebooks make the dependency rule physical: the reader builds a tiny domain service against a
**port**, swaps two adapters without touching the core, then wires it with DI and gates a
change behind a feature flag. These are the enterprise patterns an ML background skips and a
senior reviewer demands — and the exact shape the capstone's `app/` will take. Concept- and
walkthrough-led: most of the value is *seeing* optionality and 12-factor config pay off, not
writing much code.

## Planned notebooks

### 28-01 · `28-01-hexagonal-ports-and-adapters.ipynb` — Isolate the domain, swap the edge
- **Type:** walkthrough
- **Maps to:** §28.1 (layered/hexagonal/clean, the dependency rule), §28.2 (DDD-lite:
  ubiquitous language, bounded contexts, aggregates)
- **Objective:** structure a service so business logic depends on a `Protocol` port, not a
  concrete store — then prove optionality by swapping the adapter under a fixed core.
- **Prereqs:** Ch 4 (typing/`Protocol`), Ch 27 (architecture styles, quality attributes).
- **Cell arc:**
  - 🧠 mental model: dependencies point *inward*; the hexagon (core · ports · adapters).
  - Define a `DocumentStore` port (`Protocol`) and a pure `ResearchService` that needs only it.
  - Write an in-memory fake adapter; unit-test the service with **no network, no DB**.
  - 🔮 *predict*: swap in a second adapter (a stub "vector store") — what in the core changes?
  - Run with both adapters; confirm the core file is byte-for-byte unchanged.
  - DDD-lite cell: rename to the business's *ubiquitous language*; show a `Draft` aggregate
    that enforces its own invariant behind one entry point.
  - ⚠️ pitfall: cargo-culting four layers + a DI container into a 200-line tool — apply only
    as much structure as size/lifespan justify.
  - 🎯 senior lens: the model is a *choice, not a discovery*; boundaries that match how the
    business changes make a thousand future edits easy.
- **Datasets/fixtures:** 2–3 tiny in-memory "documents"; no external services.
- **APIs & cost:** none — fully offline by design (structure lesson, not a model lesson).
- **You'll be able to:** keep business logic free of framework/DB imports and swap an
  implementation with a one-line wiring change.

### 28-02 · `28-02-config-di-and-feature-flags.ipynb` — 12-factor config, the composition root, dark launches
- **Type:** walkthrough
- **Maps to:** §28.3 (Twelve-Factor + Pydantic Settings, secrets discipline), §28.4 (DI &
  composition root), §28.5 (feature flags / progressive delivery)
- **Objective:** load typed config from the environment, wire adapters at one composition
  root, override a dependency in a test, and flip behaviour with a flag — no redeploy.
- **Prereqs:** 28-01.
- **Cell arc:**
  - 🧠 12-factor: config in the *environment*; the same build runs in dev/stage/prod.
  - Define a `Settings(BaseSettings)` with `env_prefix`; show it **fail fast** when a required
    var is missing (set/unset an env var across two runs).
  - 🔮 *predict*: read a secret from `os.environ` vs a hardcoded literal — which one leaks to
    git/logs? Discuss secret managers (AWS Secrets Manager / SSM, Vault) + rotation at runtime.
  - DI as composition root: a `get_store()` / `get_service()` factory pair (FastAPI `Depends`
    shape) that decides the real adapter in *one* place; override `get_store` with the fake.
  - Feature flag: `flags.enabled("new_planner", user=...)` routes to new vs baseline; toggle a
    percentage and watch routing change with no code change.
  - ⚠️ pitfall: committing a `.env`, or shipping secrets *as* `.env` to prod (gitignore it;
    fetch from the secret manager in the cloud; scan history for leaked keys).
  - 🎯 senior lens: flags decouple *deploy* from *release* — for probabilistic AI features,
    expand/retract by percentage and pair with online evals (Part VI) before betting the fleet.
- **Datasets/fixtures:** a committed `.env.example`-style snippet (no real secrets); flag state
  is an in-memory dict.
- **APIs & cost:** none — offline; the LLM "planner" behind the flag is a mock callable.
- **You'll be able to:** stand up typed config + a composition root and ship a change dark,
  rolling it out (and back) by percentage.

### 28-03 · `28-03-operational-contract-and-enterprise-must-haves.ipynb` — Health, graceful shutdown, multi-tenancy, audit
- **Type:** concept-lab
- **Maps to:** §28.6 (CQRS/event sourcing — when they help/hurt), §28.7 (multi-tenancy, audit
  logging, soft deletes), §28.8 (health checks, graceful shutdown, the operational contract)
- **Objective:** implement the small, non-negotiable operability surface — liveness vs
  readiness, graceful drain, a centralized tenant filter and append-only audit log — and feel
  why these cross-cutting rules belong in *one* place.
- **Prereqs:** 28-02; Ch 14 (checkpointing) referenced for shutdown.
- **Cell arc:**
  - 🧠 liveness ("am I alive?") vs readiness ("am I ready for traffic?" — deps connected).
  - Build `/healthz` (cheap) and `/readyz` (checks a dependency, e.g. a mock `SELECT 1`).
  - Simulate graceful shutdown: on a termination signal, stop accepting new work, drain
    in-flight tasks, flush/close — show a request *not* dropped vs a hard kill that drops it.
  - 🔮 *predict*: a worker is killed mid-agent-run with vs without per-step checkpointing —
    which one resumes? (ties to Ch 14).
  - Multi-tenancy: a `tenant_id`-scoped base query enforced in *one* helper; show how a single
    missing filter would leak across tenants, then make the scoped path the default.
  - Append-only audit log (who/what/when) distinct from debug logs; soft delete via
    `deleted_at` + the must-exclude-from-queries gotcha and honoring real deletion requests.
  - ⚠️ pitfall: CQRS/event sourcing are seductive and over-applied — list the moving parts
    (projections, eventual consistency between sides, event-schema evolution) you pay for
    forever; plain CRUD on Postgres is usually right.
  - 🎯 senior lens: the failure mode is 49/50 endpoints scoping by tenant and the 50th leaking
    everyone's data — centralize the rule and make it hard to bypass.
- **Datasets/fixtures:** in-memory rows tagged with `tenant_id`; a mock DB call for `/readyz`.
- **APIs & cost:** none — offline; "in-flight work" is simulated with `asyncio.sleep` tasks.
- **You'll be able to:** expose a correct health/readiness contract, shut down without dropping
  work, and enforce tenancy/audit in a single, hard-to-bypass place.

## Feeds (cross-pillar)
- **Blueprint(s):** — (this chapter is structural; its patterns underpin
  [`blueprints/fastapi-agent-service/`](../../blueprints/fastapi-agent-service/) and the
  capstone `app/` layering rather than a standalone blueprint).
- **Template(s):** contributes the hexagonal layout, `Settings`, and composition-root pattern
  to [`templates/fastapi-agent-service/`](../../templates/fastapi-agent-service/) and
  [`templates/agent-project-starter/`](../../templates/agent-project-starter/).
- **Capstone:** defines the *shape* of `capstone-project/app/` (ports/adapters, `core/` domain,
  `Settings`, DI composition root, `/healthz` + `/readyz`, graceful shutdown); checkpoint
  `checkpoints/ch28-app-architecture`.

## Dependencies
- Ch 4 (typing, `Protocol`, async) · Ch 27 (architecture styles, quality attributes, ADRs).
  Ch 14 (checkpointing) is referenced for graceful shutdown. Ch 25 (FastAPI) precedes the real
  service in the capstone; these notebooks isolate the *patterns* framework-free.

## Phase-2 definition of done
- [ ] All three notebooks run top-to-bottom in `MOCK=1` with no errors and fully offline.
- [ ] Port/adapter, `Settings`, DI factories, flags, and health-probe shapes match the book's
  §28 code (and the planner/flag calls are mock callables, not live).
- [ ] Each ends with recap + exercises and links to the `fastapi-agent-service` template and
  the capstone `app/` layout.
- [ ] Secrets read from env only; no `.env` or keys in committed outputs.
