# Blueprint — LLM Gateway

> **The single door to every model call.** Base client (Ch 11) + production gateway (Ch 39–41):
> routing, fallbacks, exact + semantic cache, cost metering, and input/output guards.
> Runs **free and offline in `MOCK` mode** — no API key, no spend.

This is the standalone, hardened version of the capstone's `llm/` module — the one choke point
every other part of the system (agent loop, RAG, supervisor, evals) calls models *through*. See
[`PLAN.md`](PLAN.md) for how it maps to the book and the capstone.

---

## Naming — `llm-client` → `llm-gateway`

Earlier chapter/notebook plans referenced a `blueprints/llm-client/`. **That is this blueprint
under its old name.** The split is by layer, not by folder:

- **`llm-client`** = the **Ch 11 base layer** — `client.py` + `ports.py`. One typed door over the
  SDK: retries, streaming, usage.
- **`llm-gateway`** = the base layer **plus** the Ch 39–41 layers — routing, fallbacks, cache,
  metering, guards, composed in `Gateway`.

Any `llm-client` link resolves here. There is one package, `llm_gateway`, and the base client is
importable on its own (`from llm_gateway import LLMClient`).

---

## The two layers

```
                       ┌──────────────────────────  Gateway  (Ch 39–41)  ──────────────────────────┐
  prompt ─▶ guard.in ─▶ route ─▶ cache ─▶ │ fallback ladder over the base client │ ─▶ meter ─▶ guard.out ─▶ result
                       └──────────────────────────────────┬────────────────────────────────────────┘
                                                           │ each rung calls
                                              ┌────────────▼─────────────┐
                                              │  LLMClient  (Ch 11)      │  retries · streaming · usage
                                              └────────────┬─────────────┘
                                                           │ speaks only to
                                              ┌────────────▼─────────────┐
                                              │  ChatProvider (port)     │  MockProvider | AnthropicProvider | …
                                              └──────────────────────────┘
```

| File | Layer | Chapter | What it does |
|---|---|---|---|
| `ports.py` | base | 11 | The provider-agnostic `ChatProvider` Protocol + `MockProvider` (default) and `AnthropicProvider`. Typed `ChatRequest` / `ChatResponse` / `Usage`. |
| `client.py` | base | 11 | `LLMClient`: retries with backoff, streaming assembly, typed usage. The "single door." |
| `routing.py` | gateway | 39 | `TierRouter` (model selection by task/size) + `FallbackLadder` (primary → fallback on retryable failure). |
| `cache.py` | gateway | 40 | `ResponseCache`: exact hash cache + semantic near-hit cache, cost-aware keys. |
| `metering.py` | gateway | 40 | `Meter`: token/cost accounting with per-call attribution (by model, by label). |
| `guards.py` | gateway | 41 | `Guard`: PII redaction, prompt-injection blocking, content-safety flags — input and output. |
| `__init__.py` | gateway | 39–41 | `Gateway` composes all of the above around the base client. |

---

## Quick start

No install, no key — the mock provider is the default (`COMPANION_MOCK=1`):

```bash
python demo.py            # one prompt through route → cache → meter → guard, $0
python -m pytest -q       # 55 tests, all offline
```

In code:

```python
from llm_gateway import Gateway

gw = Gateway()                                  # mock provider, all layers on
result = gw.complete("Summarize the CAP theorem.", task="general", label="docs-bot")

result.response.text         # the (guarded) answer to return to the user
result.route.model           # which model was routed to
result.cached                # served from cache?
result.record.cost_usd       # what this call cost
gw.meter.summary()           # cost attribution by model and by label
```

Just the base client (the Ch 11 "single door"):

```python
from llm_gateway import LLMClient
text = LLMClient().ask("claude-opus-4-8", "Explain idempotency in one sentence.")
```

### Going live (spends tokens)

Secrets come from the environment only — never a constructor argument. Set two variables:

```bash
export COMPANION_MOCK=0
export ANTHROPIC_API_KEY=sk-ant-...
python demo.py
```

`default_provider()` then returns `AnthropicProvider`, which uses adaptive thinking
(`{"type": "adaptive"}`) and reads usage straight from the SDK. The `anthropic` SDK is imported
**lazily**, so the package installs and the mock path runs even when it's absent.

---

## Trade-offs (the parts worth reading)

### Exact vs semantic cache — cost vs recall

- **Exact cache** keys on a SHA-256 of the *answer-affecting* request fields (model, system,
  messages, `max_tokens`, `effort`). `metadata` is excluded on purpose, so two requests that
  differ only in a trace tag share an entry. Zero false positives; only catches verbatim repeats.
