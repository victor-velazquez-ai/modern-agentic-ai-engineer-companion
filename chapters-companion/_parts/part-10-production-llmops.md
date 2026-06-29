# Part X — Production LLMOps

> Companion to **Modern Agentic AI Engineer**, Part X · book chapters 39–41
> Status: 📋 planned (Phase 1)

## Companion emphasis

This is **LLMOps as serving, cost, and security** — operating models in production once they
work. The arc: stand up an **LLM gateway** and reason about the serving stack underneath it
(Ch 39) → make the system *affordable and fast* by metering spend, caching, and engineering
latency at that gateway (Ch 40) → make it *defensible* with the OWASP Top 10, prompt-injection
defenses, guardrails, and least-privilege tool permissions (Ch 41). One through-line ties the
part together: **the gateway from Ch 39 is the single chokepoint** where routing, cost, caching,
guardrails, and per-tenant limits all live — build it once, and cost control and security become
properties of the platform rather than scattered patches.

> **Scope note — the other half of LLMOps lives in Part VI.** Evaluation and observability —
> the *measure* and *observe* half of operating LLMs — were built back in
> [Part VI](../part-06-evaluation-observability-quality/) (Ch 21–23: the eval harness, the OTel
> tracing/cost stack). Part X deliberately does **not** repeat them; it *uses* them — Ch 40's
> cost metering emits to the Part VI observability stack, and Ch 41's injection red-team suite
> gates in the *same* CI eval harness as quality. Think of Part X as **serving + cost +
> security**, sitting on top of the eval/observability foundation already in place.

## ⚠️ These notebooks run free and offline — mock-first by default

Production LLMOps is exactly where a careless notebook runs up a bill or pokes a real system, so
**every notebook here runs free, offline, and deterministically by default** (`MOCK=1`):

- **Model calls → mocked.** The gateway, routing, fallbacks, caching, and cost metering all run
  against **canned provider responses** carrying realistic token-usage fields — **no API keys, no
  spend.** `MOCK=0` (live providers) is optional and documented per notebook.
- **Self-hosting (vLLM / TGI / Ollama) → concept-labs + an ⚠️ optional local path.** The serving
  internals (continuous batching, KV-cache, quantization, the TCO crossover) are taught with tiny
  **offline simulators and arithmetic**; the one section that touches a *real* local model is
  clearly flagged **⚠️ heavy/optional**, skipped by default, and **never run in CI**.
- **Cost / caching / latency → measured offline.** Token accounting, the three cache layers, and
  latency budgets are computed from **synthetic logs and mock clients** — every number is
  reproducible without a network.
- **Security → SAFE, defensive, simulated.** Attacks appear **only** as a small, labeled red-team
  corpus of **obviously-fake payloads** (`evil.example`) used to verify *our own* guardrails;
  classifiers, moderation, PII detection, the IdP, and the sandbox are all **mocked/simulated**.
  Nothing targets real systems or models; the deliverable is always the measured defense.

Anything with real-world reach — a live provider call, a real local model pull, a real container
or cloud credential — is **⚠️-flagged, opt-in, and excluded from CI.** Secrets come from the
environment only; no keys, tokens, PII, or attack payloads land in committed outputs.

## Chapters

| Ch | Title | Companion note | Plan |
|---|---|---|---|
| 39 | Serving & Scaling Models | 🔧 Walkthrough — build the **LLM gateway** (routing · fallback · exact cache · cost tracking) in mock mode, feeding `blueprints/llm-gateway/` + `capstone-project/llm/gateway.py`; plus an offline concept-lab on serving internals (batching, KV-cache, quantization, the TCO crossover) with an ⚠️ optional vLLM/TGI/Ollama local path. | [`39-serving-and-scaling-models/PLAN.md`](39-serving-and-scaling-models/PLAN.md) |
| 40 | Cost, Latency & Performance Engineering | Concept-labs (all measurable offline) — token accounting & per-feature/tenant/**task** attribution; the three cache layers (exact · semantic · provider prompt cache) + the retrieval cost plane + cache-aware routing; latency budgets, bounded-concurrency parallelism, and speculative patterns, with a CI cost/latency regression gate. | [`40-cost-latency-performance/PLAN.md`](40-cost-latency-performance/PLAN.md) |
| 41 | Security, Safety & Compliance | Walkthroughs (SAFE / defensive) — OWASP LLM Top 10 + the lethal-trifecta injection defense-in-depth; injection **red-teaming as a gated attack-success-rate** + the input/output guardrail pipeline (PII, content safety, link neutralization); tool-permission tiers, sandboxing/blast-radius, and delegated (per-user, short-lived) authorization. Feeds `capstone-project/security/`. | [`41-security-safety-compliance/PLAN.md`](41-security-safety-compliance/PLAN.md) |

## Run order

Read in chapter order — the part builds on itself around one artifact. **39** is the foundation:
it builds the gateway every later chapter operates on, and the serving-internals lab that lets you
reason about cost/latency even as a pure API consumer. **40** attaches metering, caching, and
latency engineering *to that same gateway* — the economics that decide whether an agentic product
is viable. **41** wraps it in defenses: guardrails and per-tenant limits enforced at the gateway,
injection resistance measured as an SLO that gates CI, and least-privilege/delegated authorization
that bounds blast radius. The build artifacts of this part — `blueprints/llm-gateway/`,
`capstone-project/llm/gateway.py`, and `capstone-project/security/` (checkpoints `ch39-serving-and-gateway`,
`ch40-cost-and-caching`, `ch41-security-and-guardrails`) — are the production controls the
capstone end-to-end (Part XI, Ch 44) assembles and the architect designs around at scale.
