"""Generator for 46-01-cascaded-vs-speech-to-speech.ipynb (concept-lab, offline)."""
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "46-01-cascaded-vs-speech-to-speech.ipynb")


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


def _lines(text):
    """Split into a list of '...\n'-terminated strings, like nbconvert does."""
    text = text.strip("\n")
    lines = text.split("\n")
    return [ln + "\n" for ln in lines[:-1]] + [lines[-1]]


cells = []

# 1 — Title + header + promise -------------------------------------------------
cells.append(md(
"""# Cascaded vs Speech-to-Speech: One Latency Budget

> 📓 *Companion to* **Modern Agentic AI Engineer** *· Ch 46 §46.1–46.2 · type: concept-lab*

**The promise:** by the end you can reason about the cascaded ↔ native speech-to-speech
trade-off (control & observability vs latency & prosody) and compute exactly *where* a
500–800 ms conversational budget is spent — which stage you must attack first, and which
stages you can hide behind streaming.

Runs **fully offline and free**: this is arithmetic over a small latency table plus a mocked
stage timeline. No API key, no audio, no network, nothing billed."""
))

# 2 — Why this matters ---------------------------------------------------------
cells.append(md(
"""## 🧠 Why this matters

A voice agent is your **ordinary agent loop wrapped in a realtime transport layer** (§46.1).
The brain — tools, memory, guardrails — is the same one you've built all book. What's new is
everything *around* it: sessions instead of requests, audio frames instead of strings, and a
**hard** latency budget instead of a soft one.

Two architectures wrap that core. The **cascaded pipeline** chains specialists —
streaming STT → your LLM agent → streaming TTS — and keeps a **text transcript at the center**,
so logging, evals, and guardrails all work unchanged and you can swap any stage. The **native
speech-to-speech** model consumes and emits audio directly over one realtime session: fewer
hops, better prosody, gracefuller interruptions — but you lose the clean text seam and steering
gets harder.

Human conversation tolerates roughly **500–800 ms** of silence before a reply feels laggy;
past a second, people talk over the agent. So the *whole game* is the latency budget — and the
senior insight (§46.2) is that **most failures blamed on "the model" in voice are actually
turn-taking and latency failures.** This notebook makes that budget concrete."""
))

# 3 — Objectives + prereqs -----------------------------------------------------
cells.append(md(
"""## Objectives & prereqs

**By the end you can:**
- Name what the cascaded text seam *buys* (control, observability, reuse) and what it *costs*
  (two extra model hops, flattened prosody).
- Encode the chapter's per-stage latency table as data and **sum a sampled budget per turn**.
- Predict which stage dominates, then see it.
- Distinguish stages that **pipeline** (overlap) from stages that **queue** — i.e. *perceived*
  vs *real* latency.
- Choose cascaded vs native for a given workload and name the budget each stage owns.

**Prereqs:** Ch 40 (latency budgets) and Ch 12 (the agent core both architectures wrap).
Standard library only. Read book §46.1–46.2 alongside this.

**Run first:** the Setup cell. Defaults to `MOCK=1` — here that means *fully offline*; there
is no live path in this notebook (it's pure arithmetic), but the switch is kept for a uniform
contract across every companion notebook."""
))

# 4 — Setup --------------------------------------------------------------------
cells.append(code(
"""# --- Setup -------------------------------------------------------------------
import os
import random

from dotenv import load_dotenv

load_dotenv()  # reads a local .env if present; never hardcode keys

# MOCK=1 (default): this notebook is pure local arithmetic + a mocked stage
# timeline, so it is fully offline, free, and deterministic. There is no live
# network path here -- the switch is kept for a uniform contract across notebooks.
MOCK = os.getenv("COMPANION_MOCK", "1") == "1"

random.seed(46)  # determinism for the sampled per-turn budget below

print(f"MOCK mode: {MOCK}  (offline -- no API key, no audio, no network needed)")"""
))

# 5 — The two architectures, side by side -------------------------------------
cells.append(md(
"""## 1 · The two architectures, side by side

Same brain, two wrappers. The difference is **where the seam is** — and a seam you can read
is a seam you can log, evaluate, and steer.

| | **Cascaded pipeline** | **Native speech-to-speech** |
|---|---|---|
| Shape | STT → LLM agent → TTS (3 components) | one realtime model, audio in/out |
| Center of the system | a **text transcript** | an **opaque audio-to-audio** core |
| Observability | high — read/inspect every stage | low — no clean text seam |
| Steerability & guardrails | reuse Part VI / Ch 41 unchanged | harder; must re-derive on audio |
| Swap a stage | yes, independently | no — it's one model |
| Latency | more hops to pay for | fewer hops; lower floor |
| Prosody / emotion | flattened by the transcript | preserved |
| Interruptions (barge-in) | you wire it (next notebook) | handled more gracefully |

As of early 2026 serious systems use **both**: a native model for the conversational front end,
with a cascaded escape hatch (or a parallel transcript stream) for tool calls, compliance
logging, and evaluation. You rarely pick one religiously — you pick where each seam lives."""
))

