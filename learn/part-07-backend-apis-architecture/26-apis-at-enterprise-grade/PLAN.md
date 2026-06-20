# Ch 26 — APIs at Enterprise Grade

> Companion plan · Part VII · book file `chapters/26-apis-at-enterprise-grade.typ`
> Status: 📋 planned (Phase 1)

## Role in the companion
A working endpoint is the easy 80%; this chapter is the hard, valuable 20% that turns an API
into something a business can expose to paying customers — auth, rate limiting, versioned
contracts, sane errors, webhooks. The notebooks are walkthroughs that *enforce* these concerns
on the Ch 25 service: the reader adds OAuth2/JWT auth and RBAC, gets rate-limited with a real
`429 + Retry-After`, and stands up a signed, retried, idempotent webhook. These are the
controls a reviewer will (rightly) block a PR over, so the reader builds them once, correctly.

## Planned notebooks

### 26-01 · `26-01-authn-authz-oauth2-jwt-rbac.ipynb` — Who are you, and what may you do
- **Type:** walkthrough
- **Maps to:** book §26.2 (authentication and authorization)
- **Objective:** secure endpoints with bearer JWTs (authn as a `Depends`) and enforce RBAC /
  per-resource ownership (authz) in *one* place — and reproduce, then close, the OWASP
  broken-object-level-authorization hole.
- **Prereqs:** Ch 25 (FastAPI, `Depends`); Ch 24 (`401`/`403` semantics).
- **Cell arc:**
  - 🧠 authn (*who are you?*) vs authz (*what may you do?*) — two questions constantly
    confused; both must be enforced consistently.
  - 🔧 mint and verify a JWT locally (HS256, a test secret from env); a `current_user`
    dependency that decodes claims and raises `401` on a bad/expired token — the book's
    `HTTPBearer` shape.
  - Walk the OAuth2 / OIDC authorization-code flow as a *diagram + mocked token exchange* (no
    live IdP); show where the JWT comes from in "log in with…".
  - 🔧 RBAC: a role claim gates an admin-only route (`403` for non-admins).
  - ⚠️ pitfall (the dangerous one): the *missing* object-level check — user A reads user B's
    resource by changing an id in the URL. 🔮 *predict* the result before the fix, then
    centralize the ownership/tenant check so it's the default, not per-endpoint memory.
  - 🎯 senior lens: JWT (stateless, hard to revoke) vs server-side sessions (central control,
    easy revocation) — pick by your revocation needs.
- **Datasets/fixtures:** a tiny in-memory users/roles table + sample owned resources in `data/`.
- **APIs & cost:** none/offline — JWTs signed/verified locally; OAuth2 exchange is mocked. No
  model calls, no live IdP.
- **You'll be able to:** add token auth and role/ownership checks to a FastAPI service and spot
  the broken-object-authorization bug on sight.

### 26-02 · `26-02-rate-limiting-quotas-errors-pagination.ipynb` — Self-protection & API conventions
- **Type:** walkthrough
- **Maps to:** book §26.3 (rate limiting, quotas, multi-tenancy), §26.4 (pagination, filtering,
  errors)
- **Objective:** make the API defend itself and behave predictably — per-tenant rate limits in
  shared state, structured errors, and cursor pagination — the conventions a consumer can rely on.
- **Prereqs:** 26-01.
- **Cell arc:**
  - 🧠 public APIs must protect themselves; cost-control is acute when each request triggers an
    expensive model call.
  - 🔧 a sliding-window / token-bucket limiter keyed by API key + user + *tenant*, backed by a
    **fakeredis** (or in-memory) store so limits hold "across instances" without a live Redis.
  - 🔮 *predict* the response when the window is exceeded → `429 Too Many Requests` with a
    `Retry-After` header; have a mock client honor it and back off.
  - Distinguish rate limits (per short window) from quotas (per day / per plan); show a
    per-tenant quota counter.
  - 🔧 a consistent structured error envelope (`{ "error": { "code", "message", "retry_after" }}`)
    via an exception handler — clients handle codes, not prose.
  - 🔧 cursor-based pagination over a list endpoint; contrast with offset on a changing dataset;
    ⚠️ pitfall: returning an *unbounded* list — always paginate.
  - 🎯 senior lens: pick conventions *once* (pagination style, error shape, snake_case,
    ISO-8601 UTC) and apply everywhere — inconsistency is a tax every client pays forever.
