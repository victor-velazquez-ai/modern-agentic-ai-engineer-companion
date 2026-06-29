# Ch 25 — Building APIs with FastAPI

> Companion plan · Part VII · book file `chapters/25-building-apis-with-fastapi.typ`
> Status: 📋 planned (Phase 1)

## Role in the companion
This is where the backend becomes real. FastAPI is the capstone's API backbone, and the
chapter's 🔧 Build (§25.5) stands up its public surface. The notebooks take the reader from a
first typed endpoint to a *streaming, async* agent API — the move that makes an agent feel
alive instead of frozen behind a spinner. The walkthroughs end by pointing at the production
scaffold (`templates/fastapi-agent-service/`) and the capstone's `app/`: you build the toy
here, then study/lift the real one.

## Planned notebooks

### 25-01 · `25-01-fastapi-from-zero.ipynb` — Typed endpoints, async, lifespan
- **Type:** walkthrough
- **Maps to:** book §25.1 (FastAPI from zero), §25.2 (async endpoints, background tasks,
  lifespans)
- **Objective:** build a validated, self-documenting endpoint from Pydantic models, run it
  with the test client, and manage shared resources with a lifespan hook.
- **Prereqs:** Ch 24 (HTTP semantics, status codes); Ch 4 (async); Ch 15 (Pydantic/structured
  outputs) helpful.
- **Cell arc:**
  - 🧠 the one habit: *declare your types, FastAPI does the rest* (validation, serialization,
    OpenAPI) — the `AskRequest`/`AskResponse` shape from the book.
  - 🔧 build `POST /ask` returning a `response_model`; drive it with `TestClient` (no live
    server, no ports) and read the generated `/openapi.json`.
  - 🔮 *predict* the status for a malformed body before sending it → see the clean `422` with
    field-level detail.
  - Add a `Depends`-injected dependency (a fake "current settings"/service) to keep the
    handler thin and testable (full DI lands in Ch 28).
  - 🔧 a `lifespan` that opens/closes a shared pool *once per process*; print startup/shutdown
    order to prove it's not per-request.
  - ⚠️ pitfall (the chapter's #1 perf bug): a *blocking* call inside an `async def` handler
    freezes the whole event loop — demonstrate with a `time.sleep` vs `await asyncio.sleep`
    timing under concurrent requests; fix via `run_in_threadpool`.
  - 🎯 senior lens: `BackgroundTasks` (in-process, fire-and-forget) vs enqueue-to-Celery
    (durable, survives a crash) — when each is correct (Ch 31).
- **Datasets/fixtures:** none — a mocked `run_agent` returning a canned answer in `MOCK=1`.
- **APIs & cost:** mockable — agent call is stubbed by default; live ≈ 1 short model call if
  `MOCK=0`. Server never binds a port (TestClient/ASGI in-process).
- **You'll be able to:** stand up a typed, async FastAPI endpoint with proper resource
  lifecycle and avoid the event-loop-blocking trap.

### 25-02 · `25-02-streaming-sse-and-websockets.ipynb` — Stream tokens & agent events; two-way WS
- **Type:** walkthrough
- **Maps to:** book §25.3 (streaming responses & Server-Sent Events), §25.4 (WebSockets)
- **Objective:** stream an LLM/agent's output to the client — first one-way via SSE (tokens
  *and* structured progress events), then two-way via WebSockets for an interruptible agent.
