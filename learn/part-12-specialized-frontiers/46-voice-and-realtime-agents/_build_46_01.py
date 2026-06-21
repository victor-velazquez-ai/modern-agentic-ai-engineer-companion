"""Builder for 46-01-cascaded-vs-speech-to-speech.ipynb (concept-lab, fully offline).

Run: python _build_46_01.py  ->  writes the .ipynb next to this file.
Every code cell is offline + deterministic; MOCK defaults to 1; outputs are empty.
"""
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "46-01-cascaded-vs-speech-to-speech.ipynb")


def _lines(text):
    text = text.strip("\n")
    parts = text.split("\n")
    return [ln + "\n" for ln in parts[:-1]] + [parts[-1]]


def md(text):
    return {"cell_type": "markdown", "metadata": {}, "source": _lines(text)}


def code(text):
    return {
        "cell_type": "code",
        "execution_count": None,
        "metadata": {},
        "outputs": [],
        "source": _lines(text),
    }


cells = []

# 1 — Title + header + promise -------------------------------------------------
cells.append(md(
"""# Cascaded vs speech-to-speech: one latency budget

> 📓 *Companion to* **Modern Agentic AI Engineer** *· Ch 46 §46.1–46.2 · type: concept-lab*

**The promise:** by the end you can reason about the cascaded ↔ native speech-to-speech trade-off (control & observability vs latency & prosody) and compute *where* a 500–800 ms conversational budget is actually spent — which stages overlap, which queue, and which one to attack first.

Runs fully **offline and free**: this notebook is arithmetic over the chapter's latency table plus a mocked stage timeline. No API key, no audio device, nothing billed."""
))

# 2 — Why this matters ---------------------------------------------------------
cells.append(md(
"""## 🧠 Why this matters

A voice agent is your ordinary agent loop wrapped in a **realtime transport layer**. The brain — tools, memory, guardrails — is the same one you've built all book. What's new is everything *around* it: sessions instead of requests, audio frames instead of strings, and a **hard** latency budget instead of a soft one.

Two architectures wrap that core differently:

- **Cascaded pipeline** — streaming STT → your LLM agent → streaming TTS. There's a **text transcript at the center**, so logging, evals (Part VI), guardrails (Ch 41), and your existing agent logic all work unchanged, and you can swap any stage independently.
- **Native speech-to-speech** — one realtime model consumes and emits audio directly over a persistent WebSocket/WebRTC session. It eliminates two model hops and preserves tone the transcript would flatten — but you give up the clean text seam, and steering/auditing gets harder.

Human conversation tolerates roughly **500–800 ms** of silence before a reply feels laggy; past a second, people talk over the agent. So the whole game is a **latency budget**, and the only way to win it is to know which stage owns which milliseconds. See §46.1–46.2."""
))

# 3 — Objectives + prereqs -----------------------------------------------------
cells.append(md(
"""## Objectives & prereqs

**By the end you can:**
- Name what the cascaded text seam buys (control, observability, independent swaps) and what native speech-to-speech buys (fewer hops, prosody, graceful interruption).
- Encode the chapter's per-stage latency table as data and **sum a sampled per-turn budget**.
- Predict which stage dominates, and separate stages that *pipeline* (overlap) from stages that *queue* — i.e. real vs perceived latency.

**Prereqs:** Ch 40 (latency budgets) · Ch 12 (the agent core both architectures wrap). Standard library only (`random`, `statistics`).

**Run first:** the Setup cell. Defaults to `MOCK=1` — and here there is *no* live path at all; it's pure local computation."""
))

# 4 — Setup --------------------------------------------------------------------
cells.append(code(
'''# --- Setup -------------------------------------------------------------------
import os
import random
import statistics

from dotenv import load_dotenv

load_dotenv()  # reads a local .env if present; we never hardcode keys

# MOCK=1 (default): this notebook is fully offline and deterministic. There is no
# live network path here at all -- the switch is kept only so every companion
# notebook shares one contract. No API key is ever read or needed.
MOCK = os.getenv("COMPANION_MOCK", "1") == "1"

random.seed(46)  # determinism for the sampled per-stage timings below

print(f"MOCK mode: {MOCK}  (fully offline -- arithmetic + a mocked stage timeline)")'''
))