cells.append(code(
"""# Encode the trade-off as data so we can reason about it instead of hand-waving.
ARCHITECTURES = {
    "cascaded": {
        "seam": "text transcript at the center",
        "buys": ["observability", "reuse evals/guardrails", "swap any stage"],
        "costs": ["two extra model hops", "flattened prosody", "more places to fail"],
    },
    "native_s2s": {
        "seam": "opaque audio-to-audio core",
        "buys": ["lower latency floor", "preserved prosody", "graceful interruptions"],
        "costs": ["no text seam to log/steer", "harder to audit", "all-or-nothing stage swap"],
    },
}

for name, a in ARCHITECTURES.items():
    print(f"{name:>11}  seam: {a['seam']}")
    print(f"{'':>11}  buys : {', '.join(a['buys'])}")
    print(f"{'':>11}  costs: {', '.join(a['costs'])}\\n")"""
))

# 6 — The latency table as data -----------------------------------------------
cells.append(md(
"""## 2 · The latency budget as data

Here is the chapter's order-of-magnitude budget for the **cascaded** turn (§46.2). The figures
vary by provider and load — what doesn't vary is the discipline: *measure each stage, and
stream everything so stages overlap instead of queueing.* Each stage gets a `(low, high)` range
in milliseconds."""
))

cells.append(code(
"""# §46.2's per-stage budget for a cascaded turn, as (low_ms, high_ms).
LATENCY_BUDGET_MS = {
    "network_round_trip": (50, 100),    # transport, there and back
    "endpointing":        (200, 400),   # deciding the caller actually stopped
    "stt_finalize":       (100, 200),   # finalizing the transcript
    "llm_ttft":           (200, 500),   # LLM time-to-first-token
    "tts_first_audio":    (100, 250),   # TTS time-to-first-audio
}

# The conversational comfort window: past this, callers start talking over the agent.
COMFORT_LOW_MS, COMFORT_HIGH_MS = 500, 800

low_total = sum(lo for lo, _ in LATENCY_BUDGET_MS.values())
high_total = sum(hi for _, hi in LATENCY_BUDGET_MS.values())

print(f"{'stage':>20}  {'low':>5}  {'high':>5}")
for stage, (lo, hi) in LATENCY_BUDGET_MS.items():
    print(f"{stage:>20}  {lo:>5}  {hi:>5}")
print(f"{'TOTAL':>20}  {low_total:>5}  {high_total:>5}  ms")
print(f"\\ncomfort window: {COMFORT_LOW_MS}-{COMFORT_HIGH_MS} ms before a reply feels laggy")"""
))

# 7 — Predict which stage dominates -------------------------------------------
cells.append(md(
"""## 3 · 🔮 Predict: which stage dominates?

Before you run the next cell, **predict**: across these five cascaded stages, which **one**
owns the largest slice of a *typical* turn? Your instinct probably says "the LLM" — that's the
expensive part of a chat app.

Look again at the ranges above. Two non-model stages are quietly large. Decide which single
stage you'd attack first to claw back the most milliseconds, then run the cell."""
))

cells.append(code(
"""# Sample one realistic turn: draw each stage uniformly from its (low, high) range.
def sample_turn(budget):
    return {stage: random.randint(lo, hi) for stage, (lo, hi) in budget.items()}


turn = sample_turn(LATENCY_BUDGET_MS)
total = sum(turn.values())

worst_stage = max(turn, key=turn.get)
print(f"{'stage':>20}  {'ms':>5}  {'share':>6}")
for stage, ms in sorted(turn.items(), key=lambda kv: -kv[1]):
    bar = "#" * (ms // 15)
    print(f"{stage:>20}  {ms:>5}  {ms / total:>5.0%}  {bar}")
print(f"{'TURN TOTAL':>20}  {total:>5}  ms")
print(f"\\ndominant stage this turn: {worst_stage} ({turn[worst_stage]} ms)")
print("over comfort window?" , total > COMFORT_HIGH_MS)"""
))

