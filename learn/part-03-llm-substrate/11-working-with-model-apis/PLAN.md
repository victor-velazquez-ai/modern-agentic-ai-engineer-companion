# Ch 11 — Working with Model APIs

> Companion plan · Part III · book file `chapters/11-working-with-model-apis.typ`
> Status: 📋 planned (Phase 1)

## Role in the companion
Everything in Part III reaches production through one HTTPS call — and this chapter engineers that
call as the external dependency it is. The notebooks make the SDK shape concrete (messages, stop
reason, usage), drill the resilience layer (error taxonomy, backoff-with-jitter, idempotency for
ambiguous timeouts), and exploit the two biggest cost levers (prompt caching, batch APIs). It all
converges on the chapter's 🔧 Build — the single-door `LLMClient` — which graduates into the
[`blueprints/llm-gateway/`](../../../blueprints/llm-gateway/) blueprint and the capstone's `llm/`.

## Planned notebooks

### 11-01 · `11-01-sdk-shapes-and-the-response.ipynb` — The common API shape: messages, stop reason, usage
- **Type:** walkthrough
- **Maps to:** book §11.1 (provider SDKs and the common shape), §11.2 (tool calling at the API
  level, lightly), §11.3 (multimodal inputs)
- **Objective:** read a model response correctly — branch on `stop_reason`, log `usage` — and see
  that Anthropic vs OpenAI differ mostly in dialect, not anatomy.
- **Prereqs:** Ch 8–10; `learn/part-03-llm-substrate/10-*`.
- **Cell arc:**
  - 🧠 mental model: every chat API is the same anatomy — POST model id + role-tagged messages +
    params (+ tools); get back content, a *stop reason*, and token *usage*.
  - Make a minimal Anthropic `messages.create(...)` call (mock); read `msg.content[0].text`,
    `msg.stop_reason`, `msg.usage`. Show the OpenAI dialect side-by-side (system in the list;
    `finish_reason`; the chat shape as a de-facto lingua franca for open-model servers).
  - 🔮 *predict* the stop reason when output is cut by `max_tokens` — then show silent truncation and
    why correct code *branches* on stop reason (natural / max_tokens / tool_use / filter).
  - Anthropic content as a *list of typed blocks* (text, tool_use, image) vs a single string — why
    that shape pays off going multimodal/agentic.
  - Multimodal (§11.3): build an image+text content list; note images are tokens too (a hi-res image
    ≈ 1000+ tokens) — downscale to the task and don't re-send static images each loop.
  - 🎯 senior lens: never scatter raw SDK calls — route every call through one internal client so
    retries/timeouts/usage/caching/model-selection live in one place (the seed of 11-03).
  - ⚠️ pitfall: ignoring `stop_reason` and shipping truncated output as if it were complete.
- **Datasets/fixtures:** `data/` — one tiny downscaled PNG for the multimodal cell (small, committed).
- **APIs & cost:** mockable — `MOCK=1` returns canned message objects (text + a typed-block example +
  a vision answer); `MOCK=0` ≈ 2 short calls, one with an image (image tokens flagged).
- **You'll be able to:** parse any provider's response and handle truncation, tools, and images.

### 11-02 · `11-02-resilience-retries-and-idempotency.ipynb` — Error taxonomy, backoff, idempotent tools
- **Type:** walkthrough
- **Maps to:** book §11.4 (rate limits, retries, and error taxonomies)
- **Objective:** build retry logic that retries only what's retryable, backs off with jitter, honors
  `retry-after`, and survives an ambiguous timeout without double side effects.
- **Prereqs:** 11-01.
- **Cell arc:**
  - 🧠 mental model: the API fails in categories; the *retryable column is the whole game* —
    retrying a 400 wastes quota, failing hard on a 429 turns a blip into an outage.
  - Walk the taxonomy table (400/401/403/404/413 → don't retry; 429/500/529/503 → retry with
    backoff; timeout → *outcome unknown*, retry carefully).
  - Implement `with_retries(...)`: exponential backoff **with jitter** over a retryable-error tuple;
    cap attempts; honor `retry-after`/quota headers (rate limits come in RPM *and* TPM at once).
  - 🔮 *predict* what happens when a *tool-executing* turn times out and you blindly retry — then
    show the danger: the email/refund already fired. Fix: **idempotency keys** so a replayed turn is
    harmless (the Ch 29 distributed-systems pattern, applied to tools).
  - Note the SDKs already retry a couple of times — configure `max_retries`/timeouts rather than
    stacking blind loops.
  - 🎯 senior lens: backoff alone can't survive sustained overload — add a client-side concurrency
    cap (semaphore), a shed/defer queue (Ch 31), and a circuit breaker that fails fast (Ch 26).
  - ⚠️ pitfall: a retry loop that hammers a failing endpoint (no jitter, no cap, retries 4xx) —
    turning a blip into a self-inflicted outage.
- **Datasets/fixtures:** none — a mock transport that raises 429/500/timeout on a schedule to drive
  the retry path deterministically (no real API needed).