- **Semantic cache** embeds the prompt and serves the nearest stored answer within a cosine-
  similarity `threshold`. It catches paraphrases the exact cache misses — and that's exactly where
  the risk lives: **too low a `threshold` and you serve a stale-but-similar answer.** This is the
  precision/recall dial. The default is conservative (`0.95`); `demo.py` drops it to `0.7` to make
  near-hits visible with the offline embedder (and you'll see it fire on more prompts than you'd
  want in production — that *is* the lesson).

The embedder is pluggable. The default `hashing_embedder` is a deterministic bag-of-words hash —
no model, no network, no extra dependency — so the cache demonstrates semantic hits in CI. **Swap
in a real embedder** (`sentence-transformers`, an embeddings API) for production recall; the seam
is one function: `ResponseCache(embedder=my_embed_fn, threshold=0.88)`.

### Routing & the fallback ladder

`TierRouter` picks a tier from a coarse `task` hint and prompt length: `classification`/
`extraction` → Haiku (cheap), `reasoning`/`analysis`/`code` or a long prompt → Opus (smart),
otherwise Sonnet (balanced). A model the caller names explicitly always wins — the router never
second-guesses an explicit choice.

`FallbackLadder` is a typed list of `(provider, model)` rungs tried in order. It advances **only on
retryable errors** (429 / 5xx / timeout); a non-retryable error (400 / auth) fails fast, because
climbing wouldn't help and would waste spend. The two compose cleanly: the base client's
backoff-retry handles a transient blip *within* a rung; the ladder handles a rung that's *down*.

### Where guards belong

Guards run at the **edges**, where data crosses your trust boundary:

- **Input guard** runs before the provider sees the prompt — redact PII so it never leaves your
  perimeter, block prompt-injection and unsafe content. Blocks **fail closed** (raise
  `GuardrailError`); redaction **fails safe** (unknown → leave alone).
- **Output guard** runs before the user sees the answer — redact any PII the model echoed back.

The detectors here are deliberately simple, readable regexes — a stand-in for a real classifier/DLP
service. The durable value is the **seam**: one place every call passes through, so the policy is
consistent, testable, and swappable without touching callers.

### The provider port (portability)

Every layer depends on the `ChatProvider` Protocol, never a vendor SDK. A second provider
(OpenAI for the eval-judge, say) slots in by writing one more adapter that satisfies the same
Protocol — nothing above `ports.py` changes. That's the Anthropic-first-but-portable stance from
the book: one visual grammar for model access, with a clean second-provider seam.

---

## How it maps

- **Book:** Ch 11 (base client), Ch 39 (routing/fallbacks), Ch 40 (cost/cache), Ch 41 (guards).
- **`learn/` walkthrough:** [`../../learn/part-03-llm-substrate/11-working-with-model-apis/`](../../learn/part-03-llm-substrate/11-working-with-model-apis/)
  builds a toy `LLMClient` and ends by pointing here for the real one.
- **Capstone:** the standalone version of the capstone `llm/` module — the model choke point.
  Structured output (Ch 15) sits on top of this base client.

> **Study & adapt, not copy-paste.** Like every blueprint, this is the "how a senior would
> structure it" reference to lift ideas from — the capstone is yours to build.

---

## Layout

```text
llm-gateway/
├── README.md            ← you are here
├── PLAN.md              ← the spec (unchanged)
├── pyproject.toml       ← stdlib-only runtime; `anthropic` is an optional extra
├── demo.py              ← runnable: one prompt through every layer, MOCK mode
├── src/llm_gateway/
│   ├── __init__.py      ← Gateway (composes the four layers) + public API
│   ├── ports.py         ← ChatProvider port; Mock + Anthropic adapters
│   ├── client.py        ← base client: retries, streaming, usage (Ch 11)
│   ├── routing.py       ← model selection + fallback ladder (Ch 39)
│   ├── cache.py         ← exact + semantic cache (Ch 40)
│   ├── metering.py      ← token/cost accounting (Ch 40)
│   └── guards.py        ← input/output guards (Ch 41)
└── tests/               ← 55 tests, all offline (MOCK)
    ├── test_client.py   ← retry/backoff, streaming assembly, usage
    ├── test_routing.py  ← tier selection, primary→fallback
    ├── test_cache.py    ← exact hit, semantic near-hit threshold, keys
    ├── test_guards.py   ← injection/PII blocked, safe text passes
    └── test_gateway.py  ← the composed path + metering attribution
```