cells.append(md(
"""**What you just saw.** With seed `46`, **endpointing** (deciding the caller actually stopped)
is the fattest single slice — bigger than the LLM's time-to-first-token. That's the chapter's
whole point in one bar chart: in voice, the *turn-taking* stages are first-class latency, not
plumbing. Shaving 150 ms off endpointing buys you more than swapping to a marginally faster LLM.
And the summed turn already crowds the 500–800 ms comfort window — before TTS has spoken a full
word."""
))

# 8 — Pipeline vs queue: perceived latency ------------------------------------
cells.append(md(
"""## 4 · Pipeline vs queue: real latency you can hide

That naive sum assumes every stage **queues** — each waits for the previous one to fully finish.
But the discipline from §46.2 is to **stream everything** so stages *pipeline* (overlap). The
classic example: TTS can start speaking the **first generated sentence** while the LLM is still
decoding the rest. The user hears audio at *TTS-start*, not at *LLM-done*.

So there are two numbers that matter, and they're different:
- **Real wall-clock** to a fully spoken reply (what your traces measure).
- **Perceived latency** = time until the caller hears the *first audio* (what decides "does it
  feel alive")."""
))

cells.append(code(
"""# Two stages pipeline: TTS starts after the LLM's FIRST token, not its last.
# Model the LLM as ttft + a decode tail; TTS overlaps the decode tail.
llm_ttft = turn["llm_ttft"]
llm_decode_tail = 600          # ms to finish generating the rest of the reply
tts_first_audio = turn["tts_first_audio"]

# Everything BEFORE the LLM still queues (you can't speak before you've understood).
pre_llm = turn["network_round_trip"] + turn["endpointing"] + turn["stt_finalize"]

# QUEUED model: wait for the whole LLM reply, THEN start TTS.
queued_to_first_audio = pre_llm + llm_ttft + llm_decode_tail + tts_first_audio

# PIPELINED model: TTS starts one sentence in -- right after ttft, overlapping decode.
pipelined_to_first_audio = pre_llm + llm_ttft + tts_first_audio

print(f"perceived latency (queued TTS)    : {queued_to_first_audio:>5} ms")
print(f"perceived latency (streamed TTS)  : {pipelined_to_first_audio:>5} ms")
print(f"hidden by streaming               : {queued_to_first_audio - pipelined_to_first_audio:>5} ms"
      f"  (the whole decode tail)")
print(f"\\nstreamed perceived latency in comfort window "
      f"({COMFORT_LOW_MS}-{COMFORT_HIGH_MS} ms)? "
      f"{pipelined_to_first_audio <= COMFORT_HIGH_MS}")"""
))

cells.append(md(
"""**What you just saw.** Streaming TTS from the first sentence hid the **entire LLM decode tail**
— hundreds of milliseconds the caller never waits through. This is why native speech-to-speech
feels snappy (it pipelines by construction) and why a *well-streamed* cascaded pipeline can feel
nearly as alive. The lesson generalizes: **perceived latency is a design surface, not just an
infra metric** (§46.2's tip — fast model for the turn, fillers like "let me pull that up" to
cover tool gaps, stream from the first token)."""
))

# 9 — Pitfall ------------------------------------------------------------------
cells.append(md(
"""## 5 · ⚠️ Pitfall: mistaking "the model" for the system

The seductive failure mode: a voice agent feels sluggish or rude (talks over people, leaves
dead air), so the team reaches for a *bigger, slower* model — or starts fine-tuning. But the
budget above shows the model is **one slice of five**, and the turn-taking slices (endpointing,
plus barge-in handling you'll build next) are where "feels laggy" and "talks over me" actually
live.

Watch a swap that *upgrades the model* but *ignores turn-taking*: the perceived experience can
get **worse**, because a stronger LLM that decodes a few tens of ms slower, with un-tuned
endpointing, still mis-detects end-of-turn."""
))

cells.append(code(
"""# A "smarter" model that's slightly slower to first token, with UNCHANGED endpointing.
faster_turn = dict(turn)
faster_turn["llm_ttft"] = turn["llm_ttft"] + 40   # bigger model: a touch more TTFT

before = sum(turn.values())
after = sum(faster_turn.values())

# But the user-felt problem ("talks over me") is endpointing, which we did NOT touch.
endpointing_share_before = turn["endpointing"] / before
endpointing_share_after = faster_turn["endpointing"] / after

print(f"total turn, before model swap : {before} ms")
print(f"total turn, after model swap  : {after} ms  (worse by {after - before} ms)")
print(f"endpointing still owns         : {endpointing_share_after:.0%} of the turn")
print("\\nWe 'upgraded the brain' and the turn got slower, while the real complaint")
print("(end-of-turn detection) was never addressed. Instrument BEFORE you fine-tune.")"""
))

