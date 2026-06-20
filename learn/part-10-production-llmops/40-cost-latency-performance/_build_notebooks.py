"""Generator for Ch 40 companion notebooks.

Builds three nbformat-4 notebooks with cleared outputs. Run once, then delete.
This file is a build helper, not shipped content.
"""
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))


def _src(text: str):
    """Turn a block string into the list-of-lines source format the repo uses
    (each line keeps its trailing newline, except possibly the last)."""
    text = text.strip("\n") + "\n"
    lines = text.splitlines(keepends=True)
    return lines


def md(text: str):
    return {"cell_type": "markdown", "metadata": {}, "source": _src(text)}


def code(text: str):
    return {
        "cell_type": "code",
        "execution_count": None,
        "metadata": {},
        "outputs": [],
        "source": _src(text),
    }


def notebook(cells):
    return {
        "cells": cells,
        "metadata": {
            "kernelspec": {
                "display_name": "Python 3",
                "language": "python",
                "name": "python3",
            },
            "language_info": {"name": "python"},
        },
        "nbformat": 4,
        "nbformat_minor": 5,
    }


def write(name, cells):
    path = os.path.join(HERE, name)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        json.dump(notebook(cells), f, indent=1, ensure_ascii=False)
        f.write("\n")
    return path


# ===========================================================================
# 40-01 · token accounting and attribution (concept-lab)
# ===========================================================================

