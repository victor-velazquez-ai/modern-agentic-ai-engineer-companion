# Part VII — Backend, APIs & Software Architecture

> Companion to **Modern Agentic AI Engineer**, Part VII · book chapters 24–31
> Status: 📋 planned (Phase 1)

## Companion emphasis

This is **deliberately the heaviest part of the book and of this companion** — eight chapters
that turn an agent into a *system*: how requests travel, how to build and harden the API,
how to architect the whole thing, and how to make it distributed, persistent, and automated.
It's heavy on purpose. An agent that runs in a notebook is a demo; the gap between that and a
backend a business can expose to paying customers is exactly the work that pays senior salaries,
and it lives here.

Two through-lines run the length of the part:

- **The capstone backend gets built and hardened.** Ch 25 stands up the API surface
  (`capstone-project/app/`), Ch 26 makes it enterprise-grade (auth, limits, webhooks), Ch 28 shapes its
  internals (hexagonal, DI, multi-tenancy), Ch 30 gives it a real data layer, and Ch 31 puts the
  slow work behind durable workers (`capstone-project/workers/`). Most chapters end by pointing at
  [`templates/fastapi-agent-service/`](../../templates/fastapi-agent-service/) — the production
  scaffold — and the matching `capstone-project/` checkpoint: *build the toy here, study/lift the real one.*
- **Architectural judgment is the durable human edge.** Ch 27 is the spine: when models generate
  the code, deciding *what* to build, *where the boundaries go*, and *which trade-offs fit this
  business* is the skill that's rising in value, not falling. Ch 29 (distributed-systems reality)
  and Ch 27/28 (styles, boundaries, ADRs) are where you build the muscles a model can't.
  Fittingly, the most code-light chapters here (27, parts of 29) are the most *senior*.

The companion honors that split: chapters about **building** (24–26, 30, 31) are walkthroughs
and concept-labs you run; chapters about **deciding** (27, and the design-heavy parts of 28–29)
lean on worksheets and simulations. Most networked behavior — DNS/TLS/load balancing,
rate-limiters, brokers, webhooks, distributed failures — is **simulated or mocked** so every
notebook runs free, offline, and deterministically in CI (`MOCK=1`), with a documented live path.

## Chapters

| Ch | Title | Companion emphasis | Plan |
|---|---|---|---|
| 24 | The Web & Networking You Must Know | Concept-labs — HTTP semantics & idempotency you can run; the DNS→TLS→LB request lifecycle and safe API versioning (offline). | [`24-web-and-networking/PLAN.md`](24-web-and-networking/PLAN.md) |
| 25 | Building APIs with FastAPI | Walkthroughs — typed async endpoints + lifespan; streaming via SSE & WebSockets; **🔧 Build (§25.5)** the capstone's thin API surface. | [`25-building-apis-with-fastapi/PLAN.md`](25-building-apis-with-fastapi/PLAN.md) |
| 26 | APIs at Enterprise Grade | Walkthroughs — OAuth2/JWT/RBAC authn-z, per-tenant rate limits (`429`/`Retry-After`), structured errors & pagination, signed/retried/idempotent webhooks + OpenAPI contract tests. | [`26-apis-at-enterprise-grade/PLAN.md`](26-apis-at-enterprise-grade/PLAN.md) |
| 27 | Software Architecture Fundamentals | **Concept-lab + worksheet (mostly no code, by design)** — rank the -ilities, run the trade-off method, write a real ADR + C4 sketch → `adr-template`, `system-design-doc`. The part's senior/architect core. | [`27-software-architecture-fundamentals/PLAN.md`](27-software-architecture-fundamentals/PLAN.md) |
| 28 | Application Architecture | Concept/walkthrough — hexagonal/ports-and-adapters, 12-factor, dependency injection, multi-tenancy & health probes. *(sibling-authored)* | [`28-application-architecture/PLAN.md`](28-application-architecture/PLAN.md) |
| 29 | Distributed Systems Fundamentals | Concept-labs — CAP, retries & backoff, idempotency keys, sagas (all *simulated*). *(sibling-authored)* | [`29-distributed-systems-fundamentals/PLAN.md`](29-distributed-systems-fundamentals/PLAN.md) |
| 30 | Data Layer | Walkthroughs — Postgres/pgvector, Redis caching, access patterns. *(sibling-authored)* | [`30-data-layer/PLAN.md`](30-data-layer/PLAN.md) |
| 31 | Distributed Backends & Automation | Walkthrough — Celery async runs + schedules, n8n automations → `capstone-project/workers/`. *(sibling-authored)* | [`31-distributed-backends-and-automation/PLAN.md`](31-distributed-backends-and-automation/PLAN.md) |

*Chapters 24–27 are planned in this pass; 28–31 are authored by the sibling agent and listed
here with their folder paths so the part index is complete.*

## Run order

Read and run in book order — the part builds cumulatively on one service:

`24` (the contracts: HTTP, idempotency, versioning) → `25` (build the FastAPI surface) →
`26` (harden it: auth, limits, webhooks) → `27` (step back: architect it — ADRs, -ilities,
boundaries) → `28` (shape its internals) → `29` (the distributed reality it must survive) →
`30` (give it a data layer) → `31` (move slow work to durable workers).

Ch 24's offline concept-labs are the recommended entry point; Ch 25's **🔧 Build (§25.5)** is the
first capstone backend milestone (`capstone-project/app/`, checkpoint `ch25-backend-api`). If you only
have time for one chapter's reflection, do **Ch 27** — its ADR + trade-off worksheet is the most
transferable hour in the part.
