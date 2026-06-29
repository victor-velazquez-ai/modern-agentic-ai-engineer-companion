# Ch 40 — Cost, Latency & Performance Engineering

> Companion plan · Part X · book file `chapters/40-cost-latency-performance.typ`
> Status: 📋 planned (Phase 1)

## Role in the companion
This is the discipline chapter — measure cost so you can attribute it, cache so you don't pay
twice, and engineer latency on purpose. Every technique here is **measurable offline**: the
notebooks meter token spend with attribution labels, build all three cache layers and watch
hit rates, and decompose a latency budget with a deterministic simulator — no live API needed
(`MOCK=1` canned usage). Everything lives at the **gateway from Ch 39**, which is exactly where
the book puts metering, caching, and routing.

## Planned notebooks

### 40-01 · `40-01-token-accounting-and-attribution.ipynb` — Unit economics, not a monthly total
- **Type:** concept-lab
- **Maps to:** book §40.1 (measuring & attributing token cost — `tracked_call`, the `CallRecord`,
  `feature`/`tenant`/`model` labels), with the cost-per-completed-*task* mental model and the
  heavy-tailed-cost pitfall.
- **Objective:** turn a pile of model calls into the numbers finance and product actually ask
  for — cost per feature, per tenant, and per *completed task* — and find the tail that hides
  in the average.
- **Prereqs:** Ch 39 (the gateway is where metering lives); Ch 23 (metrics emission) read.
- **Cell arc:**
  - 🧠 mental model: token spend is COGS — you need *unit economics* (cost per business action:
    a ticket resolved, a doc processed), not aggregate cost per request.
  - Build the book's `tracked_call` / `CallRecord` shape around a **mock** model call: capture
    input/output/cache-read tokens + latency, price from a config table (never hardcode prices),
    emit a labeled metric (`feature`, `tenant`, `model`).
  - Replay a small **synthetic traffic log** (mixed features/tenants, one agent that loops nine
    times on a ticket) through it.
  - 🔮 *predict* which *feature* dominates spend before grouping the records — then roll up
    cost-per-feature and cost-per-tenant and check.
  - **Cost per task vs per request:** compute both; show the looping agent that looks cheap
    per-request and expensive per-resolved-ticket — the unit-economics reveal.
  - ⚠️ pitfall: averages lie — costs are heavy-tailed; plot the distribution, read p95/p99 cost
    per task and top-N tenants, and add the hard caps (max tokens, max iterations, per-tenant
    spend) that defuse the *denial-of-wallet* tail.
  - 🎯 senior lens: define the *unit* first, then make every call carry enough labels to roll up
    to it; meter once at the gateway, not scattered through app code.
- **Datasets/fixtures:** a small committed `data/` synthetic call log (rows of feature/tenant/
  model/tokens) + an in-notebook `PRICES` config; all illustrative.
- **APIs & cost:** **none** — operates on a synthetic log + mock calls, fully offline.
- **You'll be able to:** attribute LLM spend to feature/tenant/task and surface the tail an
  average hides — the metering layer the cost dashboard reads.

### 40-02 · `40-02-caching-layers-and-cache-aware-routing.ipynb` — Three caches, and making them hit
- **Type:** concept-lab
- **Maps to:** book §40.2 (exact / semantic / provider prompt caching + prompt compression) and
  §40.4 (the retrieval cost plane + prefix-aware / KV-cache-aware routing); the token-optimization
  playbook table and the senior-lens *order of leverage*.
- **Objective:** build each cache layer, measure its hit rate and savings, learn which to reach
  for first, and route so the cache you paid to build actually hits.
- **Prereqs:** 40-01; Ch 11 (cache-aside) and Ch 13 (vector similarity) read.
- **Cell arc:**
  - 🧠 mental model: the cheapest, fastest token is the one you never generate — three distinct
    cache layers answer different questions; conflating them is the classic confusion.
  - **Exact cache:** the book's `cache_key` (hash model+messages+params) → store/return; measure
    hit rate on a repeating workload; safe by construction, collapses when users phrase freely.
  - **Semantic cache:** embed the query (mock/local embedder), serve on cosine-similarity above a
    threshold; 🔮 *predict* what a too-loose threshold does, then watch "fee for plan A" vs
    "plan B" collide — keep it conservative, scope keys per tenant.
  - **Provider prompt cache (prefix reuse):** simulate prefix-match savings on a stable-first
    prompt; ⚠️ pitfall: a timestamp in the system prompt silently drops the hit rate to zero with
    *no error* — diff two rendered prompts byte-by-byte to find the invalidator; verify via
    `cache_read_input_tokens`, never assume.
  - **Prompt compression:** trim/summarize history, prune tool results, dedupe chunks; measure
    tokens saved (and note fewer tokens = lower latency + often better attention).
  - **Retrieval cost plane:** meter the line items the generation meter never sees — embedding
    calls, reranker calls, vector-store infra — and show they can *rival* generation cost; cache
    query embeddings, batch embeddings, right-size the reranker/candidate set.
  - **Cache-aware routing:** round-robin scatters same-prefix requests so each pays full prefill;
    hash the routing key on the stable prefix (tenant/agent/prompt-version) and watch the second
    request reuse the first's KV-cache — the lever is the routing key.
  - 🎯 senior lens: apply optimizations cheapest-first — right-size model → prompt cache → exact
    cache → batch API → *then* semantic cache / aggressive compression (which carry quality
    risk); most teams reach for the risky end first.
- **Datasets/fixtures:** a small committed `data/` query set with deliberate exact-repeats and
  paraphrase-pairs; an offline/mock embedder (seeded) so similarity is deterministic.
