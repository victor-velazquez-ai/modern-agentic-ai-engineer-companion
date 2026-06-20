"""Generator for 44-01-capstone-tour-one-request.ipynb (walkthrough).

Builds a valid nbformat-4 notebook. Run from this folder:
    python _gen_4401.py
This script is a build tool; the notebook is the deliverable.
"""
import json
import os

cells = []


def md(text: str):
    cells.append({"cell_type": "markdown", "metadata": {}, "source": _lines(text)})


def code(text: str):
    cells.append({
        "cell_type": "code",
        "execution_count": None,
        "metadata": {},
        "outputs": [],
        "source": _lines(text),
    })


def _lines(text: str):
    # Split into a list of lines, each (except the last) keeping its trailing newline,
    # exactly as Jupyter stores source.
    text = text.strip("\n")
    raw = text.split("\n")
    return [line + "\n" for line in raw[:-1]] + [raw[-1]]


# 1. Title + header -----------------------------------------------------------
md(r"""
# One request through every layer — a tour of the capstone

> 📓 *Companion to* **Modern Agentic AI Engineer** · Ch 44 §44.1 · type: walkthrough

**The promise:** by the end you can follow one real request — *"summarize last week's customer feedback and file the top three issues"* — through the **whole** `capstone/`, naming at every hop which **plane** it touches, which `capstone/` directory owns it, and which chapter built it.

This is a **tour of the assembled system, not a from-scratch build.** The book's promise is that *you* build your capstone from the 🔧 Build sections; this notebook is the known-good reference you tour to compare, check, and unblock. It runs **fully offline and free** — `MOCK=1` replays a canned end-to-end trace, no services, no API key.
""")

# 2. Why this matters ---------------------------------------------------------
md(r"""
## 🧠 Why this matters

A capstone is overwhelming as a *directory listing* — a dozen top-level folders, hundreds of files. It becomes legible the moment you stop reading it as files and start reading it as **one request moving through four planes**. That is the trick §44.1 uses: a single trace touches every layer the book built, in order, so the architecture explains itself.

The four planes from Chapter 3 — **model · orchestration · data · infrastructure** — have stayed the load-bearing walls from the first diagram to the last. Every chapter since furnished one plane; nothing replaced the frame. Hold that, and three hundred pages later the map still matches the territory.

The most expensive misconception this tour kills: *the model is the system.* Watch how many hops in the trace are **not** the model — intake, queue, retrieval, the approval gate, the gateway, the stream, the trace export. That is where most of the engineering, and most of the failures, actually live.
""")

# 3. Objectives + prereqs -----------------------------------------------------
md(r"""
## Objectives & prereqs

**By the end you can:**
- Narrate the entire capstone as **one request across four planes**, hop by hop.
- Map each layer of §44.1's table onto a `capstone/` directory **and** the chapters that built it.
- Point at any hop and say which plane it lives in — and which hops are *not* the model.
- Locate the thin-intake / approval-gate / gateway / flywheel moments in both the book and the tree.

**Prereqs:** effectively the whole book — especially Ch 3 (four planes), Ch 12–20 (agent core, MCP, approval gates), Ch 22–23 (evals + observability), Ch 38–41 (frontend, gateway, security), Ch 42 (thin intake). Ideally your own capstone attempt and the Ch 12–41 notebooks. This notebook *reads and traces* the reference `capstone/`; it assumes it is built (or uses `checkpoints/`).

**Packages:** Python standard library only (`json`, `os`, `pathlib`). No external dependency, no API key, no network in `MOCK=1`. The live path (`MOCK=0`) drives the real local `capstone/` via `docker compose` and is **opt-in** and ⚠️ flagged.
""")