- **APIs & cost:** offline/mock by default (the fake transport exercises every branch free); `MOCK=0`
  is optional and not required to learn the lesson.
- **You'll be able to:** write production retry logic and make side-effecting tools safe to replay.

### 11-03 · `11-03-caching-batching-and-the-llm-client.ipynb` — 🔧 Caching, batching & the single-door `LLMClient`
- **Type:** walkthrough  *(this is the chapter's 🔧 Build: the `LLMClient`)*
- **Maps to:** book §11.5 (prompt caching, batching, cost control), §11.6 (provider features worth
  knowing), §11.7 (the `LLMClient` 🔧 Build)
- **Objective:** cut the two biggest agent costs (prompt caching, batch APIs) and assemble the one
  internal client every model call flows through.
- **Prereqs:** 11-01, 11-02.
- **Cell arc:**
  - 🧠 mental model: two API primitives exploit structure you already have — caching attacks
    repetition *within* a workload; batching attacks work that *doesn't need an answer now*.
  - **Prompt caching**: set a `cache_control` breakpoint after a stable system prefix; read
    `cache_creation_input_tokens` / `cache_read_input_tokens` from `usage`; 🔮 *predict* the hit on
    the 2nd loop iteration vs the 1st. The prerequisite is Ch 10's layout: *stable prefix first,
    volatile last* — any change invalidates the cache from that point (and providers differ:
    explicit breakpoints vs automatic prefix caching).
  - **Batch APIs**: model an async batch submit/collect at ~half price for offline work (embedding
    backfills, nightly classification, bulk evals — Ch 22; the capstone's ingestion via Celery,
    Ch 31). "Paying real-time prices for work that tolerates hours = donating margin."
  - Provider features survey (§11.6): grounded **citations** API, **server-side hosted tools**
    (web search / code exec), differing **cache semantics**, and **reasoning-block round-tripping**
    (echo thinking blocks back on the next turn or multi-step reasoning silently degrades).
  - 🔧 build the `LLMClient`: one `async call(task, *, messages, tools, **params)` that resolves
    model tier + cached system prefix + params from the prompt registry (Ch 10), wraps the SDK call
    in a limiter (semaphore + circuit breaker), and records `usage`/`stop_reason` to metrics — *no
    caller knows which provider answered.*
  - 🎯 senior lens: treat cost as a quality attribute (Ch 27) — you must be able to answer "what does
    one agent run cost, and what drives it?" from logs; caching, batching, routing, and call-count
    reduction are the four standing levers. Per-provider quirks (citations, hosted tools, cache
    breakpoints, reasoning blocks) belong in *one* adapter behind a stable interface.
  - ⚠️ pitfall: letting a timestamp or per-request id sneak into the cacheable prefix — it
    invalidates the cache on every call and you pay full prefill silently.
- **Datasets/fixtures:** reuse a long static system prompt as the cacheable prefix; a small list of
  fake "offline" requests for the batch demo.
- **APIs & cost:** mockable — `MOCK=1` returns `usage` objects with synthetic cache-hit fields and a
  canned batch result so cost math runs offline; `MOCK=0` exercises real caching on a multi-turn run
  (cache read/create tokens flagged; batch left as an optional gated cell).
- **You'll be able to:** instrument cache hit rate, route offline work to batch, and stand up the
  single-door client Part IV's agents are built on.

## Feeds (cross-pillar)
- **Blueprint(s):** the 🔧 `LLMClient` graduates into
  [`blueprints/llm-gateway/`](../../../blueprints/llm-gateway/) — the production wrapper (retries,
  timeouts, usage logging, prompt caching, model routing, circuit breaker). 11-03 ends pointing here.
- **Template(s):** the client and `.env`-based key handling seed
  [`templates/agent-project-starter/`](../../../templates/agent-project-starter/)'s LLM-access layer.
- **Capstone:** advances the capstone `llm/` package — `LLMClient` is the *only door to model APIs*
  in the platform; Part IV's agents (`agents/`) are built entirely on top of it; checkpoint
  `checkpoints/ch11-llm-client`.

## Dependencies
- Ch 10 (the versioned prompt registry the client resolves config from; stable-prefix layout for
  caching) · `learn/part-03-llm-substrate/10-*`. Ch 9 supplies streaming + usage habits. Forward:
  Ch 12 (tool design/execution/failures builds on the API-level tool protocol), Ch 26 (full
  resilience patterns), Ch 29 (idempotency), Ch 31 (batch/Celery).

## Phase-2 definition of done
- [ ] All three notebooks run top-to-bottom in `MOCK=1` with no errors (response parsing, the full
      retry/idempotency path via the fake transport, caching usage fields, and the `LLMClient`).
- [ ] SDK shapes, the error taxonomy + backoff code, caching/`cache_control` usage, and the
      `LLMClient` signature match the book's §11.
- [ ] Each notebook ends with recap + exercises; 11-03 ends pointing at `blueprints/llm-gateway/`.
- [ ] Secrets from env only; live token/caching costs documented; the fake-transport retry demo is
      fully offline.
