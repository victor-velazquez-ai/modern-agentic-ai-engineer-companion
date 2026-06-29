# `llm/` — the model layer (the only door to model APIs)

The platform's single door to every model call. No other module touches a model
SDK; they all go through here, so retries, streaming, usage, routing, cost,
caching, and guards are uniform and in *one* reviewable place. Built across
**Ch 11** (base client), **Ch 15** (structured output), and **Ch 39–41** (the
gateway). The standalone pattern is the [`llm-gateway`](../../../blueprints/llm-gateway/README.md)
blueprint — this is its assembled-into-the-capstone form.

> Reference + answer key, not a starting point. Build yours from the chapters'
> 🔧 Build sections; compare against this. See the capstone [`README.md`](../../README.md).

## The three files (Appendix C)

| File | Layer | Chapter | What it does |
|---|---|---|---|
| `client.py` | base — the door to the **provider** | 11 | `ChatProvider` port + `MockProvider` (default, offline) and `AnthropicProvider` (lazy SDK import); `LLMClient` with retry/backoff, streaming assembly, typed `Usage`. |
| `structured.py` | choke point — typed **data** | 15 | `complete_structured(prompt, schema)`: ask for JSON → extract → validate (Pydantic model *or* JSON-Schema dict) → repair-and-retry; raises `ValidationError` rather than returning junk. |
| `gateway.py` | gateway — the door for **callers** | 39–41 | `Gateway` composing `TierRouter` + `FallbackLadder` (routing/fallbacks), `ResponseCache` (exact + semantic), `Meter` (cost attribution + daily cap), and `Guard` (PII/injection/unsafe). |

The blueprint splits routing/cache/metering/guards into separate modules; the
capstone folds them into `gateway.py` to match Appendix C's exact file list. The
provider port + adapters fold into `client.py` for the same reason.

## Request path through the gateway

```
guard(input) → route → cache → [fallback ladder over LLMClient] → meter → cost-cap → guard(output)
```

Each layer is injectable. A cache hit costs $0 and skips the provider; the cost
cap and guards **fail closed** (raise), redaction **fails safe** (leave unknown).

## Mock-runnable (zero spend)

Everything runs offline by default — `COMPANION_MOCK=1` (the repo convention)
selects `MockProvider`. Secrets are read from the **environment only**, never a
constructor argument.

```python
from llm import Gateway, LLMClient, complete_structured

# Gateway: full production path, mock provider.
gw = Gateway.from_settings()                       # reads core.config.Settings
res = gw.complete("Summarize the CAP theorem.", task="general", label="docs-bot")
res.response.text     # guarded answer        res.route.model    # routed model
res.cached            # served from cache?    res.record.cost_usd
gw.meter.summary()    # cost by model + by label

# Base client: the Ch 11 "single door."
text = LLMClient().ask("claude-sonnet-4-6", "Explain idempotency in one sentence.")

# Structured output: typed data, not prose.
from pydantic import BaseModel
class Ticket(BaseModel):
    priority: str
    summary: str
result = complete_structured("Triage: 'site is down for everyone'", Ticket)
result.value          # a validated Ticket   result.repaired    # needed a repair?
```

## Going live (spends tokens)

```bash
export COMPANION_MOCK=0
export ANTHROPIC_API_KEY=sk-ant-...
```

`default_provider()` then returns `AnthropicProvider` (adaptive thinking; usage
read from the SDK). The `anthropic` SDK is imported **lazily**, so the package
installs and the mock path runs even when it's absent.

## Design notes (the parts worth reading)

- **The provider port is the portability seam.** Every layer depends on
  `ChatProvider`, never a vendor SDK. A second provider (OpenAI for the
  eval-judge) slots in by writing one more adapter — nothing above `client.py`
  changes.
- **Exact vs. semantic cache** is the precision/recall dial: exact has zero false
  positives but only catches verbatim repeats; semantic catches paraphrases at the
  risk of serving a stale-but-similar answer below the `threshold` (default 0.95).
  The embedder is pluggable — swap `hashing_embedder` for a real one in production.
- **Routing vs. retry compose cleanly:** the client's backoff handles a transient
  blip *within* a rung; the fallback ladder handles a rung that's *down* (advancing
  only on retryable errors — a 400 fails fast).
- **Guards belong at the edges** and are shared with `security/` (Ch 41), which
  configures the same detectors as one reviewable policy.
- **`structured.py` sits on top of the client, it is not a second door.** It is the
  one seam every "give me typed data" call passes through.

## Dependencies

Runtime is **stdlib-only** for the mock path. `anthropic` (lazy) is needed only to
go live; `pydantic` is used by `structured.py` *when a model schema is passed* and
by `core.config` — both are imported defensively so the dict-schema/mock paths run
without them.
