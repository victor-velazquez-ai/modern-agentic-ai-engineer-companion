# Ch 09 — Inference, Sampling & Control

> Companion plan · Part III · book file `chapters/09-inference-sampling-control.typ`
> Status: 📋 planned (Phase 1)

## Role in the companion
Chapter 8 ended at the model emitting a probability distribution; this chapter is the engineering
that happens *after* — picking a token, making it (un)repeatable, streaming it, and paying for it.
These are **concept-labs**: the reader reshapes a distribution by hand and watches temperature and
top-p change the draw, sees why temperature-0 isn't truly deterministic, and clocks TTFT vs decode
rate. This is where "the levers you actually hold at inference time" stop being words and become
sliders the reader has moved.

## Planned notebooks

### 09-01 · `09-01-decoding-knobs-live.ipynb` — Temperature, top-p, top-k, penalties
- **Type:** concept-lab
- **Maps to:** book §9.1 (decoding: temperature, top-p, top-k, penalties)
- **Objective:** reshape a probability distribution with each knob and predict its effect on output
  variety vs consistency — without confusing either with truth.
- **Prereqs:** Ch 8 (next-token prediction); `learn/part-03-llm-substrate/08-*`.
- **Cell arc:**
  - 🧠 mental model: decoding = *reshape the distribution, then roll a die*; temperature reshapes,
    top-p/top-k truncate the tail. No knob adds capability that isn't already in the distribution.
  - Start fully offline: a hand-made next-token distribution (" Paris" 92%, " the" 3%, …); apply
    a temperature scale to the logits and re-softmax; plot before/after.
  - Implement nucleus (top-p) and top-k truncation on that distribution; show what gets cut.
  - 🔮 *predict* whether sampling at temp 0 vs 1.0 changes a *wrong* fact — then show it only
    changes consistency, not correctness (hallucination lives in the distribution).
  - Optional live cell (`MOCK=0`): same prompt at temp 0.0 / 0.7 / 1.0, eyeball variety.
  - 🎯 senior lens: agent/tool/JSON calls want *low* temperature (variety is a liability); raise it
    only for explicitly creative steps. Sampling params are part of the prompt's contract (Ch 10).
  - ⚠️ pitfall: tuning temperature *and* top-p aggressively at once; or treating a temp-0 setting as
    a truth guarantee.
- **Datasets/fixtures:** an in-notebook toy distribution; no external data.
- **APIs & cost:** offline by default (all reshaping is local NumPy); `MOCK=0` adds a few short live
  generations to compare variety (≈ a few cheap calls).
- **You'll be able to:** set sampling parameters deliberately per call type and justify why.

### 09-02 · `09-02-determinism-seeds-and-replay.ipynb` — Determinism, seeds, reproducibility
- **Type:** concept-lab
- **Maps to:** book §9.4 (determinism, seeds, reproducibility), §9.3 (log-probs & confidence,
  lightly)
- **Objective:** treat determinism as an engineering property you *build* (pin, design-for, log,
  test statistically), not a parameter you set.