# 4. Setup --------------------------------------------------------------------
code(r'''
# Setup — imports, env, and the MOCK switch.
import json
import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()  # reads a local .env if present; never hardcode keys

# MOCK=1 (default) replays a canned end-to-end trace from data/canned_trace.json:
# offline, free, deterministic, no services. MOCK=0 would drive the real local
# capstone/ via `docker compose up` (opt-in, costs real tokens) — see the ⚠️ cell
# near the end. This tour reads known-good state; it never needs a key to teach.
MOCK = os.getenv("COMPANION_MOCK", "1") == "1"

# Where the capstone lives, relative to this notebook (learn/part-11/44-.../).
# We only reference paths for the map; we do not import from it here.
CAPSTONE = Path("../../../capstone")

DATA = Path("data")
print(f"MOCK mode: {MOCK}  (offline, free, deterministic)")
print(f"capstone path (for the map): {CAPSTONE}  exists={CAPSTONE.exists()}")
print("No API key required in MOCK mode. Nothing leaves this machine.")
''')

# 5. Map cell: the layer table onto the tree ----------------------------------
md(r"""
## The capstone, layer by layer (§44.1)

The fastest way to see all of it at once is the §44.1 map: each **layer**, the `capstone/` **directory** that realizes it, and the **chapters** that built it. Nothing here is decorative — remove a layer and a requirement from Chapter 42's method goes unmet.
""")

code(r'''
# The §44.1 layer table, joined to the capstone/ directory tree and the chapters
# that built each layer. Each row links a PLANE -> a directory -> the book.
LAYERS = [
    # (layer,            plane,            capstone dir,                  built in)
    ("Agent core",       "model",          "agents/",                     "Ch 12, 14, 16-17"),
    ("Knowledge",        "data",           "rag/",                        "Ch 13"),
    ("Orchestration",    "orchestration",  "agents/ + mcp/",              "Ch 18-20"),
    ("Quality",          "infrastructure", "evals/",                      "Ch 21-23"),
    ("Backend",          "infrastructure", "app/",                        "Ch 24-26"),
    ("Architecture",     "infrastructure", "app/ (modular monolith)",     "Ch 27-28"),
    ("Data",             "data",           "memory/ + infra/ (pg/redis)", "Ch 30"),
    ("Async",            "infrastructure", "workers/",                    "Ch 29, 31"),
    ("Cloud",            "infrastructure", "infra/ (Terraform)",          "Ch 32-36"),
    ("Frontend",         "infrastructure", "web/",                        "Ch 37-38"),
    ("LLMOps",           "infrastructure", "infra/gateway/",              "Ch 39-41"),
]

w1, w2, w3 = 14, 16, 30
print(f"{'layer':<{w1}}{'plane':<{w2}}{'capstone/ dir':<{w3}}built in")
print("-" * 78)
for layer, plane, d, built in LAYERS:
    print(f"{layer:<{w1}}{plane:<{w2}}{d:<{w3}}{built}")
print("-" * 78)
print(f"{len(LAYERS)} layers, four planes, one system.")
''')

md(r"""
**What you just saw.** Eleven layers, but only **four planes**. Read the `plane` column top to bottom and the whole capstone collapses into Chapter 3's frame: a couple of *model* layers, a couple of *data* layers, the *orchestration* loop, and a stack of *infrastructure* that makes it fast, observable, cheap, and safe. Most of the tree is infrastructure — which is the point.
""")

# 6. Load the canned trace ----------------------------------------------------
md(r"""
## The request, end to end (mock trace)

We now follow one request through the assembled system. In `MOCK=1` we replay a canned trace from `data/canned_trace.json` — the same shape an OpenTelemetry export would produce (Chapter 23), with a `plane`, the owning `capstone/` directory, the chapters, latency, tokens, and cost per span.
""")

code(r'''
# Load the canned end-to-end trace. In MOCK=0 this is where you would instead
# attach to the live capstone's tracer (Ch 23) after `docker compose up`.
def load_trace():
    if MOCK:
        path = DATA / "canned_trace.json"
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    # pragma: no cover - live path, opt-in only (see the ⚠️ cell below)
    raise RuntimeError(
        "MOCK=0 requires the live capstone running (docker compose up) and a key. "
        "This tour is designed to teach in MOCK=1; flip MOCK only when comparing "
        "against your own running system."
    )


trace = load_trace()
spans = trace["spans"]
print(f'request: "{trace["request"]}"')
print(f'tenant: {trace["tenant"]}   run_id: {trace["run_id"]}   spans: {len(spans)}')
''')