- **Prereqs:** 25-01.
- **Cell arc:**
  - 🧠 why streaming: latency you can *see* progressing beats latency you can't — the UX move
    that makes an agent feel trustworthy.
  - 🔧 `StreamingResponse` with `media_type="text/event-stream"`; an async generator yielding
    `data: …\n\n` SSE frames over a mocked token stream, terminated by `[DONE]`.
  - 🔧 stream *structured events* not just tokens — "calling tool X", "retrieved 5 sources",
    "step 3/8", then answer tokens — exactly what the Ch 38 frontend renders.
  - 🔮 *predict* what the client sees if the generator raises mid-stream; then handle it (emit
    an error frame, close cleanly) — partial-output hygiene.
  - 🔧 a `@app.websocket` echo-then-stream handler: `iter_text()` in, `send_json(event)` out;
    show the client pushing a "stop" message mid-run (the upstream channel SSE can't give you).
  - ⚠️ pitfall: reaching for WebSockets when SSE suffices — added complexity (connection
    lifecycle, reconnection) you only pay for when the client must push mid-stream.
  - 🎯 senior lens: choose deliberately — SSE for most chat output, WebSockets only for
    interruptible/interactive/collaborative sessions.
- **Datasets/fixtures:** a tiny scripted event/token sequence in `data/` (or generated) so the
  stream is deterministic in CI.
- **APIs & cost:** mockable — token stream is canned by default; live ≈ 1 streamed completion
  if `MOCK=0`. WebSocket exercised via the ASGI test client, no real socket server.
- **You'll be able to:** stream model tokens and structured agent progress over SSE, and run a
  two-way WebSocket session for a steerable agent.

### 25-03 · `25-03-capstone-backend-api.ipynb` — 🔧 Build the capstone's API surface
- **Type:** walkthrough  *(this is the chapter's 🔧 Build, §25.5)*
- **Maps to:** book §25.5 (Build: the capstone backend API)
- **Objective:** assemble the capstone's small, *thin* public surface — validate-and-dispatch
  in milliseconds, push the slow stateful work behind a queue, stream progress back.
- **Prereqs:** 25-01, 25-02. (Celery worker is *mocked* here; the real one is Ch 31.)
- **Cell arc:**
  - 🧠 the pattern to internalize: thin async streaming API in front, durable workers behind.
  - 🔧 build the routes from the book: `POST /runs` (enqueue, return `run_id`, `201`),
    `GET /runs/{id}` (status + result), `GET /runs/{id}/stream` (SSE progress),
    `POST /ask` (sync quick answer), `GET /healthz` + `GET /readyz` (the Ch 28 probes).
  - Replace the real `run_agent.delay(...)` with a mock task queue (an in-memory job dict +
    background task) so the whole flow runs offline and deterministically.
  - 🔮 *predict* the immediate response of `POST /runs` (queued, not the answer) vs `POST /ask`
    (the answer) — internalize sync-vs-async dispatch.
  - Drive the full lifecycle end-to-end: start a run → poll status → subscribe to the SSE
    stream → see it finish; assert `201`/`200`/event order.
  - ⚠️ pitfall: doing the heavy agent work *inside* the request handler — show how it stalls
    concurrent requests; the queue is what keeps the API thin.
  - 🎯 senior lens: idempotent `POST /runs` (reuse the Ch 24 idempotency key) so a retried
    "start" doesn't launch two runs — retry-safety meets the real endpoint.
  - 📋 ends by pointing at `templates/fastapi-agent-service/` (the scaffold) and
    `capstone-project/app/` (the production version): "you built the toy; here's the real one."
- **Datasets/fixtures:** in-memory run store + a scripted progress-event sequence (committed
  small in `data/`).
- **APIs & cost:** mockable — agent + queue stubbed by default; live ≈ a short run if
  `MOCK=0`. No external broker/Redis required (mock queue).
- **You'll be able to:** stand up the capstone's real API surface — thin, async, streaming —
  with the queue boundary in the right place.

## Feeds (cross-pillar)
- **Blueprint(s):** consumes the agent loop from
  [`blueprints/agent-loop/`](../../blueprints/agent-loop/) behind `run_agent`/`stream_agent`.
- **Template(s):** **primary contributor** to
  [`templates/fastapi-agent-service/`](../../templates/fastapi-agent-service/) — the
  production scaffold of everything these notebooks build (typed routes, lifespan, SSE,
  health probes); each walkthrough ends by pointing here.
- **Capstone:** builds `capstone-project/app/` (the API surface from §25.5); checkpoint
  `checkpoints/ch25-backend-api`. The queue handoff lands fully in Ch 31 (`capstone-project/workers/`).

## Dependencies
- Ch 24 (HTTP, status codes, idempotency) · Ch 4 (async) · Ch 15 (Pydantic). Ch 28 (DI,
  health probes) and Ch 31 (Celery) are *referenced forward* — mocked here, real there.

## Phase-2 definition of done
- [ ] All three notebooks run top-to-bottom in `MOCK=1` with no errors and **no bound port /
      no external broker** (TestClient/ASGI in-process; mock queue).
- [ ] Endpoint names, status codes, the SSE frame shape, and the thin-API/durable-worker split
      match the book's §25 code exactly.
- [ ] Each notebook ends with recap + exercises and links to
      `templates/fastapi-agent-service/` and `capstone-project/app/`.
- [ ] Secrets from env only; canned token/event streams are realistic; no live spend by default.