# 10 — Senior lens -------------------------------------------------------------
cells.append(md(
"""## 🎯 Senior lens

Evaluate a voice agent at **two layers**, and don't let one masquerade as the other.

- The **conversation layer** reuses everything from Part VI: transcript evals for correctness,
  tool-call accuracy, guardrail adherence (Ch 41). If you kept the cascaded text seam, these
  run *unchanged* — that observability is a large part of what the seam buys you.
- The **audio layer** is new and is where voice agents actually live or die: **endpointing
  precision**, **barge-in response time**, and **per-stage latency percentiles** (p50 is a
  liar here — callers feel your p95). None of these show up in a transcript eval.

So the architecture choice is really an *evaluation* choice. Going native speech-to-speech for
the prosody is a fine call — as long as you've decided how you'll keep a parallel transcript for
the conversation-layer evals and compliance logging you just gave up. And when something feels
"off," the senior reflex is to **profile the pipeline first**: most "the model is bad" tickets
in voice resolve to a mis-tuned turn-taking stage or a p95 latency spike, not the LLM."""
))

# 11 — Recap -------------------------------------------------------------------
cells.append(md(
"""## Recap

- A voice agent is your **agent core wrapped in a realtime transport layer** — same brain,
  new sessions/audio/latency budget.
- **Cascaded** keeps a text seam (observability, reuse, swappable stages) at the cost of extra
  hops and flattened prosody; **native speech-to-speech** lowers the latency floor and preserves
  prosody but is opaque and hard to steer. Production often runs **both**.
- The comfort window is **~500–800 ms**; the **turn-taking** stages (endpointing) can dominate a
  cascaded turn — often more than the LLM's TTFT.
- **Streaming pipelines** stages (TTS from the first sentence), hiding the LLM decode tail — it
  cuts *perceived*, not *real*, latency, and that's usually the real complaint.
- **Most "model" failures in voice are turn-taking/latency failures** — instrument the two
  layers (conversation + audio) before you fine-tune anything."""
))

# 12 — Exercises ---------------------------------------------------------------
cells.append(md(
"""## Exercises

Each one *changes a number* and asks you to predict first. (Solutions land in `solutions/` in
Phase 2.)

1. **Find the real bottleneck.** Run `sample_turn` over 1,000 seeds and count how often each
   stage is the dominant one. Predict whether `endpointing` or `llm_ttft` wins more often, then
   tally it. Which stage should own your *first* optimization sprint?
2. **Budget a native turn.** Native speech-to-speech collapses STT+LLM+TTS into one hop. Build a
   `NATIVE_BUDGET_MS` with `network_round_trip`, `endpointing`, and a single `s2s_first_audio`
   stage (say 250–450 ms). Predict the total vs the cascaded total, then compute it — where did
   the savings come from?
3. **Spend the streaming win.** In §4, raise `llm_decode_tail` to 1500 ms (a long, reasoned
   answer). Predict the gap between queued and streamed perceived latency, then show it. Why does
   a longer reply make streaming *more* valuable, not less?
4. **Percentiles, not means.** Sample 500 turns and print p50, p95, and p99 of the total. Predict
   how far p95 sits above p50, then compute it — and argue why you'd staff the budget to p95."""
))

cells.append(code("# Exercise 1 -- your code here"))
cells.append(code("# Exercise 2 -- your code here"))
cells.append(code("# Exercise 3 -- your code here"))
cells.append(code("# Exercise 4 -- your code here"))

# 13 — Next --------------------------------------------------------------------
cells.append(md(
"""## Next

- ▶️ **Next notebook:** [`46-02-realtime-session-loop.ipynb`](46-02-realtime-session-loop.ipynb)
  — 🔧 build an async session loop over a *mocked* realtime stream that does endpointing and
  barge-in, and instrument this exact per-stage budget per turn.
- 📖 **Book:** §46.1 (cascaded vs native; the realtime-session sketch), §46.2 (telephony,
  turn-taking, and the latency budget table). Revisit Ch 40 for latency budgets and Ch 12 for
  the agent core both architectures wrap.
- 🧠 **Blueprint this leans on:** [`blueprints/agent-loop/`](../../blueprints/agent-loop/) —
  the transport-agnostic core. Voice is a *wrapper* around it, not a new brain; the realtime
  transport sits in front of the same `capstone-project/agents/` core."""
))

nb = {
    "cells": cells,
    "metadata": {
        "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
        "language_info": {"name": "python"},
    },
    "nbformat": 4,
    "nbformat_minor": 5,
}

with open(OUT, "w", encoding="utf-8") as f:
    json.dump(nb, f, indent=1, ensure_ascii=False)
    f.write("\n")

print("wrote", OUT, "with", len(cells), "cells")