# 7. Predict moment -----------------------------------------------------------
md(r"""
## 🔮 Predict: what does intake *not* do?

You are about to print the trace. The very first thing that happens server-side is the **FastAPI intake** (Chapter 42 argued this must stay *thin*). Before you run the next cell, **predict**: in this trace, does the intake hop make a **model call**? Does it do the retrieval, or the summarizing, or file the ticket?

Write your guess. Then run the cell and look at `api.intake`'s `tokens` and `cost_usd`.
""")

code(r'''
# Print the full hop-by-hop trace: seq, plane, hop, owning capstone dir, chapters,
# latency, tokens, cost. This is the single end-to-end trace §44.1 walks.
def print_trace(spans):
    print(f"{'#':>2}  {'plane':<14} {'hop':<34} {'dir':<22} {'ms':>6} {'tok':>5} {'$':>8}")
    print("-" * 100)
    for s in spans:
        print(
            f"{s['seq']:>2}  {s['plane']:<14} {s['hop']:<34} "
            f"{s['capstone_dir']:<22} {s['ms']:>6.1f} {s['tokens']:>5} {s['cost_usd']:>8.5f}"
        )
    print("-" * 100)
    tot_ms = sum(s["ms"] for s in spans)
    tot_tok = sum(s["tokens"] for s in spans)
    tot_usd = sum(s["cost_usd"] for s in spans)
    print(f"{'':>2}  {'TOTAL':<14} {'':<34} {'':<22} {tot_ms:>6.1f} {tot_tok:>5} {tot_usd:>8.5f}")
    return tot_ms, tot_tok, tot_usd


tot_ms, tot_tok, tot_usd = print_trace(spans)
''')

md(r"""
**What you just saw.** `api.intake` shows **0 tokens, \$0.00**. The intake persists a run row, enqueues the job, and returns a stream handle — and that is *all* it does (Chapter 42). It makes no model call, so a model-provider brownout or a slow agent run **cannot take the intake down**: it stays fast and available because the expensive, failure-prone work is pushed to the worker behind the queue. Thin intake is a reliability decision, and the trace makes it literal.
""")

# 8. Worker hop ---------------------------------------------------------------
md(r"""
## The worker hop: plan → retrieve → tool-via-MCP-with-approval → checkpoint

Once the worker (Chapter 31) dequeues the run, the **agent core** drives the real work. Watch four things happen in order in the trace: the agent **plans** (`agent.plan`), **retrieves** feedback from pgvector (`rag.retrieve`, the *data* plane, Chapter 13), **summarizes** it, then calls the **ticketing tool through MCP** (`mcp.tool.create_ticket`, Chapters 18–20) — and notice that one tag.
""")

code(r'''
# Zoom into the worker's hops and surface the approval gate explicitly.
def show_worker_hops(spans):
    worker_planes = {"model", "data", "orchestration"}
    for s in spans:
        if s["plane"] in worker_planes:
            gate = "  <-- APPROVAL GATE" if "APPROVAL" in s["hop"] else ""
            print(f"  [{s['plane']:<13}] {s['hop']:<34} ({s['chapters']}){gate}")
            print(f"                  {s['detail']}")


show_worker_hops(spans)
''')

md(r"""
**What you just saw.** Filing issues is a **side effect** — irreversible from the system's point of view — so the `create_ticket` tool call is **gated by a human approval** (Chapter 20), not fired automatically. The summarize/retrieve steps are not gated (they are read-only); only the action that *changes the outside world* is. And every step is **checkpointed** (Chapter 14), so if the worker dies mid-run, it resumes from the last good step instead of re-charging you for the whole agent run.
""")