- **APIs & cost:** **none** — mock model + offline embedder; all hit-rate/savings numbers computed
  locally.
- **You'll be able to:** build and measure all three caches, avoid the prompt-cache killers, meter
  the retrieval cost plane, and route prefix-aware so caches actually hit.

### 40-03 · `40-03-latency-budgets-parallelism-and-speculation.ipynb` — Engineer latency on purpose
- **Type:** concept-lab
- **Maps to:** book §40.5 (latency budgets, parallelism, speculative patterns) — TTFT vs total,
  output-tokens-dominate, the per-stage latency-budget table, bounded-concurrency fan-out, and
  the three speculative patterns; the cost↔latency coupling key idea and the §40 checklist.
- **Objective:** decompose a request's latency into a per-stage budget, cut the biggest line with
  parallelism, and decide when to *spend tokens to buy time* with speculation.
- **Prereqs:** 40-01–02; Ch 4 (async) and Ch 24 (latency budgets for web services) read.
- **Cell arc:**
  - 🧠 mental model: cost is paid by the company; latency by the user, every interaction —
    set a budget, decompose it, attack the biggest stage.
  - **TTFT vs total:** simulate a streamed vs all-at-once response; show why 400 ms-to-first-token
    *feels* fast even at 8 s total — budget TTFT separately.
  - **Output tokens dominate:** a deterministic generation-time model (time ∝ output tokens);
    🔮 *predict* the speedup from halving `max_tokens`, then measure — "ask for less" is latency
    engineering.
  - **Per-stage budget:** reproduce the book's table (network+auth, retrieval, TTFT, generation,
    tool calls) and assign each stage an owner so a regression has one.
  - **Parallelism:** the book's bounded `summarize_all` (asyncio.gather + a `Semaphore`) over a
    mock async client — ten docs at concurrency eight finish in ~the time of two; ⚠️ pitfall:
    unbounded `gather` meets the provider's rate limiter (Ch 29 backpressure) — the semaphore
    matters.
  - **Speculative patterns (simulated):** *race the tiers*, *prefetch* the likely follow-up,
    *optimistic tool calls* — model the wasted-branch cost vs wall-clock saved and show it's a
    good trade exactly when latency outvalues tokens; ⚠️ don't confuse with Ch 39's in-decoder
    speculative *decoding*.
  - **Regression guard:** wire a cost+latency budget assertion (this run must stay under N tokens
    / T ms) so a prompt change that doubles tokens fails offline — the CI hook the book wants.
  - 🎯 senior lens: cost and latency couple through one decision — *how much model per step?*
    Routing a step to a smaller model improves both; the gateway (Ch 39) is where that knob turns.
  - 📋 close on the §40 **cost/latency production checklist** (metering · unit economics · tails ·
    caps · routing · prompt cache · app caches · batching · streaming · parallelism · output
    discipline · context compaction · regression guard) as a copyable cell.
- **Datasets/fixtures:** a handful of mock "documents" for the fan-out; seeded timing model; no
  external services.
- **APIs & cost:** **none** — mock async client with simulated latencies; deterministic and offline.
- **You'll be able to:** build a per-stage latency budget, parallelize fan-out safely, judge when
  speculation pays, and gate cost/latency regressions in CI.

## Feeds (cross-pillar)
- **Blueprint(s):** extends [`blueprints/llm-gateway/`](../../blueprints/llm-gateway/) (Ch 39)
  with metering, the three cache layers, prompt compression, and cache-aware routing — the
  cost/latency half of the gateway; emits the cost metrics
  [`blueprints/observability-stack/`](../../blueprints/observability-stack/) (Ch 23)
  dashboards on. Cross-links [`blueprints/rag-pipeline/`](../../blueprints/rag-pipeline/)
  (Ch 13) for the retrieval cost plane.
- **Template(s):** — (no new template; reinforces the prices-in-config and gateway-as-single-
  entry-point conventions). The CI cost/latency budget check feeds
  [`templates/github-actions-ci/`](../../templates/github-actions-ci/) (Ch 7).
- **Capstone:** advances `capstone-project/llm/gateway.py` — adds the metering/budget hooks, exact +
  semantic + prompt caching, and prefix-aware routing the platform's Grafana cost dashboard
  reads; checkpoint `checkpoints/ch40-cost-and-caching`.

## Dependencies
- Ch 39 (the gateway these layers attach to) · Ch 11 (cache-aside) · Ch 13 (vector similarity;
  retrieval cost) · Ch 23 (metrics emission / cost dashboards) · Ch 4 (async) · Ch 24 (latency
  budgets). Forward: Ch 41 adds spend caps as a *security/abuse* control (denial-of-wallet) on
  the same meter; Ch 42 turns these into SLOs.

## Phase-2 definition of done
- [ ] All three notebooks run top-to-bottom in `MOCK=1` with no errors and **no network** —
      every cost, hit-rate, and latency figure is computed offline from synthetic logs / mock
      clients.
- [ ] The `tracked_call`/`CallRecord` shape, the three cache layers + prompt-cache killer, the
      retrieval-cost-plane line items, prefix-aware routing, the latency-budget table, bounded
      `summarize_all`, and the three speculative patterns match the book's §40 exactly.
- [ ] Each notebook ends with recap + 2–4 change-and-predict exercises; 40-01/40-02/40-03 link
      back to `capstone-project/llm/gateway.py` and the §40 checklist appears as a copyable cell.
- [ ] Prices live in config (never hardcoded in logic); no secrets in committed outputs;
      semantic-cache keys scoped per tenant in every example.
