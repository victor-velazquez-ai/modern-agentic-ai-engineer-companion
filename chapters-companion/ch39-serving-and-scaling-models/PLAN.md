# Ch 39 — Serving & Scaling Models

> Companion plan · Part X · book file `chapters/39-serving-and-scaling-models.typ`
> Status: 📋 planned (Phase 1)

## Role in the companion
Reading explains *why* a gateway and a serving stack matter; running makes the trade-offs
land. These notebooks build the **LLM gateway** the rest of Part X operates on — routing,
fallbacks, caching, cost tracking, provider independence — entirely in **MOCK mode** against
canned provider responses (no keys, no spend). A second, optional concept-lab makes the
serving internals (continuous batching, the KV-cache, quantization) tangible with a tiny
offline simulator, and flags real local-model paths (vLLM / TGI / Ollama) as ⚠️ heavy/optional
so the chapter still runs free on a laptop. This is where `blueprints/llm-gateway/` and
`capstone-project/llm/gateway.py` are born.

## Planned notebooks

### 39-01 · `39-01-llm-gateway-routing-and-fallbacks.ipynb` — 🔧 Build the gateway (mock mode)
- **Type:** walkthrough  *(the chapter's central 🔧 Build — the gateway component)*
- **Maps to:** book §39.9 (model routing, fallbacks & gateways — the LiteLLM-style chokepoint),
  with the reliability patterns it names (Ch 29 retries/fallback) and the isolate-what-changes
  framing (Ch 28).
- **Objective:** put *one* gateway in front of every model call that routes by task difficulty,
  fails over to a backup provider on error/timeout, and records cost — so swapping or mixing
  providers becomes config, not a code edit.
- **Prereqs:** Ch 11 / `blueprints/llm-gateway/` (SDK shapes, retries); Ch 29 (fallback,
  backpressure) read.
- **Cell arc:**
  - 🧠 mental model: the gateway as a single chokepoint — routing · fallback · caching · rate
    limiting · cost tracking · provider independence, all in one place (the book's gateway
    figure).
  - Define a provider-agnostic `complete()` interface and **two mock backends** (a "cheap" tier
    and a "frontier" tier) that return canned, realistic responses + usage — no network.
  - **Routing:** a difficulty signal (length / task tag) picks the tier; 🔮 *predict* which tier
    a batch of mixed prompts lands on, then read the routing log.
  - **Fallback:** make the primary backend raise/time out; watch the gateway retry on the backup
    and return a result — the Ch 29 pattern as config.
  - **Exact cache** in front of the call (hash request → cached response) so an identical request
    skips the model; deeper caching is Ch 40's job — link forward.
  - ⚠️ pitfall: a *too-aggressive router* sending hard tasks to the cheap tier — show a quality
    cliff and the guardrail (route on an evaluated signal, not a guess; Ch 22).
  - 🎯 senior lens: build/adopt the gateway *early* — a provider outage, price change, or new
    model becomes a config change instead of edits scattered across the codebase; it's
    hexagonal architecture (Ch 28) applied to the most volatile dependency, the model.
  - Close by pointing at `blueprints/llm-gateway/` (the production version: real providers,
    telemetry hooks, rate limits) and `capstone-project/llm/gateway.py`.
- **Datasets/fixtures:** a tiny in-notebook prompt set (mixed easy/hard) + canned per-backend
  responses with token-usage fields; no external data.
- **APIs & cost:** **none by default** — `MOCK=1` returns canned provider responses
  deterministically; `MOCK=0` would route to live providers (a handful of short calls) and is
  optional/documented.
- **You'll be able to:** stand up a routing+fallback+cost gateway every later chapter calls,
  and reason about provider independence as an architectural decision.

### 39-02 · `39-02-serving-internals-batching-kv-cache-quant.ipynb` — Why inference costs what it does
- **Type:** concept-lab
- **Maps to:** book §39.3 (throughput, batching, quantization, the KV-cache), §39.1–39.2
  (hosted vs self-host, the VRAM rule, vLLM/TGI/Ollama), §39.4 (speculative decoding),
  §39.8 (GPU autoscaling & cold starts) — at an intuition, not kernel, level.
- **Objective:** explain, from a tiny simulation, *why* long contexts cost more, why providers
  sell cheaper batch endpoints, and why a smaller/quantized model is cheaper and faster —
  understanding you can use even as a pure API consumer.
- **Prereqs:** 39-01; Ch 8 (how LLMs work) read.
- **Cell arc:**
  - 🧠 mental model: four levers explain most of inference performance — batching, the
    KV-cache, quantization, throughput-vs-latency.
  - **Batching simulator (offline):** a toy model of a GPU serving N requests one-at-a-time vs
    continuously batched; 🔮 *predict* the throughput multiple before revealing it.
  - **KV-cache memory model:** compute KV-cache size as a function of sequence length and show
    it, not the weights, capping concurrent requests → *this is why long contexts cost memory*.
  - **VRAM rule of thumb:** ~2 bytes/param at 16-bit → a 13B model needs ~26 GB for weights;
    quantize to 8-/4-bit and watch the footprint (and the small quality caveat) — fully arithmetic.
  - **Throughput vs latency:** vary batch size; see total tokens/sec rise while per-request
    latency rises — pick the knob per use case (chat = latency, batch job = throughput).
  - Concept-only tours (no execution): *speculative decoding* (draft proposes, target verifies;
    win depends on acceptance rate) and *GPU cold starts / warm floor* (scale-to-zero vs tail
    latency) — explained, with the book's pitfall that speculative *decoding* ≠ Ch 40's
    application-level speculative *execution*.
  - ⚠️ pitfall: assuming "self-host is cheaper" — re-run the book's TCO crossover (utilization,
    not sticker price, governs break-even) as a small spreadsheet-style cell with all numbers
    flagged as illustrative assumptions.
  - 🎯 senior lens: start hosted, instrument real token volume *and* realistic utilization, and
    revisit self-hosting with actual numbers — never architect a GPU fleet on day one.