# 5 — Two architectures side by side -------------------------------------------
cells.append(md(
"""## 1 · The two architectures, side by side

The trade-off is the classic one between **composability** and **integration**.

| | Cascaded pipeline | Native speech-to-speech |
|---|---|---|
| **Shape** | STT → LLM agent → TTS | one audio-in / audio-out realtime model |
| **Center of the system** | a **text transcript** (a clean seam) | an **opaque audio core** (no text seam) |
| **Buys you** | control, observability, per-stage swaps, reuse of all your text tooling | fewer model hops, preserved prosody/tone, smoother interruption |
| **Costs you** | extra latency from two model hops; transcription flattens tone | hard to log/steer/audit; evals must work on audio, not text |
| **Where it shines** | tool-heavy, compliance-heavy, must-audit flows | the conversational front end; natural, low-latency chat |

As of early 2026, serious systems use **both**: a native model for the conversational front end, with a cascaded escape hatch (or a parallel transcript stream) for tool calls, compliance logging, and evaluation. Below we make the *latency* half of this trade-off concrete."""
))

# 6 — Encode the latency table -------------------------------------------------
cells.append(md(
"""## 2 · Encode the chapter's latency table as data

§46.2 gives an order-of-magnitude budget for the **cascaded** path. We encode each stage as a `(low_ms, high_ms)` range so we can both sum it and sample it. The discipline the chapter insists on: *measure each stage, then stream everything so stages overlap instead of queue.*"""
))

cells.append(code(
'''# The cascaded latency budget from book Table (§46.2), as (low_ms, high_ms) ranges.
# "pipelines" marks a stage that can OVERLAP the next one once streaming is on.
STAGES = [
    # name                                  low   high  pipelines?
    ("Network transport (round trip)",        50,  100, False),
    ("Endpointing (decide caller stopped)",  200,  400, False),
    ("STT finalize transcript",              100,  200, True),   # streams partials
    ("LLM time-to-first-token",              200,  500, True),   # stream tokens out
    ("TTS time-to-first-audio",              100,  250, True),   # stream audio early
]

TARGET_LOW, TARGET_HIGH = 500, 800  # the human-conversation comfort band (ms)

print(f"{'stage':40} {'low':>5} {'high':>5}  pipelines")
for name, lo, hi, pipe in STAGES:
    print(f"{name:40} {lo:>5} {hi:>5}  {'yes' if pipe else 'no'}")
print(f"\\nComfort band: {TARGET_LOW}-{TARGET_HIGH} ms before a reply feels laggy.")'''
))

# 7 — Sum naive (serial) budget ------------------------------------------------
cells.append(md(
"""## 3 · The naive sum: every stage in series

First, the pessimistic view — each stage runs to completion before the next begins (no streaming). Add the high end of every range: that's the budget a *queueing* pipeline spends."""
))

cells.append(code(
'''serial_low = sum(lo for _, lo, _, _ in STAGES)
serial_high = sum(hi for _, _, hi, _ in STAGES)

print(f"serial (queueing) budget : {serial_low}-{serial_high} ms")
print(f"comfort band             : {TARGET_LOW}-{TARGET_HIGH} ms")
over = serial_high - TARGET_HIGH
print(f"\\nAt the high end the serial pipeline is {over} ms OVER the comfort band"
      f" ({serial_high} vs {TARGET_HIGH}).")
print("Run everything in series and you blow the budget. Streaming is not optional.")'''
))

# 8 — Predict ------------------------------------------------------------------
cells.append(md(
"""## 4 · 🔮 Predict: which single stage dominates?

Before you compute anything: of the five stages, **which one owns the largest slice of the budget at its high end** — network, endpointing, STT, LLM time-to-first-token, or TTS?

Write down your guess. People almost always say "the LLM." Then run the next cell."""
))

cells.append(code(
'''ranked = sorted(STAGES, key=lambda s: s[2], reverse=True)  # by high_ms
print("stages ranked by worst-case (high_ms) contribution:\\n")
for name, lo, hi, pipe in ranked:
    bar = "#" * (hi // 25)
    print(f"{hi:>4} ms  {bar:18} {name}")

top = ranked[0]
print(f"\\nThe biggest single slice is *{top[0]}* at {top[2]} ms.")
print("Endpointing ties the LLM at the high end -- the 'decide the caller stopped'")
print("delay is a turn-taking cost, not a model cost. That is the chapter's whole point.")'''
))

cells.append(md(
"""**What you just saw.** Endpointing (200–400 ms) is as large as LLM time-to-first-token, and it isn't "the model" at all — it's the cost of *deciding the human finished talking*. Most latency people blame on the LLM in voice systems is really turn-taking. Tune endpointing too eager and you cut callers off; too patient and the agent feels slow. We attack this directly in **46-02**."""
))