- **Prereqs:** 09-01.
- **Cell arc:**
  - 🧠 mental model: even at temp 0, GPU float non-associativity + server-side batching can flip a
    borderline token, and one flip changes everything after it; `seed` is best-effort.
  - Offline demo of the *shape* of the problem: sum the same floats in two orders and show the
    result differ at the last bits → "one flipped token cascades."
  - The four disciplines, made concrete: **pin** dated snapshots (not `latest`); **design for**
    nondeterminism (validate + retry); **log to replay** (model, prompt, params, seed, response);
    **test statistically** (assert properties across N runs, not string equality).
  - 🔮 *predict* whether a `seed` makes two live calls byte-identical — then (mock or live) see "
    usually, not guaranteed."
  - Build a tiny "replay log" record dict and a property-style check ("valid JSON across 20 mock
    runs") to model the statistical-test habit.
  - 🎯 senior lens: logprobs (where available) let you gate/escalate low-confidence answers and feed
    calibration analysis (Ch 22) — act on uncertainty instead of being blind to it.
  - ⚠️ pitfall: a suite that asserts exact transcripts — green for weeks, then red after a provider
    update, or flaky from batching; teams then pin to recordings and stop testing the real model.
- **Datasets/fixtures:** none (synthetic float demo + canned multi-run mock responses).
- **APIs & cost:** offline/mock by default; `MOCK=0` optionally issues a couple of seeded calls to
  observe best-effort behavior (≈ 2 short calls).
- **You'll be able to:** design an LLM system that's reproducible *enough* and testable despite
  nondeterminism.

### 09-03 · `09-03-streaming-and-latency-anatomy.ipynb` — Streaming, TTFT vs decode, token economics
- **Type:** concept-lab
- **Maps to:** book §9.5 (streaming & token economics), §9.6 (latency anatomy: TTFT & tokens/sec),
  §9.2 (reasoning budget, lightly)
- **Objective:** decompose one call into TTFT (queue + prefill) and decode (tokens/sec), and turn
  that into the levers that cut real vs perceived latency and cost.
- **Prereqs:** 09-01; 08-01 (token counting).
- **Cell arc:**
  - 🧠 mental model: a call has two phases — prefill (parallel, scales with *input*) sets TTFT;
    decode is sequential (≈ constant per token), so total ≈ TTFT + output_len / decode_rate.
  - Consume a streamed response with the Anthropic `messages.stream(...)` shape (mock yields timed
    deltas); print tokens as they "arrive" and read `usage` at the end.
  - 🔮 *predict* whether streaming reduces *total* latency or only *perceived* latency — then show
    same total time, radically better experience.
  - A tiny latency model: vary input size and output length, compute TTFT and total from a mock
    decode rate, and rank the levers (fewer input tokens → cache prefix → fewer output tokens →
    faster tier → stream → parallelize).
  - Token economics: output tokens cost several × input; set `max_tokens` per call type (a
    classifier needs 10, not 4096); the growing transcript is the silent input multiplier in loops.
  - 🎯 senior lens: in an agent, the dominant term is the *number of sequential calls* (eight
    round-trips = eight TTFTs + eight decodes); combine/parallelize/route/cache — profile the
    critical path first (Ch 23). The reasoning *thinking budget* (§9.2) is the biggest per-step
    cost/latency lever — spend it only on genuinely hard steps.
  - ⚠️ pitfall: streaming *unvalidated* structured output into something that executes/renders
    (Ch 41); buffer until JSON parses or use partial-JSON helpers.
- **Datasets/fixtures:** none (mock streaming generator + a synthetic latency table).
- **APIs & cost:** mockable — `MOCK=1` simulates the SSE delta stream offline and deterministically;
  `MOCK=0` streams from a real model (≈ one short streamed call).
- **You'll be able to:** read a latency budget, choose the right lever, and stream safely.

## Feeds (cross-pillar)
- **Blueprint(s):** — (concept). Sampling/streaming/usage habits here are realized in
  [`blueprints/llm-gateway/`](../../../blueprints/llm-gateway/) (built from Ch 11), which owns
  streaming, retries, and usage logging.
- **Template(s):** —
- **Capstone:** no code yet. Sets the defaults the capstone `llm/` client encodes — low temperature
  for agent/extraction calls, pinned snapshots, streamed endpoints (Ch 38), per-call usage logging.

## Dependencies
- Ch 8 (`learn/part-03-llm-substrate/08-*`) for tokens and the distribution. Async fan-out
  (`asyncio.gather`) referenced here is built in Ch 4; the prompt-as-contract idea continues in
  Ch 10; cost primitives (caching, batching) arrive in Ch 11.

## Phase-2 definition of done
- [ ] All three notebooks run top-to-bottom in `MOCK=1` fully offline (distribution math local;
      streaming + multi-run responses canned), deterministically where the math allows.
- [ ] Decoding-knob, determinism, TTFT/decode, and economics terminology matches the book's §9.
- [ ] Each notebook ends with recap + 2–3 exercises that *change* a knob and predict the result.
- [ ] Sampling code shapes (and the `messages.stream` usage) match the book and current SDK; secrets
      from env only; live token cost documented in the setup cell.
