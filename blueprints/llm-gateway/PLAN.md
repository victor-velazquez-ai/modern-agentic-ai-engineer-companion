# Blueprint — LLM Gateway  (pattern)

> Realizes book Ch 11, 39–41 · mirrors capstone `llm/` · Status: 📋 planned (Phase 1)

## What it is
The **single door to every model call** in the system, in two layers:

1. **Base client (Ch 11)** — a thin, provider-agnostic wrapper over the SDK: typed
   request/response, retries with backoff, streaming, and usage capture. One choke point so no
   raw `client.messages.create(...)` is scattered through the code.
2. **Gateway (Ch 39–41)** — everything that wraps that client for production: **model routing**
   and **fallbacks**, an **exact + semantic response cache**, **cost/token metering**, and
   **input/output guards** (PII, injection, content safety). Anthropic-first, with a portable
   port so a second provider slots in for routing and the eval-judge.

> **Naming — this subsumes `llm-client`.** Earlier plans referenced a `blueprints/llm-client/`.
> That is this blueprint under its old name: **`llm-client` = the Ch 11 base layer; `llm-gateway`
> = the base layer + the Ch 39+ layers.** All `llm-client` links resolve here.

## Why a blueprint (not a notebook)
- It is the most-imported module in the repo (agent loop, RAG, supervisor, evals, the capstone
  all call models *through it*) — it has to be a stable, tested package, not cells.
- The valuable parts — semantic-cache keying, a routing policy, a fallback ladder, cost
  attribution per call — are cross-cutting infrastructure that only reads as real code.
- It is the place the book's safety/cost lessons (Ch 39–41) become enforceable defaults rather
  than advice.

## Planned structure
```text
llm-gateway/
├── README.md                  # the two layers, the port, trade-offs, how to adapt
├── pyproject.toml
├── src/llm_gateway/
│   ├── __init__.py
│   ├── client.py              #   base client (Ch 11): retries, streaming, typed usage
│   ├── ports.py               #   provider-agnostic Protocol; mock + Anthropic adapters
│   ├── routing.py             #   model selection + fallback ladder (Ch 39)
│   ├── cache.py               #   exact + semantic cache, cost-aware keys (Ch 40)
│   ├── metering.py            #   token/cost accounting, per-call attribution (Ch 40)
│   └── guards.py              #   input/output filters: PII, injection, safety (Ch 41)
├── tests/
│   ├── test_client.py         #   retry/backoff, streaming assembly, usage parsing
│   ├── test_routing.py        #   primary→fallback on error/timeout
│   ├── test_cache.py          #   exact hit; semantic near-hit threshold
│   └── test_guards.py         #   injection/PII patterns blocked; safe text passes
└── demo.py                    # runnable: one prompt through route→cache→meter→guard, MOCK
```

## Composes / depends on
- **Foundational** — depends on no other blueprint. It is the dependency: `agent-loop`,
  `rag-pipeline`, `multi-agent-supervisor`, and `eval-harness` all call models through it.
- Ships a **mock provider** so the whole gateway (and everything above it) runs with zero keys.

## Maps to the book
- **Ch 11 — Working with Model APIs:** the base client (SDK shapes, retries, caching, streaming,
  usage). Makes §11's 🔧 "single-door `LLMClient`" Build real.
- **Ch 39 — Serving & Scaling Models:** §"Model routing, fallbacks, and gateways."
- **Ch 40 — Cost, Latency & Performance:** token cost measurement, caching layers, semantic cache.
- **Ch 41 — Security, Safety & Compliance:** input/output guardrails, PII, content safety.
- **`learn/` walkthrough:** [`../../learn/part-03-llm-substrate/11-working-with-model-apis/`](../../learn/part-03-llm-substrate/11-working-with-model-apis/)
  builds the toy `LLMClient` and **ends by pointing here** (its plan currently links the old
  `llm-client/` slug — that link now resolves to this blueprint).

## Maps to the capstone
Standalone version of capstone **`llm/`** — the model choke point (`structured.py` and the
routing layer). The capstone uses this gateway as its single model door; structured-output
(Ch 15) sits on top of the base client.

## Phase-2 definition of done
- [ ] `pytest tests/` passes; client, routing, cache, and guards all covered.
- [ ] `python demo.py` runs a full request through all layers in **`MOCK=1`** (no API spend).
- [ ] README explains trade-offs: exact-vs-semantic cache cost/recall, the routing/fallback
      policy, where guards belong, and the provider-port seam for portability.
- [ ] States the `llm-client → llm-gateway` reconciliation; cross-links (Ch 11/39–41 walkthroughs,
      capstone `llm/`) resolve.