# 9 — Streaming overlap: pipelines vs queues -----------------------------------
cells.append(md(
"""## 5 · Streaming overlap: what *pipelines* vs what *queues*

Streaming doesn't make any single stage faster — it changes *when the next stage can start*. Three of our stages can **pipeline**: STT emits partial transcripts, the LLM streams tokens, and TTS can start speaking from the first generated sentence. They overlap instead of queue.

A crude but honest model of perceived latency = **time until the user hears the first audio**:
- the non-pipelined prefix (network + endpointing) must finish first, then
- the pipelined stages overlap, so the *first audio* lands roughly after the **largest** of them, not their sum."""
))

cells.append(code(
'''def perceived_first_audio_ms(stages, use_high=True):
    """Crude perceived-latency model: serial prefix + max() of overlapping stages."""
    idx = 2 if use_high else 1  # pick high_ms or low_ms from each tuple
    serial_prefix = sum(s[idx] for s in stages if not s[3])     # must complete in order
    pipelined = [s[idx] for s in stages if s[3]]                # overlap once streaming
    overlapped = max(pipelined) if pipelined else 0
    return serial_prefix + overlapped


queueing_high = sum(s[2] for s in STAGES)              # everything in series
streaming_high = perceived_first_audio_ms(STAGES, use_high=True)

print(f"time-to-first-audio, QUEUEING  (no streaming): {queueing_high} ms")
print(f"time-to-first-audio, STREAMING (overlapped)  : {streaming_high} ms")
print(f"perceived saving from streaming               : {queueing_high - streaming_high} ms")
print(f"\\nStreaming pulls perceived latency from {queueing_high} ms back toward the")
print(f"{TARGET_LOW}-{TARGET_HIGH} ms comfort band -- without making any stage faster.")'''
))

cells.append(md(
"""**What you just saw.** The pipelined stages (STT, LLM, TTS) overlap, so the user hears the first audio after the *largest* of them plus the unavoidable network+endpointing prefix — not after their sum. This is the same lesson as text streaming (§9.6): streaming transforms **perceived** latency. The non-overlapping prefix — network and especially **endpointing** — is the part you can't stream away, which is why it deserves the most engineering."""
))

# 10 — Sampled per-turn budget -------------------------------------------------
cells.append(md(
"""## 6 · A sampled per-turn budget

Real turns don't sit at the high end every time. Sample each stage uniformly within its range, simulate a handful of turns, and look at the **distribution** — because what bites a caller is the p95 turn, not the average one."""
))

cells.append(code(
'''def sample_turn_ms(stages):
    """One turn: sample each stage in its range; return (queueing_ms, streaming_ms)."""
    sampled = [(name, random.randint(lo, hi), lo, pipe) for name, lo, hi, pipe in stages]
    queueing = sum(ms for _, ms, _, _ in sampled)
    serial_prefix = sum(ms for _, ms, _, pipe in sampled if not pipe)
    pipelined = [ms for _, ms, _, pipe in sampled if pipe]
    streaming = serial_prefix + (max(pipelined) if pipelined else 0)
    return queueing, streaming


N = 200
queue_samples, stream_samples = [], []
for _ in range(N):
    q, s = sample_turn_ms(STAGES)
    queue_samples.append(q)
    stream_samples.append(s)


def pctile(xs, p):
    xs = sorted(xs)
    return xs[min(len(xs) - 1, int(p / 100 * len(xs)))]


for label, data in [("queueing", queue_samples), ("streaming", stream_samples)]:
    print(f"{label:9}  mean={statistics.mean(data):6.1f} ms   "
          f"p50={pctile(data,50):4d}   p95={pctile(data,95):4d}   max={max(data):4d}")

print(f"\\nComfort band {TARGET_LOW}-{TARGET_HIGH} ms. With streaming the p95 turn stays")
print("far closer to 'feels alive'; the queueing p95 is the one that makes callers talk over the agent.")'''
))

cells.append(md(
"""**What you just saw.** Averages hide the problem. The *streaming* p95 stays near the comfort band; the *queueing* p95 is what produces talk-over. When you instrument a real voice agent you track **per-stage latency percentiles**, not a single mean — exactly the audio-layer metric the senior lens below calls for."""
))

# 11 — Pitfall -----------------------------------------------------------------
cells.append(md(
"""## ⚠️ Pitfall: mistaking "the model" for the system

The reflex when a voice agent feels bad is to swap the LLM or fine-tune it. But you just saw that **endpointing alone rivals the entire LLM TTFT**, and that streaming (a transport decision, not a model decision) can halve perceived latency. Most failures blamed on "the model" in voice are **turn-taking and latency failures**.

Two corollaries you'll feel in 46-02:
- Endpointing tuned on quiet audio cuts real callers off — and that shows up as *interruption / talk-over rate*, not word-error rate.
- A faster model can't rescue a pipeline that queues instead of streams.

Instrument the pipeline (per-stage percentiles) **before** you touch the model."""
))