- **Datasets/fixtures:** none — pure in-notebook arithmetic/simulation with seeded inputs.
- **APIs & cost:** **none** — fully offline by design.
- **⚠️ Optional local-model appendix (heavy/optional):** a clearly-flagged, **non-CI** section
  showing the *real* serving path — start `Ollama` (or vLLM/TGI) locally and hit its
  OpenAI-compatible endpoint *through the same gateway interface from 39-01* to prove "swap in
  your own server without touching application code." Skipped by default; needs a local GPU/CPU
  model pull; never runs in CI and incurs no cloud spend.
- **You'll be able to:** reason about serving cost/latency from first principles and explain
  every line of a provider's pricing page — without owning a GPU.

## Feeds (cross-pillar)
- **Blueprint(s):** **builds** [`blueprints/llm-gateway/`](../../blueprints/llm-gateway/) —
  the production gateway (routing, fallback, caching, rate limiting, cost tracking, hosted +
  self-hosted behind one interface); 39-01 ends pointing here. Builds on
  [`blueprints/llm-gateway/`](../../blueprints/llm-gateway/) (Ch 11) for the underlying SDK
  call shape, and exposes the hooks [`blueprints/observability-stack/`](../../blueprints/observability-stack/)
  (Ch 23) reads.
- **Template(s):** the gateway slots into [`templates/agent-project-starter/`](../../templates/agent-project-starter/)
  as the single model entry point new projects start from. (No new template here.)
- **Capstone:** **builds `capstone-project/llm/gateway.py`** — the platform's single model chokepoint
  that Ch 40 (cost/metering) and Ch 41 (guardrails, per-tenant limits) extend; checkpoint
  `checkpoints/ch39-serving-and-gateway`.

## Dependencies
- Ch 11 / `blueprints/llm-gateway/` (SDK shapes, retries) · Ch 28 (hexagonal / isolate what
  changes) · Ch 29 (fallback, backpressure) · Ch 35 (GPU vs CPU autoscaling, referenced).
  Forward: Ch 40 adds metering/caching/routing-for-cost *at this same gateway*; Ch 41 adds
  guardrails and per-tenant limits at it.

## Phase-2 definition of done
- [ ] Both notebooks run top-to-bottom in `MOCK=1` with no errors and **no network** (canned
      backends; offline simulators). The optional local-model section is ⚠️-flagged and excluded
      from CI.
- [ ] The gateway responsibilities (routing · fallback · caching · cost tracking · provider
      independence), the four serving levers, the VRAM rule, and the TCO-crossover logic match
      the book's §39 exactly; speculative *decoding* vs Ch 40 speculative *execution* is called out.
- [ ] 39-01 ends pointing at `blueprints/llm-gateway/` + `capstone-project/llm/gateway.py`; each notebook
      ends with recap + 2–4 change-and-predict exercises.
- [ ] Secrets/provider keys from env only; canned mock responses carry realistic token-usage
      fields; no keys in committed outputs.