# 9. Gateway + SSE hop --------------------------------------------------------
md(r"""
## The gateway and the stream

Every model call in the worker did not go straight to a provider — it went **through the gateway** (`gateway.route`, Chapter 39): routed to the right model, budget-checked against the per-tenant cap, and breaker-protected so a provider outage trips a fallback instead of cascading. Meanwhile tokens stream back to the browser over **SSE** (`sse.stream`, Chapter 38), where the UI renders steps, citations, and — crucially — the **approval card** the human acted on above.
""")

code(r'''
# The infrastructure hops that wrap the model work: gateway + stream.
for s in spans:
    if s["hop"] in ("gateway.route", "sse.stream"):
        print(f"  [{s['plane']:<13}] {s['hop']:<16} ({s['chapters']})")
        print(f"                  {s['detail']}")
''')

# 10. Exhaust / flywheel hop --------------------------------------------------
md(r"""
## The exhaust hop: trace → observability → the flywheel

The request is answered, but the system is not done with it. The **full trace** — every span, token count, and dollar — lands in **observability** (Chapter 23). And the one **wrong retrieval** the agent made (flagged in the trace) gets queued to be **promoted into the eval set tomorrow** (Chapter 22). That is the quality flywheel: today's failure becomes tomorrow's regression test, for free, because the trace captured it.
""")

code(r'''
# The exhaust: where the trace goes and how a failure feeds the flywheel.
last = spans[-1]
print(f"  [{last['plane']:<13}] {last['hop']}  ({last['chapters']})")
print(f"                  {last['detail']}")

# Roll the trace up by plane so the shape of the system is obvious at a glance.
print("\nshare of latency by plane:")
planes = ("model", "orchestration", "data", "infrastructure")
for plane in planes:
    ms = sum(s["ms"] for s in spans if s["plane"] == plane)
    share = ms / tot_ms if tot_ms else 0
    bar = "#" * round(share * 30)
    print(f"  {plane:<15} {ms:>6.1f} ms  {share:>5.0%}  {bar}")
''')

# 11. Pitfall -----------------------------------------------------------------
md(r"""
## ⚠️ Pitfall: mistaking "the model" for "the system"

Count the hops in the trace that are **not** the model: intake, queue, worker pickup, retrieval, the MCP approval gate, the gateway, the SSE stream, the trace export. Of eleven spans, only a couple are model calls. They dominate *latency and cost* (look at the per-plane roll-up) — but almost everything that determines whether the answer is **correct, safe, and observable** lives in the other three planes (Chapter 3's lesson, restated at the capstone).

So when this system returns a wrong answer, the instinct to "swap in a bigger model" is usually wrong. The bug is far more often a **data**-plane miss (`rag.retrieve` pulled the wrong feedback), an **orchestration** error (the approval was mis-scoped, or the loop never terminated), or an **infrastructure** failure (the gateway breaker was open and a stub came back). **Locate the plane first.** A bigger model just makes a wrong answer more fluent.
""")

# 12. Senior lens -------------------------------------------------------------
md(r"""
## 🎯 Senior lens

The payoff of Chapter 3's four planes is visible right here: a good early mental model means that three hundred pages later, the map *still matches the territory*. You did not have to learn a new architecture for the capstone — you furnished the same four planes, one chapter at a time, and the trace you just read is the same trace you could have drawn after Chapter 3, only fuller.

That is the senior move: invest in the load-bearing abstraction early, so every later decision has a place to hang. When a new engineer joins this system, you do not hand them the 200-file tree — you hand them this one trace and the layer map, and they can locate *anything* (a bug, a cost spike, a new feature) in both the book and the directory within minutes. The architecture teaches itself because the frame never moved.
""")