# 12 — Senior lens -------------------------------------------------------------
cells.append(md(
"""## 🎯 Senior lens

Evaluate voice agents at **two layers**, and don't conflate them:

- **Conversation layer** — reuse Part VI wholesale: transcript evals for correctness, tool-call accuracy, guardrail adherence. The cascaded path hands you this transcript for free; on a native path you run a *parallel transcript stream* so you don't lose it.
- **Audio layer** — this is the new surface: **endpointing precision, barge-in response time, per-stage latency percentiles.** None of it shows up in a text eval.

So the architecture choice isn't "cascaded vs native" as a religion — it's *where you put the text seam*. Pick native for the conversational front end where prosody and low latency win, and keep a cascaded escape hatch (or parallel transcript) wherever you must log, evaluate, or run tools. And treat the realtime session as **state to manage**: long calls need the same context-compaction discipline as long agent runs (Ch 14)."""
))

# 13 — Recap -------------------------------------------------------------------
cells.append(md(
"""## Recap

- A voice agent = a transport-agnostic agent **core** wrapped in a **realtime transport layer**; cascaded vs native is a choice about *where the text seam lives*.
- **Cascaded** buys control, observability, and reuse of your text tooling; **native** buys fewer hops, prosody, and smoother interruption — most production systems use both.
- The comfort band is **500–800 ms**; run the cascaded stages in series and you blow it.
- **Endpointing rivals the LLM** as the biggest single stage — a *turn-taking* cost, not a model cost.
- **Streaming** overlaps STT/LLM/TTS, cutting *perceived* latency without speeding any stage; the network+endpointing prefix is what you can't stream away.
- Track **per-stage percentiles** (p95, not mean) and evaluate at two layers: conversation (transcript) and audio (endpointing, barge-in, latency)."""
))

# 14 — Exercises ---------------------------------------------------------------
cells.append(md(
"""## Exercises

Each one *changes a number* and asks you to predict first. (Solutions land in `solutions/` in Phase 2.)

1. **Cache the system prefix.** Prompt caching (Ch 11) can slash LLM TTFT for an unchanged system+tools prefix. Cut the LLM stage range to `(80, 160)` and re-run the sampled budget. Predict the p95 streaming improvement *before* you compute it.
2. **A noisier endpointer.** Widen endpointing to `(200, 700)` (real, noisy audio). Predict what happens to the queueing **and** streaming p95 — and which one moves more — then check. Why does endpointing hurt streaming so much?
3. **Add a tool gap.** Insert a sixth stage `("Tool call round-trip", 300, 900, False)` that fires on tool turns only. Predict whether a "let me pull that up" filler (§46.2 tip) changes the *measured* latency or only the *perceived* one, then argue it in a markdown cell."""
))

cells.append(code("# Exercise 1 -- your code here\n"))
cells.append(code("# Exercise 2 -- your code here\n"))
cells.append(code("# Exercise 3 -- your code here\n"))

# 15 — Next --------------------------------------------------------------------
cells.append(md(
"""## Next

- ▶️ **Next notebook:** [`46-02-realtime-session-loop.ipynb`](46-02-realtime-session-loop.ipynb) — build the async session loop over a *mocked* realtime stream: endpointing, mid-conversation tool dispatch, and **barge-in** (cancel generation *and* stop playback), with the latency instrumentation you just modeled.
- 📖 **Book:** §46.1 (cascaded vs native), §46.2 (the latency budget table); revisit Ch 40 (latency) and §9.6 (streaming changes perceived latency).
- 🧩 **Blueprint this feeds:** the transport layer is provider-specific, but the *core* both architectures wrap is the existing [`blueprints/agent-loop/`](../../../blueprints/agent-loop/), reused unchanged — the whole point is that voice is a wrapper, not a new brain.
- 🎓 **Capstone:** no dedicated module; a realtime transport would sit in front of the existing transport-agnostic `capstone/agents/` core."""
))

notebook = {
    "cells": cells,
    "metadata": {
        "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
        "language_info": {"name": "python"},
    },
    "nbformat": 4,
    "nbformat_minor": 5,
}

with open(OUT, "w", encoding="utf-8") as f:
    json.dump(notebook, f, indent=1, ensure_ascii=False)
    f.write("\n")

print("wrote", OUT, "with", len(cells), "cells")
