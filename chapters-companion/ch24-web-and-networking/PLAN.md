# Ch 24 — The Web & Networking You Must Know

> Companion plan · Part VII · book file `chapters/24-web-and-networking.typ`
> Status: 📋 planned (Phase 1)

## Role in the companion
Part VII builds the backend, and this chapter is its foundation: the working model of how a
request actually travels and what HTTP guarantees. The notebooks make that model *tangible* —
the reader runs a request lifecycle, *sees* idempotency save them from a double-charge, and
watches versioning break (or not) a client — so that when they build the FastAPI service in
Ch 25 the contracts and retry-safety habits are already in their fingers. Pure concept-labs,
mostly offline; no production service is built here.

## Planned notebooks

### 24-01 · `24-01-http-and-idempotency.ipynb` — HTTP semantics & retry-safety, run
- **Type:** concept-lab
- **Maps to:** book §24.1 (HTTP, REST, status codes, and idempotency)
- **Objective:** read and reason about a real request/response, and prove to yourself which
  operations are safe to retry by building a tiny idempotency-keyed handler that ignores
  duplicate `POST`s.
- **Prereqs:** none beyond Python; Ch 24 read. (Foreshadows Ch 29 idempotency keys.)
- **Cell arc:**
  - 🧠 mental model: request = method + path + headers + body; response = status + headers +
    body; methods are a *contract*, not a hint.
  - Build a 3-route in-process app (a plain WSGI/ASGI callable or a dict-dispatch stub) for
    `GET`/`POST`/`PUT`; inspect the raw request and response objects.
  - Map the status-code table (2xx/3xx/4xx/5xx) to outcomes; 🔮 *predict* the status for a
    bad body before running the validation path (expect `422`), a missing resource (`404`),
    a duplicate create (`409`).
  - 🔧 add an in-memory **idempotency key** store; replay the same `POST` twice and watch the
    second be recognized and ignored (one resource, not two).
  - ⚠️ pitfall: retrying a non-idempotent `POST` blindly → "charged twice / sent two emails";
    contrast `GET`/`PUT`/`DELETE` (idempotent by definition) with bare `POST`.
  - 🎯 senior lens: *every* networked call is eventually retried by something — design write
    endpoints retry-safe from day one (the §24.1 key idea).
- **Datasets/fixtures:** none — in-memory resources (a tiny `messages` dict).
- **APIs & cost:** none/offline — no model, no network egress; fully deterministic.
- **You'll be able to:** choose correct status codes and methods, and make a create endpoint
  safe under retry with an idempotency key.

### 24-02 · `24-02-request-lifecycle-and-versioning.ipynb` — DNS→TLS→LB lifecycle + API versioning
- **Type:** concept-lab
- **Maps to:** book §24.2 (TLS, DNS, load balancing, request lifecycle), §24.3 (serialization,
  content types, API versioning)
- **Objective:** trace one HTTPS request through DNS → TLS → load balancer → app server, name
  the cost at each hop, and demonstrate why statelessness enables horizontal scaling.
- **Prereqs:** 24-01.
- **Cell arc:**
  - 🧠 walk the request-lifecycle diagram (mirror the book's figure) hop by hop; print a
    labeled trace with a synthetic latency budget for each stage.
  - Simulate DNS caching and a stale record → "down for some users" (no real resolver; a
    mocked cache with TTL) to make the classic incident concrete.
  - 🔧 a toy round-robin **load balancer** over N identical "servers"; show requests spread.
  - 🔮 *predict* what breaks when one server keeps session state *in memory*, then route the
    same client to a different server and watch the state be missing — the case for statelessness.
  - Serialize the same object to JSON vs a compact binary form; compare size/legibility
    (`Content-Type` announces which) — foreshadows gRPC/protobuf in Ch 26.
  - 🔧 version an endpoint: `/v1/...` vs `/v2/...`; add an *optional* field (non-breaking) and
    then rename one (breaking) and watch a pinned client fail.
  - ⚠️ pitfall: a breaking change to an *unversioned* API silently breaks every integration;
    treat the published shape as immutable — add, never mutate/remove without a new version.
- **Datasets/fixtures:** none — synthetic latency numbers + an in-memory object to serialize.
- **APIs & cost:** none/offline — DNS/TLS/LB are *simulated*, no real sockets or certs.
- **You'll be able to:** explain where request latency goes, justify statelessness behind a
  load balancer, and evolve an API without breaking clients.

## Feeds (cross-pillar)
- **Blueprint(s):** — (conceptual foundation; the retry-safety pattern recurs in
  [`blueprints/observability-stack/`](../../blueprints/observability-stack/) tracing and in
  Ch 29 distributed-systems labs).
- **Template(s):** establishes the HTTP/versioning conventions that
  [`templates/fastapi-agent-service/`](../../templates/fastapi-agent-service/) bakes in.
- **Capstone:** no code yet — these are the contracts the capstone `app/` (Ch 25) will honor
  (status codes, idempotent `POST /runs`, `/v1` surface).

## Dependencies
- None hard. Pairs with Ch 4 (async/concurrency mental model) and is the prerequisite for the
  rest of Part VII (Ch 25–31).

## Phase-2 definition of done
- [ ] Both notebooks run top-to-bottom in `MOCK=1` (here: fully offline) with no errors.
- [ ] Status-code usage, the idempotency-key shape, and the lifecycle stages match the book's
      §24 terminology and figure.
- [ ] Each notebook ends with a recap + 2–4 exercises (e.g., "add a `DELETE`; is it
      idempotent?", "version a field rename safely").
- [ ] No secrets, no live network; cross-links to Ch 25/26/29 and the templates resolve.