# 13. Recap -------------------------------------------------------------------
md(r"""
## Recap

- The whole capstone is legible as **one request through four planes** — model, orchestration, data, infrastructure (§44.1).
- The §44.1 **layer → directory → chapter map** lets you locate any concern in both the book and the `capstone/` tree.
- **Thin intake** makes no model call (0 tokens), so the API tier stays available while the worker does the expensive work behind a queue (Ch 42).
- **Irreversible actions are approval-gated** (the MCP `create_ticket` call), every step is **checkpointed**, and every model call routes **through the gateway** (Ch 14, 20, 39).
- The trace feeds the **flywheel**: today's wrong retrieval becomes tomorrow's eval case (Ch 22–23). Most hops are **not** the model — locate the plane before reaching for a bigger one.
""")

# 14. Exercises ---------------------------------------------------------------
md(r"""
## Exercises

Each exercise *changes* the trace and asks you to predict the result before running.

1. **Add the second approval.** Suppose the request also *emails* the three issue owners. Add a span for an `mcp.tool.send_email` call. Predict: should it be approval-gated? Add it after `create_ticket`, label its plane, and justify the gate (or its absence).
2. **Move the bottleneck.** Cache the `agent.summarize` result for repeated feedback shapes (an infrastructure hop). Predict what happens to total latency, total cost, and the per-plane roll-up — then edit the loaded `spans` and re-run `print_trace`.
3. **Find the layer.** Pick three chapters you have not opened in a while (say Ch 30, Ch 39, Ch 41). For each, name the **layer**, the **plane**, and the `capstone/` **directory** from the map — without scrolling up. Then check.
4. **Break a hop.** Set `gateway.route`'s detail to "breaker OPEN — provider down, served fallback model." Trace what the user sees and which later spans change. Which plane absorbed the failure?
""")

code("# Exercise scratch space — your code here.\n")
code("# Exercise scratch space — your code here.\n")

# 15. Optional live path ------------------------------------------------------
md(r"""
## ⚠️ (Opt-in) Drive the real capstone with `MOCK=0`

Everything above ran on a canned trace. To watch a **real** request flow through the live system, you would harden the loop into the actual `capstone/`:

```bash
# From the repo root — costs real tokens; needs a key in .env.
export COMPANION_MOCK=0
cd capstone && docker compose up --build      # brings up app, workers, pg, redis, web
# then re-run this notebook: load_trace() attaches to the live tracer (Ch 23)
```

This is **opt-in** and flagged because it spends real money and stands up real services. The tour does not need it — the canned trace teaches the same map. Reach for `MOCK=0` only when you want to **diff your own running system against this known-good trace**.
""")

# 16. Next --------------------------------------------------------------------
md(r"""
## Next

- **Next notebook:** [`44-02-production-readiness-pass.ipynb`](44-02-production-readiness-pass.ipynb) — now that you can narrate the system, *harden* it and run the §44.5 master checklist against it.
- **The capstone itself:** read [`../../../capstone/README.md`](../../../capstone/README.md) (the Appendix C mapping) with this trace open, and diff your own assembly against the matching [`../../../capstone/checkpoints/`](../../../capstone/checkpoints/) — *build yours first, then compare.*
- **Blueprints assembled here:** the [`agent-loop/`](../../../blueprints/agent-loop/), [`rag-pipeline/`](../../../blueprints/rag-pipeline/), [`multi-agent-supervisor/`](../../../blueprints/multi-agent-supervisor/), [`eval-harness/`](../../../blueprints/eval-harness/), and [`observability-stack/`](../../../blueprints/observability-stack/) blueprints all show up together inside this one running system.
- **Book:** keep §44.1 (the layer table and AWS diagram) within reach — this notebook is its runnable companion.
""")

# Assemble & write ------------------------------------------------------------
nb = {
    "cells": cells,
    "metadata": {
        "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
        "language_info": {"name": "python"},
    },
    "nbformat": 4,
    "nbformat_minor": 5,
}

out = "44-01-capstone-tour-one-request.ipynb"
with open(out, "w", encoding="utf-8") as f:
    json.dump(nb, f, indent=1, ensure_ascii=False)
    f.write("\n")
print(f"wrote {out} with {len(cells)} cells")