nb1 = [
    md(r"""
# Token accounting & attribution: unit economics, not a monthly total

> 📓 *Companion to* **Modern Agentic AI Engineer** *· Ch 40 §40.1 · type: concept-lab*

**The promise:** by the end you can turn a pile of model calls into the numbers finance and product actually ask for — cost per feature, per tenant, and per *completed task* — and find the heavy tail that hides inside the average.
"""),
    md(r"""
## 🧠 Why this matters

The provider bills you one aggregate number per month, but the decisions that *drive* that number — which feature, which prompt, which customer — are buried in your application. The fix is to record usage **at the call site**, with enough labels to answer the questions you'll inevitably be asked.

Think of token spend like any other COGS line: you need **unit economics**, not totals. The unit is the *business action* — a ticket resolved, a document processed — not the API request. Aggregate cost per request hides the agent that loops nine times on one ticket; cost per *completed task* exposes it instantly. Define the unit first, then make every model call carry enough labels to roll up to it. See §40.1.
"""),
    md(r"""
## Objectives & prereqs

**By the end you can:**
- Capture per-call usage in the book's `CallRecord` shape and price it from a **config table** (never hardcoded in logic).
- Emit a metric with attribution labels (`feature`, `tenant`, `model`) — the metering layer a cost dashboard reads.
- Roll a synthetic traffic log up to **cost per feature**, **per tenant**, and **per completed task**.
- Read the **heavy tail** (p95/p99 cost per task, top-N tenants) that an average hides, and name the caps that defuse it.

**Prereqs:** Ch 39 (the gateway is where metering lives); Ch 23 (metrics emission) read. Notebook `08-01-tokens-and-the-bill` for token intuition.

**Runs free & offline.** Everything here operates on a tiny committed synthetic log (`data/call_log.csv`) plus a **mock** model call. No API key, no network — `MOCK=1` is the only mode that does real work, and it is the default.
"""),
    code(r"""
# Setup — imports, env, and the MOCK switch.
import os
import csv
import time
import json
import random
import statistics
from dataclasses import dataclass, asdict

from dotenv import load_dotenv

load_dotenv()  # reads a local .env if present; never hardcode keys

# MOCK=1 (default) keeps this notebook offline, free, and deterministic. There is no
# live path here worth the spend — the lesson is metering, and a mock call carries the
# same usage shape a real one does. MOCK=0 would simply call the real SDK in tracked_call.
MOCK = os.getenv("COMPANION_MOCK", "1") == "1"

random.seed(40)  # any stochastic mock is reproducible

DATA = os.path.join(os.getcwd(), "data")
print("MOCK mode:", MOCK, "— offline, no API key needed" if MOCK else "— LIVE (would call the SDK)")
print("data dir :", DATA)
"""),
    md(r"""
## Prices live in config, not in logic

The single most important habit in this whole notebook: **prices are configuration.** They change, they differ per model, and a hardcoded number buried in application logic is a bug waiting to happen. Keep a table keyed by model, in *dollars per million tokens*, loaded from config — here, an in-notebook dict standing in for that config.
"""),
    code(r"""
# Price table: dollars per MILLION tokens, as (input, output, cache_read).
# In production this is loaded from config (a YAML file, a settings object) — never
# hardcoded in the call path. Numbers here are illustrative, not a live price sheet.
PRICES = {
    "claude-opus-4-8":  (5.00, 25.00, 0.50),   # frontier tier
    "claude-haiku-4-5": (0.80,  4.00, 0.08),   # cheap tier
}


def price_call(model: str, input_tokens: int, output_tokens: int, cache_read_tokens: int) -> float:
    """Cost in USD for one call, priced from the config table."""
    in_p, out_p, cache_p = PRICES[model]
    # Cache-read tokens are billed at the cheap cached rate, not full input price.
    billable_input = input_tokens - cache_read_tokens
    return (billable_input * in_p
            + cache_read_tokens * cache_p
            + output_tokens * out_p) / 1_000_000


print("priced models:", list(PRICES))
print("example: opus, 4000 in / 500 out / 2400 cached =",
      f"${price_call('claude-opus-4-8', 4000, 500, 2400):.5f}")
"""),
    md(r"""
## The book's `tracked_call` and `CallRecord`

This is the metering shape from §40.1, built around a **mock** model call so it runs offline. It captures input/output/cache-read tokens plus latency, prices the call from `PRICES`, and emits a labeled metric. The labels — `feature`, `tenant`, `model` — are the entire point: they are what lets you roll usage up to a business unit later.

In the capstone this lives in **one** place — the gateway (Ch 39) — so every call passes through a single chokepoint. No scattered instrumentation, no blind spots.
"""),
    code(r"""
@dataclass
class CallRecord:
    model: str
    input_tokens: int
    output_tokens: int
    cache_read_tokens: int
    latency_ms: float
    cost_usd: float
    feature: str
    tenant: str
    task_id: str


# A tiny in-memory metrics sink standing in for Prometheus / an events table (Ch 23).
METRICS: list[dict] = []


def emit_metric(name: str, value: float, labels: dict) -> None:
    METRICS.append({"name": name, "value": value, **labels})


class _Usage:
    """Mirrors the provider's usage object shape."""
    def __init__(self, input_tokens, output_tokens, cache_read_input_tokens):
        self.input_tokens = input_tokens
        self.output_tokens = output_tokens
        self.cache_read_input_tokens = cache_read_input_tokens


def _mock_messages_create(**kwargs):
    """Stand-in for client.messages.create — returns a canned response + usage.

    The usage numbers come from kwargs so a replayed log reproduces exactly; a real
    response would carry the same .usage shape, which is the whole point of mocking it.
    """
    u = kwargs["_usage"]
    return type("Resp", (), {
        "usage": _Usage(u["input_tokens"], u["output_tokens"], u["cache_read_tokens"]),
        "content": [type("Block", (), {"type": "text", "text": "(mock answer)"})()],
    })()


def tracked_call(*, feature: str, tenant: str, task_id: str, model: str, _usage: dict, **kwargs):
    """Meter one model call: time it, price it, emit a labeled metric, return the record.

    MOCK=1 uses the canned response above; MOCK=0 would swap in the real client. Either
    way the metering code is identical — that is what 'meter once at the gateway' buys you.
    """
    start = time.monotonic()
    resp = _mock_messages_create(model=model, _usage=_usage, **kwargs)
    latency_ms = (time.monotonic() - start) * 1000

    u = resp.usage
    cost = price_call(model, u.input_tokens, u.output_tokens, u.cache_read_input_tokens or 0)

    record = CallRecord(
        model=model,
        input_tokens=u.input_tokens,
        output_tokens=u.output_tokens,
        cache_read_tokens=u.cache_read_input_tokens or 0,
        latency_ms=latency_ms,
        cost_usd=cost,
        feature=feature,
        tenant=tenant,
        task_id=task_id,
    )
    emit_metric("llm_cost_usd", cost,
                labels={"feature": feature, "tenant": tenant, "model": model})
    return record


# Smoke-test one call.
rec = tracked_call(feature="support_agent", tenant="acme", task_id="t-demo",
                   model="claude-opus-4-8",
                   _usage={"input_tokens": 4000, "output_tokens": 500, "cache_read_tokens": 2400})
print(json.dumps(asdict(rec), indent=2))
print("metrics emitted:", len(METRICS))
"""),
    md(r"""
## Replay a small synthetic traffic log

`data/call_log.csv` is a tiny, hand-built log: a `doc_summarizer` and a `faq_bot` on the cheap tier, and a `support_agent` that **loops nine times on one ticket** (`task_id = t-tkt-01`) on the frontier tier — plus one giant 98k-token document that is the heavy tail. We replay each row through `tracked_call`, which produces the same `CallRecord`s a live system would.
"""),
    code(r"""
def load_log(path):
    with open(path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            for k in ("input_tokens", "output_tokens", "cache_read_tokens"):
                row[k] = int(row[k])
            yield row


records: list[CallRecord] = []
for row in load_log(os.path.join(DATA, "call_log.csv")):
    records.append(tracked_call(
        feature=row["feature"], tenant=row["tenant"], task_id=row["task_id"],
        model=row["model"],
        _usage={"input_tokens": row["input_tokens"],
                "output_tokens": row["output_tokens"],
                "cache_read_tokens": row["cache_read_tokens"]},
    ))

total = sum(r.cost_usd for r in records)
print(f"{len(records)} calls replayed, total spend ${total:.4f}")
print(f"average cost per *request*: ${total/len(records):.5f}")
"""),
    md(r"""
## 🔮 Predict: which feature dominates spend?

Three features generated traffic: `doc_summarizer`, `faq_bot`, and `support_agent`. One of them is going to dominate the bill.

**Predict, before you run the next cell:** which feature accounts for the most spend — and is it because of *price per call*, *number of calls*, or both? Write your guess, then group the records.
"""),
    code(r"""
def rollup(records, key):
    """Sum cost by a label, returning a sorted (label, cost, n_calls) list."""
    agg: dict[str, list] = {}
    for r in records:
        bucket = agg.setdefault(getattr(r, key), [0.0, 0])
        bucket[0] += r.cost_usd
        bucket[1] += 1
    rows = [(k, v[0], v[1]) for k, v in agg.items()]
    return sorted(rows, key=lambda x: x[1], reverse=True)


print("Cost per FEATURE")
for feature, cost, n in rollup(records, "feature"):
    print(f"  {feature:16s} ${cost:8.4f}   ({n} calls, ${cost/n:.5f}/call)")

print("\nCost per TENANT")
for tenant, cost, n in rollup(records, "tenant"):
    print(f"  {tenant:10s} ${cost:8.4f}   ({n} calls)")
"""),
    md(r"""
**What you just saw.** The `support_agent` dwarfs the others — partly because it's on the frontier tier, but mostly because **one ticket triggered nine model calls**. That's the agentic cost multiplier: a single user action fans out into a dozen calls. And `megacorp` jumps up the tenant list off the back of *one* giant document — a preview of the tail.
"""),
    md(r"""
## Cost per task vs. cost per request — the unit-economics reveal

Cost *per request* makes the looping agent look cheap: each individual call is a few cents. Cost *per completed task* tells the truth — nine calls roll up to one resolved ticket, and that is the number to compare against what a ticket is worth. We have `task_id` on every record, so we can roll up to the unit.
"""),
    code(r"""
def cost_per_task(records):
    by_task: dict[str, list] = {}
    for r in records:
        b = by_task.setdefault(r.task_id, [0.0, 0, r.feature])
        b[0] += r.cost_usd
        b[1] += 1
    return by_task


tasks = cost_per_task(records)
agent_tasks = {t: v for t, v in tasks.items() if v[2] == "support_agent"}

print(f"{'task':10s} {'feature':16s} {'calls':>5s} {'cost/task':>11s}")
for task, (cost, n, feat) in sorted(tasks.items(), key=lambda kv: kv[1][0], reverse=True)[:6]:
    print(f"{task:10s} {feat:16s} {n:>5d} {cost:>11.5f}")

avg_req = sum(r.cost_usd for r in records) / len(records)
avg_agent_task = statistics.mean(v[0] for v in agent_tasks.values())
print(f"\navg cost per REQUEST           : ${avg_req:.5f}")
print(f"avg cost per resolved TICKET   : ${avg_agent_task:.5f}  "
      f"({avg_agent_task/avg_req:.1f}x the per-request number)")
"""),
    md(r"""
**What you just saw.** The same workload reads as "fractions of a cent per request" *or* as a multi-cent cost per resolved ticket — and only the second number can be compared to revenue. A nine-call ticket that looks cheap per request is the unit you must price your support tier against.
"""),
    md(r"""
## ⚠️ Pitfall: averages lie — costs are heavy-tailed

The average request cost is a comforting, useless number. A handful of calls — the 98k-token document, the runaway loop — carry most of the bill while the *average* looks fine. Always read the **distribution**: p95/p99 cost per task and the top-N tenants. The fix is structural: hard caps (max tokens, max iterations, per-tenant spend) on the tail. **An unbounded loop with a paid API attached is a denial-of-wallet bug** (Ch 41 turns these caps into an abuse control).
"""),
    code(r"""
def percentile(values, p):
    """Nearest-rank percentile on a small list — no numpy needed."""
    s = sorted(values)
    k = max(0, min(len(s) - 1, round((p / 100) * (len(s) - 1))))
    return s[k]


per_call = sorted((r.cost_usd for r in records), reverse=True)
print("Per-CALL cost distribution")
print(f"  mean : ${statistics.mean(per_call):.5f}")
print(f"  p50  : ${percentile(per_call, 50):.5f}")
print(f"  p95  : ${percentile(per_call, 95):.5f}")
print(f"  p99  : ${percentile(per_call, 99):.5f}")
print(f"  max  : ${per_call[0]:.5f}   <- one call, this fraction of the total bill:")
print(f"         {per_call[0] / sum(per_call) * 100:.0f}% of all spend in a single call")

# A crude ASCII view of the tail so 'heavy-tailed' is something you SEE.
print("\nTop calls by cost (the tail):")
for c in per_call[:5]:
    bar = "#" * int(c / per_call[0] * 40)
    print(f"  ${c:8.5f} {bar}")
"""),
    code(r"""
# The caps that defuse the tail. These are config knobs, enforced at the gateway —
# here we just SHOW what each would have trimmed on this log.
MAX_TOKENS_PER_CALL = 8000          # refuse / truncate giant inputs
MAX_ITERATIONS_PER_TASK = 6         # stop a runaway agent loop
PER_TENANT_DAILY_USD = 0.10         # denial-of-wallet ceiling

capped_input = [r for r in records if r.input_tokens > MAX_TOKENS_PER_CALL]
loop_lengths = {}
for r in records:
    loop_lengths[r.task_id] = loop_lengths.get(r.task_id, 0) + 1
runaway = {t: n for t, n in loop_lengths.items() if n > MAX_ITERATIONS_PER_TASK}

print(f"calls over {MAX_TOKENS_PER_CALL} input tokens (would be capped): "
      f"{len(capped_input)}  -> {[r.task_id for r in capped_input]}")
print(f"tasks over {MAX_ITERATIONS_PER_TASK} iterations (loop cap trips): {runaway}")
tenant_spend = {t: c for t, c, _ in rollup(records, "tenant")}
over = {t: c for t, c in tenant_spend.items() if c > PER_TENANT_DAILY_USD}
print(f"tenants over ${PER_TENANT_DAILY_USD:.2f} (budget alert): "
      f"{ {t: round(c, 4) for t, c in over.items()} }")
"""),
    md(r"""
**What you just saw.** Three small caps — a per-call token ceiling, a loop limit, and a per-tenant budget — each catch a *different* slice of the tail the average never showed you. None of them touch the well-behaved median traffic. That's the shape of good cost control: bound the tail, leave the body alone.
"""),
    md(r"""
## 🎯 Senior lens

Define the **unit** first — the business action you actually sell — then make every model call carry enough labels (`feature`, `tenant`, `task_id`, `model`) to roll up to it. Meter **once**, at the gateway (Ch 39), not scattered through application code: scattered instrumentation drifts, double-counts, and leaves blind spots exactly where a new feature is bleeding money. And never trust the mean — a cost dashboard that shows only averages is hiding the loop and the whale that are actually your bill. Track p95/p99 cost per task and top-N tenants, alert on them, and cap the tail by construction.
"""),
    md(r"""
## Recap

- Record usage **at the call site** in the `CallRecord` shape; price it from a **config table**, never a hardcoded number in logic.
- Attribution labels (`feature`, `tenant`, `task_id`, `model`) are the point — they let you roll spend up to a business unit.
- **Cost per completed task**, not per request, is the unit-economics number; it exposes the agent that loops nine times on one ticket.
- Costs are **heavy-tailed**: read p95/p99 and top-N tenants, not the mean. One call can be most of the bill.
- Defuse the tail with **hard caps** (max tokens, max iterations, per-tenant spend) — an unbounded paid loop is a denial-of-wallet bug.
- Meter **once at the gateway**, the single chokepoint the cost dashboard reads.
"""),
    md(r"""
## Exercises

Each one *changes* something and asks you to predict the result first.

1. **A price hike.** Double the output price for `claude-opus-4-8` in `PRICES` and re-run the rollups. Predict whether cost-per-ticket moves more than cost-per-FAQ, then check — and explain the difference from the input/output token mix.
2. **Add a worse loop.** Append three more rows to a new `t-tkt-04` so it loops twelve times. Predict its rank in the cost-per-task table and whether it trips `MAX_ITERATIONS_PER_TASK`, then verify.
3. **A real cap.** Write `enforce_caps(row)` that *rejects* a call over `MAX_TOKENS_PER_CALL` before it's made. Re-replay the log through it and predict the new total spend before computing it.
4. **Tenant budget.** Roll up cost per tenant *per feature* (a two-level group-by) and find which tenant/feature pair to put a budget on first. Predict it from the earlier rollups before you compute.
"""),
    code(r"""
# Exercise 1 — your code here.
"""),
    code(r"""
# Exercise 2 — your code here.
"""),
    code(r"""
# Exercise 3 — your code here.
"""),
    md(r"""
## Next

- **Next notebook:** [`40-02-caching-layers-and-cache-aware-routing.ipynb`](40-02-caching-layers-and-cache-aware-routing.ipynb) — the cheapest token is the one you never generate; build all three cache layers and measure their hit rates.
- **Book:** §40.1 (measuring & attributing cost) and the §40 cost/latency checklist; Ch 23 for the dashboards these metrics feed; Ch 41 for caps as an abuse control.
- **Blueprint this feeds:** [`blueprints/llm-gateway/`](../../../blueprints/llm-gateway/) (metering at the chokepoint) and [`blueprints/observability-stack/`](../../../blueprints/observability-stack/) (the cost dashboard).
- **Capstone:** advances [`capstone/llm/gateway.py`](../../../capstone/llm/gateway.py) — the metering and per-tenant budget hooks the platform's Grafana cost dashboard reads (`checkpoints/ch40-cost-and-caching`).
"""),
]

# ===========================================================================
# 40-02 · caching layers and cache-aware routing (concept-lab)
# ===========================================================================

nb2 = [
    md(r"""
# Caching layers & cache-aware routing: three caches, and making them hit

> 📓 *Companion to* **Modern Agentic AI Engineer** *· Ch 40 §40.2, §40.4 · type: concept-lab*

**The promise:** by the end you can build each of the three cache layers, measure its hit rate and savings, know which to reach for first, meter the retrieval cost plane, and route so the cache you paid to build actually hits.
"""),
    md(r"""
## 🧠 Why this matters

The cheapest, fastest token is the one you never generate. Caching for LLM systems comes in **three distinct layers**, and conflating them is the classic source of confusion:

- **Exact cache** — return a stored response when the *identical* request arrives again. Safe by construction; collapses when users phrase freely.
- **Semantic cache** — serve a stored response when a *similar enough* past query exists. Catches paraphrases; risky at the threshold.
- **Provider prompt cache** — the provider reuses computation on a stable **prefix** of your prompt. Near-free, huge for agents; a strict prefix match.

This notebook builds all three offline with a mock model and a seeded local embedder, so every hit-rate and savings number is computed deterministically. See §40.2 and §40.4.
"""),
    md(r"""
## Objectives & prereqs

**By the end you can:**
- Build the book's `cache_key` exact cache and measure its hit rate on a repeating workload.
- Build a semantic cache on a seeded offline embedder, and feel why the threshold is dangerous.
- Simulate provider prompt-cache prefix reuse — and catch the **timestamp killer** that silently zeroes the hit rate.
- Meter the **retrieval cost plane** (embedding / reranker / index) that the generation meter never sees.
- Route **prefix-aware** so same-prefix requests reuse a KV-cache instead of each paying full prefill.

**Prereqs:** `40-01-token-accounting-and-attribution`; Ch 11 (cache-aside) and Ch 13 (vector similarity) read.

**Runs free & offline.** Mock model + a tiny **seeded** offline embedder; the query set is committed in `data/queries.csv` with deliberate exact-repeats and paraphrase-pairs. No API key, no network.
"""),
    code(r"""
# Setup — imports, env, and the MOCK switch.
import os
import csv
import json
import hashlib
import random
import math

from dotenv import load_dotenv

load_dotenv()

# MOCK=1 (default): offline mock model + deterministic local embedder. The cache logic
# is identical against a live provider; mocking just makes hit rates reproducible.
MOCK = os.getenv("COMPANION_MOCK", "1") == "1"

random.seed(40)  # the offline embedder is seeded so cosine similarity is deterministic

DATA = os.path.join(os.getcwd(), "data")
print("MOCK mode:", MOCK, "— offline, no API key needed" if MOCK else "— LIVE (would call the SDK)")
"""),
    md(r"""
## A mock model that *counts* what it generated

To measure savings we need a model call that records what it cost. This stand-in returns a canned answer and tracks generated output tokens, so "tokens saved by the cache" is a real, computed number rather than a claim.
"""),
    code(r"""
GEN_LOG = {"calls": 0, "output_tokens": 0}


def mock_generate(prompt: str) -> str:
    """A canned 'model' that meters itself. Deterministic; no network."""
    GEN_LOG["calls"] += 1
    answer = f"[answer to: {prompt[:48]}...]"
    GEN_LOG["output_tokens"] += 60  # pretend each fresh answer is ~60 output tokens
    return answer


def reset_gen():
    GEN_LOG["calls"] = 0
    GEN_LOG["output_tokens"] = 0
"""),
    md(r"""
## Layer 1 — exact cache (`cache_key`)

The book's exact cache is the cache-aside pattern from Ch 11, with the key derived by **hashing the full request** (model + messages + params). A hit is, by construction, the right answer. We replay a repeating workload and watch the hit rate.
"""),
    code(r"""
def cache_key(model: str, messages: list, **params) -> str:
    payload = json.dumps(
        {"model": model, "messages": messages, "params": params},
        sort_keys=True,
    )
    return "llm:" + hashlib.sha256(payload.encode()).hexdigest()


EXACT_CACHE: dict[str, str] = {}


def cached_call(model, messages, **params):
    key = cache_key(model, messages, **params)
    if (hit := EXACT_CACHE.get(key)) is not None:
        return hit, True            # cache hit
    text = mock_generate(messages[-1]["content"])
    EXACT_CACHE[key] = text
    return text, False              # miss -> generated


def load_queries(path):
    with open(path, newline="", encoding="utf-8") as f:
        return [(row["tenant"], row["query"]) for row in csv.DictReader(f)]


queries = load_queries(os.path.join(DATA, "queries.csv"))
reset_gen()
EXACT_CACHE.clear()

hits = 0
for tenant, q in queries:
    # NOTE: scope the key per tenant so one customer's answer can't leak to another.
    msgs = [{"role": "user", "content": q}]
    _, was_hit = cached_call("claude-haiku-4-5", msgs, tenant=tenant)
    hits += was_hit

print(f"{len(queries)} queries, exact-cache hits: {hits}  "
      f"({hits/len(queries)*100:.0f}% hit rate)")
print(f"model calls actually made: {GEN_LOG['calls']}  "
      f"(saved {len(queries) - GEN_LOG['calls']} generations)")
"""),
    md(r"""
**What you just saw.** The exact cache only fires on *byte-identical* repeats — "how do I reset my password" hits, but "password reset steps" is a complete miss even though it wants the same answer. Safe, but its hit rate collapses the moment users phrase things freely. That gap is exactly what the next layer attacks.
"""),
    md(r"""
## Layer 2 — semantic cache (and its dangerous threshold)

A semantic cache embeds the incoming query and serves a stored answer when a *similar enough* past query exists (cosine similarity above a threshold, the vector machinery from Ch 13). It catches paraphrases. Its danger is the threshold — and a real trap lives in our query set: **"fee for plan A"** and **"fee for plan B"** sit a hair apart in embedding space but have *opposite* answers.

Our embedder is a tiny **seeded, offline** hashing embedder — not a real model, but deterministic and good enough to *feel* the threshold trade-off without a network call.
"""),
    code(r"""
def embed(text: str, dim: int = 64) -> list[float]:
    """Deterministic offline embedder: hash tokens into a bag-of-words vector.

    Not a real semantic model — but stable and seeded, so similarity is reproducible
    and the threshold lesson is visible without any API call.
    """
    vec = [0.0] * dim
    for tok in text.lower().split():
        h = int(hashlib.sha256(tok.encode()).hexdigest(), 16)
        vec[h % dim] += 1.0
    norm = math.sqrt(sum(v * v for v in vec)) or 1.0
    return [v / norm for v in vec]


def cosine(a, b):
    return sum(x * y for x, y in zip(a, b))


class SemanticCache:
    def __init__(self, threshold: float):
        self.threshold = threshold
        self.store: dict[str, list] = {}   # tenant -> [(embedding, query, answer)]

    def get(self, tenant, query):
        qv = embed(query)
        best, best_sim = None, -1.0
        for ev, q, ans in self.store.get(tenant, []):   # per-tenant scope: never cross tenants
            sim = cosine(qv, ev)
            if sim > best_sim:
                best, best_sim = (q, ans), sim
        if best is not None and best_sim >= self.threshold:
            return best[1], best_sim, best[0]
        return None, best_sim, None

    def put(self, tenant, query, answer):
        self.store.setdefault(tenant, []).append((embed(query), query, answer))
"""),
    md(r"""
## 🔮 Predict: what does a too-loose threshold do?

We'll run the same queries through a semantic cache at a **loose** threshold (`0.80`) and a **conservative** one (`0.95`). The query set deliberately contains the `plan A` / `plan B` pair.

**Predict, before running:** at the loose threshold, will "what is the fee for plan B" be served the *cached "plan A" answer*? And which threshold gives the higher hit rate — and is higher better here? Write your guess, then run it.
"""),
    code(r"""
def run_semantic(threshold):
    reset_gen()
    cache = SemanticCache(threshold)
    hits, wrong = 0, 0
    for tenant, q in queries:
        cached, sim, _ = cache.get(tenant, q)
        if cached is not None:
            hits += 1
            # Detect a dangerous near-miss: a 'plan B' query served the 'plan A' answer.
            if "plan b" in q.lower() and "plan a" in cached.lower():
                wrong += 1
        else:
            ans = mock_generate(q)
            cache.put(tenant, q, ans)
    return hits, wrong, GEN_LOG["calls"]


for thr in (0.80, 0.95):
    hits, wrong, calls = run_semantic(thr)
    print(f"threshold {thr:.2f}: {hits:>2d} hits, {wrong} WRONG-answer hits, "
          f"{calls} model calls")
"""),
    md(r"""
**What you just saw.** The loose threshold serves more "hits" — including, dangerously, the **plan A answer to a plan B question**. That near-miss reads to the user as a bug, not a cache. The conservative threshold gives up some hit rate to stay correct. The semantic cache is the one layer where a higher hit rate can be *worse*. Keep the threshold conservative, scope keys **per tenant** (done above), and use it only where near-misses are tolerable.
"""),
    md(r"""
## Layer 3 — provider prompt cache (prefix reuse), and the killer

The provider reuses computation for a *prefix* of your prompt — system prompt, tool definitions, shared context — charging cached tokens at a fraction of input price. It is a **strict prefix match**: order stable-first (frozen system prompt, deterministic tools), keep volatile content (timestamps, the user's question) last. A single early-byte change invalidates everything after it.

We simulate prefix-match savings, then reproduce the classic killer: a **timestamp in the system prompt** silently drops the hit rate to zero — *no error, just full price*.
"""),
    code(r"""
def shared_prefix_len(a: str, b: str) -> int:
    """Length of the common leading substring — the provider's cacheable prefix."""
    n = 0
    for ca, cb in zip(a, b):
        if ca != cb:
            break
        n += 1
    return n


CACHE_READ_RATE = 0.10  # cached prefix tokens cost ~1/10th of fresh input here


def prefill_cost(prompt: str, previous: str | None):
    """Tokens billed at full price vs. read from the prompt cache. ~4 chars/token."""
    if previous is None:
        return len(prompt) / 4, 0.0
    reuse = shared_prefix_len(prompt, previous)
    fresh = (len(prompt) - reuse) / 4
    cached = reuse / 4
    return fresh, cached


STATIC_SYSTEM = (
    "You are a support agent. Follow policy. Tools: lookup_order, issue_refund. "
)
# GOOD: volatile user question appended AFTER a frozen prefix.
good_prompts = [STATIC_SYSTEM + "User: where is my order?",
                STATIC_SYSTEM + "User: how do I get a refund?"]
fresh_g, cached_g = prefill_cost(good_prompts[1], good_prompts[0])

# BAD: a timestamp interpolated into the SYSTEM prompt changes the very first bytes.
bad_prompts = [f"Current time: 2026-06-20 14:32:07. {STATIC_SYSTEM}User: where is my order?",
               f"Current time: 2026-06-20 14:32:09. {STATIC_SYSTEM}User: how do I get a refund?"]
fresh_b, cached_b = prefill_cost(bad_prompts[1], bad_prompts[0])

print(f"stable-prefix prompt : fresh={fresh_g:5.1f} tok  cached={cached_g:5.1f} tok  "
      f"(cache_read>0  -> WORKING)")
print(f"timestamped prompt   : fresh={fresh_b:5.1f} tok  cached={cached_b:5.1f} tok  "
      f"(cache_read==0 -> KILLED)")
"""),
    md(r"""
## ⚠️ Pitfall: the prompt-cache killer

A timestamp interpolated into the system prompt — `Current time: 2026-06-20 14:32:07` — changes every request and silently reduces your hit rate to **zero**. No error, no warning, just full price on every call. The diagnosis is mechanical: when cached-token counts read zero on traffic that *should* repeat, **diff two rendered prompts byte by byte** — the invalidator is in the first place they differ. And always **verify** via `cache_read_input_tokens` on the response; never assume the cache is working.
"""),
    code(r"""
def first_diff(a: str, b: str) -> int:
    return shared_prefix_len(a, b)  # first differing index == shared prefix length


idx = first_diff(bad_prompts[0], bad_prompts[1])
print("byte-diff of the two timestamped prompts:")
print(f"  first difference at index {idx}: "
      f"{bad_prompts[0][idx-3:idx+3]!r} vs {bad_prompts[1][idx-3:idx+3]!r}")
print("  -> the volatile timestamp sits BEFORE the static system prompt, so nothing caches.")
print("\nFix: move volatile content to the END; verify cache_read_input_tokens > 0 in prod.")
"""),
    md(r"""
## Prompt compression — shrink what you send

Compression is a family of habits, not one trick: trim conversation history by summarizing old turns, prune verbose tool results to the fields the model needs, and dedupe retrieved chunks before stuffing them into context. Tokens you don't send are also tokens the model doesn't have to *read* — fewer tokens means lower latency and often **better** attention.
"""),
    code(r"""
def compress_context(history: list[str], tool_results: list[dict], chunks: list[str]):
    """Three compression habits, measured. Returns (before_tokens, after_tokens)."""
    def toks(s):
        return len(s) / 4

    before = sum(toks(h) for h in history) \
        + sum(toks(json.dumps(t)) for t in tool_results) \
        + sum(toks(c) for c in chunks)

    # 1) Summarize old turns: replace all but the last 2 with a short summary.
    summarized = ["(summary of earlier turns)"] + history[-2:] if len(history) > 2 else history
    # 2) Prune tool results to needed fields only.
    pruned = [{"id": t["id"], "status": t["status"]} for t in tool_results]
    # 3) Dedupe retrieved chunks.
    deduped = list(dict.fromkeys(chunks))

    after = sum(toks(h) for h in summarized) \
        + sum(toks(json.dumps(t)) for t in pruned) \
        + sum(toks(c) for c in deduped)
    return before, after


history = [f"turn {i}: some back-and-forth text that piles up over a long agent run" for i in range(8)]
tool_results = [{"id": i, "status": "ok", "raw": "x" * 400, "debug": "y" * 200} for i in range(3)]
chunks = ["retrieved passage about refunds"] * 4 + ["a distinct passage about shipping"]

before, after = compress_context(history, tool_results, chunks)
print(f"context before compression: {before:7.0f} tokens")
print(f"context after  compression: {after:7.0f} tokens  "
      f"({(1 - after/before)*100:.0f}% smaller -> cheaper AND faster)")
"""),
    md(r"""
## The retrieval cost plane — line items the generation meter never sees

A retrieval pipeline spends money the completion meter is blind to. Three line items hide there: **embedding-API calls** (every doc indexed and every query embedded), **reranker calls** (a cross-encoder scores every candidate for every query), and **vector-store infrastructure** (RAM/disk you rent whether or not anyone queries). For a retrieval-heavy agent these can *rival* generation cost — so meter them with the **same** per-feature, per-tenant labels.
"""),
    code(r"""
# Illustrative unit prices for the retrieval plane (config, not hardcoded in logic).
RETRIEVAL_PRICES = {
    "embed_per_1k_tokens": 0.0001,
    "rerank_per_candidate": 0.00005,
    "index_hourly_usd": 0.04,
}


def retrieval_cost(n_queries, tokens_per_query, candidates_per_query, hours=1):
    embed = n_queries * tokens_per_query / 1000 * RETRIEVAL_PRICES["embed_per_1k_tokens"]
    rerank = n_queries * candidates_per_query * RETRIEVAL_PRICES["rerank_per_candidate"]
    infra = hours * RETRIEVAL_PRICES["index_hourly_usd"]
    return {"embedding": embed, "reranker": rerank, "index_infra": infra}


# Naive: re-embed every query, rerank the top 100 candidates reflexively.
naive = retrieval_cost(n_queries=10_000, tokens_per_query=40, candidates_per_query=100)
# Optimized: cache query embeddings (50% recur), right-size the candidate set to 20.
opt = retrieval_cost(n_queries=5_000, tokens_per_query=40, candidates_per_query=20)

print("retrieval cost plane (per hour at 10k queries):")
for k in naive:
    print(f"  {k:12s} naive ${naive[k]:7.4f}   optimized ${opt[k]:7.4f}")
print(f"  {'TOTAL':12s} naive ${sum(naive.values()):7.4f}   "
      f"optimized ${sum(opt.values()):7.4f}")
print("\nCache query embeddings, batch them, right-size the reranker/candidate set.")
"""),
    md(r"""
## Cache-aware (prefix-affinity) routing

The provider's prompt cache and the gateway's KV-cache both key off a **shared prompt prefix** — but a cache only pays off if requests sharing that prefix land where the cache lives. Round-robin **scatters** same-prefix requests across replicas, so each pays full prefill. The lever is the **routing key**: hash on the stable prefix (tenant / agent / prompt-version) so the second request reuses the first's KV-cache.
"""),
    code(r"""
N_REPLICAS = 4


def route_round_robin(requests):
    return [i % N_REPLICAS for i, _ in enumerate(requests)]


def route_prefix_aware(requests):
    # Hash the STABLE prefix (here: tenant + agent), not the volatile question.
    return [int(hashlib.sha256(f"{t}/{agent}".encode()).hexdigest(), 16) % N_REPLICAS
            for (t, agent, _q) in requests]


def kv_cache_hits(requests, routing):
    """A replica reuses its KV-cache when it sees the same prefix it saw before."""
    seen_per_replica: dict[int, set] = {}
    hits = 0
    for (t, agent, _q), replica in zip(requests, routing):
        prefix = f"{t}/{agent}"
        bucket = seen_per_replica.setdefault(replica, set())
        if prefix in bucket:
            hits += 1
        else:
            bucket.add(prefix)
    return hits


# 12 requests from 2 tenants/agents — lots of shared prefixes to exploit.
reqs = [("acme", "support_agent", f"q{i}") for i in range(6)] + \
       [("globex", "faq_bot", f"q{i}") for i in range(6)]

rr = route_round_robin(reqs)
pa = route_prefix_aware(reqs)
print(f"round-robin routing : KV-cache hits = {kv_cache_hits(reqs, rr):>2d} / {len(reqs)}")
print(f"prefix-aware routing: KV-cache hits = {kv_cache_hits(reqs, pa):>2d} / {len(reqs)}")
print("\nSame requests, same caches — only the routing KEY changed.")
"""),
    md(r"""
**What you just saw.** Identical traffic, identical cache machinery — the *only* change is the routing key, and the prefix-aware router lands same-prefix requests on the same replica so the KV-cache actually hits. A cache you paid to build is worthless if the load balancer keeps moving the request away from it.
"""),
    md(r"""
## 🎯 Senior lens

Apply optimizations **cheapest-first**: right-size the model → prompt caching → exact caching → batch API → *then* semantic caching and aggressive compression, which carry quality risk. Most teams reach for the risky end first because it sounds sophisticated; run the list top-down and you usually cut spend severalfold before touching anything that can degrade answers. Two more senior instincts from §40.4: put **embedding and reranker calls through the same metered chokepoint** as completions — a RAG agent optimized only on generation tokens still bleeds through an unmetered embedding pipeline — and make the router **cache-aware**, because a cache that never hits is just latency you paid for.
"""),
    md(r"""
## Recap

- Three cache layers answer different questions: **exact** (identical request), **semantic** (similar request), **provider prompt** (shared prefix). Don't conflate them.
- Exact cache is safe but collapses on free phrasing; semantic cache catches paraphrases but its **threshold** can serve wrong near-misses — keep it conservative and **scope keys per tenant**.
- Provider prompt caching needs a **stable prefix**; a timestamp in the system prompt is the classic killer — diff prompts byte-by-byte and verify `cache_read_input_tokens > 0`.
- **Prompt compression** (summarize history, prune tool results, dedupe chunks) cuts cost *and* latency.
- The **retrieval cost plane** (embedding / reranker / index) can rival generation cost — meter it with the same labels and right-size it.
- **Prefix-aware routing** makes the cache you paid to build actually hit — the lever is the routing key.
- Order of leverage: **right-size model → prompt cache → exact cache → batch → semantic/compression.**
"""),
    md(r"""
## Exercises

Each one *changes* something and asks you to predict first.

1. **Tune the threshold.** Sweep the semantic threshold from `0.70` to `0.99` and plot (print) hit rate vs. wrong-answer count. Predict the threshold where wrong-answer hits first appear, then find it.
2. **Move the timestamp.** Rewrite `bad_prompts` to put the timestamp at the *end* (after the user question). Predict the new cached-token count, then compute it and confirm the cache revives.
3. **Right-size the reranker.** In `retrieval_cost`, find the `candidates_per_query` at which reranker cost equals embedding cost for 10k queries. Predict above/below 50 first.
4. **Break prefix routing.** Change `route_prefix_aware` to hash the *full request* (including the question). Predict the KV-cache hit count, then run it — and explain why it collapses to round-robin.
"""),
    code(r"""
# Exercise 1 — your code here.
"""),
    code(r"""
# Exercise 2 — your code here.
"""),
    code(r"""
# Exercise 3 — your code here.
"""),
    md(r"""
## Next

- **Next notebook:** [`40-03-latency-budgets-parallelism-and-speculation.ipynb`](40-03-latency-budgets-parallelism-and-speculation.ipynb) — cost is paid by the company, latency by the user; engineer it on purpose.
- **Book:** §40.2 (caching & compression), §40.4 (retrieval cost plane + prefix-aware routing), the token-optimization playbook table, and the §40 checklist; Ch 11 (cache-aside), Ch 13 (vector similarity).
- **Blueprint this feeds:** [`blueprints/llm-gateway/`](../../../blueprints/llm-gateway/) (the three cache layers + cache-aware routing) and [`blueprints/rag-pipeline/`](../../../blueprints/rag-pipeline/) (the retrieval cost plane).
- **Capstone:** advances [`capstone/llm/gateway.py`](../../../capstone/llm/gateway.py) — exact + semantic + prompt caching and prefix-aware routing (`checkpoints/ch40-cost-and-caching`).
"""),
]

# ===========================================================================
# 40-03 · latency budgets, parallelism, and speculation (concept-lab)
# ===========================================================================

nb3 = [
    md(r"""
# Latency budgets, parallelism & speculation: engineer latency on purpose

> 📓 *Companion to* **Modern Agentic AI Engineer** *· Ch 40 §40.5 · type: concept-lab*

**The promise:** by the end you can decompose a request's latency into a per-stage budget, cut the biggest line with bounded parallelism, judge when speculation pays, and gate cost/latency regressions in CI.
"""),
    md(r"""
## 🧠 Why this matters

Cost is paid by the company; **latency is paid by the user**, on every single interaction. The discipline is the one you applied to web services in Ch 24 — set a budget, decompose it, attack the biggest stage — with two LLM-specific twists:

- **TTFT, not total**, is the metric for chat. A response that *starts* in 400 ms feels fast even at 8 s total; the same answer delivered all at once after 8 s feels broken.
- **Output tokens dominate** generation time. Models decode sequentially, so a 2,000-token answer takes ~10× a 200-token one. The fastest latency fix is often *ask for less*.

Everything here runs on a **deterministic, seeded timing simulator** — no network, no real latency, fully reproducible. See §40.5.
"""),
    md(r"""
## Objectives & prereqs

**By the end you can:**
- Separate **TTFT** from total time and explain why streaming changes *perceived* latency.
- Model generation time as ∝ output tokens and predict the speedup from halving `max_tokens`.
- Reproduce the book's **per-stage latency budget** table and give each stage an owner.
- Run the book's bounded `summarize_all` (asyncio.gather + a Semaphore) over a mock async client.
- Model the three **speculative patterns** and judge when wasted tokens buy wall-clock.
- Wire a **cost+latency budget assertion** that fails offline when a change blows the budget.

**Prereqs:** `40-01`, `40-02`; Ch 4 (async) and Ch 24 (latency budgets) read.

**Runs free & offline.** Mock async client with *simulated* latencies; deterministic and seeded. No API key, no real waiting.
"""),
    code(r"""
# Setup — imports, env, and the MOCK switch.
import os
import asyncio
import random

from dotenv import load_dotenv

load_dotenv()

# MOCK=1 (default): a mock async client with simulated (not real) latencies. The
# parallelism structure is identical against a live AsyncAnthropic client.
MOCK = os.getenv("COMPANION_MOCK", "1") == "1"

random.seed(40)  # the timing model is seeded so every number below is reproducible

print("MOCK mode:", MOCK, "— offline, deterministic" if MOCK else "— LIVE (would call AsyncAnthropic)")
"""),
    md(r"""
## TTFT vs. total — why streaming *feels* fast

Streaming doesn't change total wall-clock; it changes *when the first token lands*. We model one call as a fixed TTFT followed by steady decode, and compare what a buffered vs. a streamed user experiences.
"""),
    code(r"""
TTFT_S = 0.40          # seconds before the first token (network + queue + prefill)
DECODE_RATE = 50.0     # tokens / second
OUTPUT_TOKENS = 400

total = TTFT_S + OUTPUT_TOKENS / DECODE_RATE
print(f"total wall-clock (both modes)   : {total:.2f}s")
print(f"first output, BUFFERED          : {total:.2f}s  (spinner the whole time)")
print(f"first output, STREAMED          : {TTFT_S:.2f}s  (user reads along)")
print("\nSame total. Streaming transforms PERCEIVED latency — so budget TTFT separately.")
"""),
    md(r"""
## 🔮 Predict: halve `max_tokens`

Generation time is roughly proportional to output tokens (decode is sequential). The current call generates 400 output tokens.

**Predict, before running:** if you halve `max_tokens` so the model emits ~200 tokens instead of 400, what happens to *total* latency — does it halve, drop by a third, or barely move? Remember TTFT is fixed. Write your guess, then measure.
"""),
    code(r"""
def gen_latency(output_tokens, ttft=TTFT_S, decode_rate=DECODE_RATE):
    """time ~= TTFT + output_tokens / decode_rate. Output dominates the tail."""
    return ttft + output_tokens / decode_rate


full = gen_latency(400)
half = gen_latency(200)
print(f"max_tokens ~400 -> {full:.2f}s")
print(f"max_tokens ~200 -> {half:.2f}s")
print(f"speedup: {full/half:.2f}x  (NOT 2x — the fixed TTFT floor dilutes the gain)")
print("\n'Ask for less' is latency engineering — but TTFT sets a floor you can't decode past.")
"""),
    md(r"""
**What you just saw.** Halving output does *not* halve latency, because TTFT is a fixed floor that decode time is added on top of. Output discipline is real latency engineering — but only the decode portion shrinks, so the win is biggest on long answers and smallest on short ones.
"""),
    md(r"""
## The per-stage latency budget

A budget per stage means a regression has an **owner** — not a vague "it feels slow." This reproduces the book's table for a streaming RAG chat turn. The numbers are illustrative; the discipline is having a line and a lever per stage.
"""),
    code(r"""
LATENCY_BUDGET = [
    # stage,            budget_ms, owner,         levers
    ("network + auth",        50,  "platform",    "keep-alive connections, regional endpoints"),
    ("retrieval",            150,  "search",      "index tuning, caching, smaller candidate sets (Ch 13)"),
    ("TTFT",                 600,  "llm-gateway", "prompt caching, shorter prompts, faster tier"),
    ("generation",          3000,  "llm-gateway", "shorter outputs, streaming so the user reads along"),
    ("tool calls",           400,  "agent",       "parallelize independent calls, cache tool results"),
]

print(f"{'stage':16s} {'budget':>8s}  {'owner':12s} levers")
total_budget = 0
for stage, ms, owner, levers in LATENCY_BUDGET:
    total_budget += ms
    print(f"{stage:16s} {ms:>6d}ms  {owner:12s} {levers}")
print(f"{'TOTAL':16s} {total_budget:>6d}ms")
print("\nA regression in any line now has exactly one owner to page.")
"""),
    md(r"""
## Parallelism — the book's bounded `summarize_all`

Agents are full of sequential habits that don't need to be sequential. Fan-out over ten documents shouldn't be a loop — run it with **bounded** concurrency. This is the book's `summarize_all`: `asyncio.gather` plus a `Semaphore` to respect rate limits, over a **mock** async client with simulated per-call latency.
"""),
    code(r"""
class MockAsyncClient:
    """Stands in for anthropic.AsyncAnthropic. Each call 'takes' a simulated time
    we sleep for a scaled, tiny real fraction so the notebook stays fast and offline."""
    async def summarize(self, doc: str) -> str:
        sim_latency_s = 0.5  # each call 'costs' ~0.5s of model time
        await asyncio.sleep(sim_latency_s * 0.02)  # scaled down so the cell runs fast
        return f"summary({doc})"


aclient = MockAsyncClient()


async def summarize_all(docs, limit: int = 8):
    sem = asyncio.Semaphore(limit)  # respect rate limits (Ch 29 backpressure)

    async def bounded(doc):
        async with sem:
            return await aclient.summarize(doc)

    return await asyncio.gather(*(bounded(d) for d in docs))


import time as _time
docs = [f"doc-{i}" for i in range(10)]

start = _time.monotonic()
results = await summarize_all(docs, limit=8)
elapsed = _time.monotonic() - start
print(f"summarized {len(results)} docs at concurrency 8 in {elapsed*50:.1f} 'model-seconds'")
print("Ten docs at concurrency eight finish in ~the time of two — not ten.")
"""),
    md(r"""
## ⚠️ Pitfall: unbounded `gather` meets the rate limiter

Drop the semaphore and `gather` fires *all* requests at once. For ten docs that's fine; for a thousand it slams straight into the provider's rate limiter — `429`s, retries, and a slower result than the bounded version (Ch 29's backpressure lesson, replayed). The semaphore is not optional at scale; it is the thing standing between you and your own rate limit.
"""),
    code(r"""
RATE_LIMIT = 8  # provider allows 8 concurrent in-flight requests


def simulate_inflight(n_requests, concurrency):
    """How many requests would exceed the provider's concurrency limit at peak?"""
    peak = min(n_requests, concurrency)
    rejected = max(0, peak - RATE_LIMIT)
    return peak, rejected


for conc in (8, 100):
    peak, rejected = simulate_inflight(1000, conc)
    label = "bounded (Semaphore=8)" if conc == 8 else "UNBOUNDED gather"
    print(f"{label:22s}: peak in-flight {peak:>4d}, over rate limit by {rejected:>4d} "
          f"-> {'fine' if rejected == 0 else '429s + retries (slower!)'}")
"""),
    md(r"""
## Speculative patterns — spend tokens to buy time

When parallelism *within* a task is exhausted, spend a little cost to buy latency. Three patterns recur, and all three trade wasted tokens on the losing branch for wall-clock on the winning one — a good trade exactly when latency outvalues tokens:

- **Race the tiers** — fire cheap + frontier together; serve the cheap answer if a quick check accepts it, else the frontier result already in flight.
- **Prefetch** — while the user reads, speculatively run the retrieval (or draft) for the likely follow-up.
- **Optimistic tool calls** — start the lookup the plan almost certainly needs while the model is still reasoning.

> ⚠️ Don't confuse these app-level patterns with Ch 39's in-decoder *speculative decoding* — different layer entirely.
"""),
    code(r"""
def race_the_tiers(cheap_ms, frontier_ms, cheap_accept_prob, cheap_tokens, frontier_tokens):
    """Model 'race the tiers': both run; wall-clock is the one we serve, cost is both."""
    # We serve the cheap answer when it's accepted (arrives first); else the frontier.
    expected_latency = (cheap_accept_prob * cheap_ms
                        + (1 - cheap_accept_prob) * frontier_ms)
    wasted_tokens = (cheap_accept_prob * frontier_tokens      # frontier wasted when cheap wins
                     + (1 - cheap_accept_prob) * cheap_tokens)  # cheap wasted when it loses
    return expected_latency, wasted_tokens


seq_latency = 300 + 1500   # cheap-then-fallback-to-frontier, in series
race_latency, wasted = race_the_tiers(
    cheap_ms=300, frontier_ms=1500, cheap_accept_prob=0.7,
    cheap_tokens=60, frontier_tokens=200,
)
print(f"sequential (cheap, then frontier on reject): {seq_latency:.0f}ms worst case")
print(f"race the tiers (both in flight)           : {race_latency:.0f}ms expected")
print(f"  cost of the race: ~{wasted:.0f} wasted tokens on the losing branch")
print("\nGood trade when a user-facing ms is worth more than a token. Usually it is.")
"""),
    md(r"""
**What you just saw.** Racing the tiers spends tokens on a branch you throw away, but it collapses the worst-case latency — you never pay the full frontier wait *plus* a failed cheap attempt in series. Speculation is the deliberate purchase of wall-clock with tokens; it pays exactly when latency outvalues tokens, which for user-facing products it usually does.
"""),
    md(r"""
## Regression guard — fail the build when the budget blows

The CI hook the book wants: assert this run stays under N tokens / T ms, so a prompt change that doubles tokens **fails offline** before it ships. Cost and latency budgets belong in CI alongside your tests (feeds `templates/github-actions-ci/`).
"""),
    code(r"""
def assert_within_budget(*, tokens, latency_ms, max_tokens, max_latency_ms):
    """Raise if a run blows its cost or latency budget. This is your CI gate."""
    problems = []
    if tokens > max_tokens:
        problems.append(f"tokens {tokens} > budget {max_tokens}")
    if latency_ms > max_latency_ms:
        problems.append(f"latency {latency_ms:.0f}ms > budget {max_latency_ms}ms")
    if problems:
        raise AssertionError("BUDGET REGRESSION: " + "; ".join(problems))
    return True


# A 'good' run passes.
ok = assert_within_budget(tokens=1800, latency_ms=2200, max_tokens=4000, max_latency_ms=4200)
print("baseline run within budget:", ok)

# Simulate a prompt change that doubled the tokens — the guard catches it offline.
try:
    assert_within_budget(tokens=4200, latency_ms=2200, max_tokens=4000, max_latency_ms=4200)
except AssertionError as e:
    print("CI would FAIL ->", e)
"""),
    md(r"""
## 🎯 Senior lens

Cost and latency couple through **one** decision: *how much model do you buy per step?* Routing a step to a smaller model improves **both** at once — fewer parameters and shorter outputs mean less compute per token and fewer tokens — which makes model routing the single highest-leverage knob in this chapter, and the gateway (Ch 39) the place where it turns. Profile a slow agent like any distributed system: find the critical path first (Ch 23 traces), *then* tune. The number of **sequential** model calls usually dominates everything else, so the senior move is structural — combine steps, parallelize independent branches, route trivial decisions to fast models or plain code — long before reaching for parameter tweaks.
"""),
    md(r"""
## 📋 The §40 cost/latency production checklist

A copyable, end-of-chapter checklist. Paste it into a PR template or an ADR — every item maps to something you built across 40-01 / 40-02 / 40-03.
"""),
    code(r#"""
CH40_CHECKLIST = """
Cost / Latency production checklist (book §40):

[ ] Metering        — every call records tokens, cost, latency, model, feature, tenant
                      at the GATEWAY, not scattered through app code.        (40-01)
[ ] Unit economics  — cost per completed TASK (not per request) on a weekly dashboard. (40-01)
[ ] Tails           — p95/p99 cost & latency tracked and alerted, not just averages. (40-01)
[ ] Caps            — hard max tokens, agent iterations, per-tenant spend.   (40-01)
[ ] Model routing   — each step on the cheapest model that passes evals (Ch 22).
[ ] Prompt cache    — stable prefix first, volatile last, cache_read verified nonzero. (40-02)
[ ] App caches      — exact cache for repeats; semantic only where near-miss is OK,
                      threshold tested, keys scoped per tenant.              (40-02)
[ ] Batching        — latency-tolerant work on the discounted batch endpoint.
[ ] Streaming       — user-facing responses streamed, TTFT budgeted separately. (40-03)
[ ] Parallelism     — independent calls / fan-out concurrent, bounded by a Semaphore. (40-03)
[ ] Output discipline — concise-output prompts, max_tokens set deliberately.  (40-03)
[ ] Context compaction — long runs summarize history so per-turn tokens stay bounded (Ch 16).
[ ] Regression guard  — cost & latency budgets run in CI so a token-doubling change fails. (40-03)
"""
print(CH40_CHECKLIST)
"""#),
    md(r"""
## Recap

- **TTFT, not total**, is the chat metric; streaming changes *perceived* latency, not the wall-clock — budget it separately.
- **Output tokens dominate** generation time, but TTFT is a fixed floor — halving output does *not* halve latency.
- A **per-stage budget** gives every regression an owner; reproduce the book's table and assign levers.
- **Bounded** `summarize_all` (gather + Semaphore) parallelizes fan-out safely; unbounded gather meets the rate limiter.
- **Speculation** (race the tiers / prefetch / optimistic tool calls) spends wasted tokens to buy wall-clock — worth it when latency outvalues tokens.
- A **regression guard** asserting tokens/latency budgets in CI catches a token-doubling change *offline*.
- Cost and latency couple through one knob — **how much model per step** — and the gateway is where it turns.
"""),
    md(r"""
## Exercises

Each one *changes* something and asks you to predict first.

1. **Find the streaming win.** For what `OUTPUT_TOKENS` does halving `max_tokens` save at least 1 second of *total* latency? Predict above/below 100 tokens, then solve with `gen_latency`.
2. **Tune concurrency.** Re-run `summarize_all` over 40 docs at limits 1, 4, 16. Predict the ordering of wall-clock times and whether limit 16 beats limit 8 here, then measure.
3. **When does racing pay?** In `race_the_tiers`, find the `cheap_accept_prob` at which expected latency equals the frontier-only latency (1500ms). Predict it first.
4. **Tighten the guard.** Set `max_latency_ms=2000` and re-run the baseline through `assert_within_budget`. Predict pass or fail, then explain which stage of the budget table you'd attack to make it pass.
"""),
    code(r"""
# Exercise 1 — your code here.
"""),
    code(r"""
# Exercise 2 — your code here.
"""),
    code(r"""
# Exercise 3 — your code here.
"""),
    md(r"""
## Next

- **End of Ch 40's labs.** Next chapter: [`../41-security-safety-compliance/`](../41-security-safety-compliance/) — spend caps return as a *denial-of-wallet* abuse control on the same meter.
- **Book:** §40.5 (latency budgets, parallelism, speculation), the cost↔latency key idea, and the §40 checklist; Ch 4 (async), Ch 24 (web-service latency budgets), Ch 39 (the routing knob).
- **Blueprint this feeds:** [`blueprints/llm-gateway/`](../../../blueprints/llm-gateway/) (the routing knob, streaming, bounded fan-out) and the CI budget check in [`templates/github-actions-ci/`](../../../templates/github-actions-ci/).
- **Capstone:** advances [`capstone/llm/gateway.py`](../../../capstone/llm/gateway.py) — the metering/budget hooks, caching, and prefix-aware routing the cost dashboard reads (`checkpoints/ch40-cost-and-caching`).
"""),
]

paths = []
paths.append(write("40-01-token-accounting-and-attribution.ipynb", nb1))
paths.append(write("40-02-caching-layers-and-cache-aware-routing.ipynb", nb2))
paths.append(write("40-03-latency-budgets-parallelism-and-speculation.ipynb", nb3))
for p in paths:
    print("wrote", p)