- **Datasets/fixtures:** a generated list (e.g. 200 synthetic messages) to paginate; in-memory
  tenant/quota counters.
- **APIs & cost:** none/offline — limiter on fakeredis/in-memory; no model calls.
- **You'll be able to:** rate-limit per tenant with correct `429`/`Retry-After`, return
  structured errors, and paginate safely.

### 26-03 · `26-03-webhooks-and-openapi-contracts.ipynb` — Outbound events + contract testing
- **Type:** walkthrough
- **Maps to:** book §26.5 (OpenAPI, contract testing, SDKs), §26.6 (webhooks and event-driven
  APIs)
- **Objective:** notify other systems reliably (signed, retried, idempotent webhooks) and use
  the auto-generated OpenAPI spec as the single source of truth for contract tests.
- **Prereqs:** 26-02; Ch 24 (idempotency); foreshadows Ch 29 (retries/at-least-once) and Ch 31
  (n8n automations consuming events).
- **Cell arc:**
  - 🧠 not every interaction is request→response; sometimes *your* system must notify *theirs*
    when a long agent run finishes — that's a webhook (`POST` to a registered URL).
  - 🔧 sign a webhook payload with an HMAC; a mock receiver verifies the signature and rejects
    a tampered body — trust that it came from you.
  - 🔧 deliver with retry + backoff to a flaky mock receiver (fails twice, then succeeds) —
    at-least-once delivery; 🔮 *predict* how many attempts before success.
  - ⚠️ pitfall: a non-idempotent *consumer* — you *will* receive duplicates; make the handler
    idempotent (reuse the Ch 24 idempotency key) so a redelivered event is harmless.
  - 🔧 dump FastAPI's generated `openapi.json`; write a tiny **contract test** that fails when a
    field is renamed/removed — catch breaking changes in CI before they ship (and the basis for
    generated SDKs).
  - 🎯 senior lens: treat outbound events with the same rigor as the inbound API — retried,
    signed, idempotent, versioned; that rigor is the difference between trust and silently
    dropped events.
- **Datasets/fixtures:** a saved OpenAPI snapshot + a sample webhook event payload in `data/`.
- **APIs & cost:** none/offline — receiver and delivery loop are in-process mocks; no model,
  no real outbound HTTP.
- **You'll be able to:** ship signed, retried, idempotent webhooks and gate API changes with a
  contract test against the OpenAPI spec.

## Feeds (cross-pillar)
- **Blueprint(s):** the auth/rate-limit/error-envelope middleware here is the enterprise layer
  studied in [`blueprints/observability-stack/`](../../../blueprints/observability-stack/)
  (structured errors + request context feed tracing).
- **Template(s):** hardens
  [`templates/fastapi-agent-service/`](../../../templates/fastapi-agent-service/) — auth
  dependency, rate-limit middleware, error envelope, and webhook sender become its production
  defaults.
- **Capstone:** wraps `capstone/app/` with the enterprise concerns (auth, per-tenant limits,
  signed webhooks); checkpoint `checkpoints/ch26-enterprise-api`. Webhooks connect to
  `capstone/workers/` automations (Ch 31).

## Dependencies
- Ch 25 (the FastAPI service these notebooks harden) · Ch 24 (status codes, idempotency).
  Ch 28 (multi-tenancy) and Ch 29 (retries/at-least-once) are referenced forward.

## Phase-2 definition of done
- [ ] All three notebooks run top-to-bottom in `MOCK=1` with no errors and **no live IdP,
      Redis, or outbound HTTP** (mocked/fakeredis/in-process throughout).
- [ ] JWT/`Depends` shapes, the `429`+`Retry-After` behavior, the error envelope, and the
      webhook (sign + retry + idempotent) match the book's §26 code.
- [ ] Each notebook ends with recap + exercises and links to
      `templates/fastapi-agent-service/` and `capstone/app/`.
- [ ] No secrets in outputs; JWT secret and HMAC key read from env only.
