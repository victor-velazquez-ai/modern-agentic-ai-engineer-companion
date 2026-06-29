# Ch 46 — Voice & Realtime Agents

> Companion plan · Part XII · book file `chapters/46-voice-and-realtime-agents.typ`
> Status: 📋 planned (Phase 1)

## Role in the companion
Voice is "your ordinary agent loop wrapped in a realtime transport layer." A Jupyter kernel
can't carry a live phone call, so these notebooks teach the part that *is* runnable and
language-agnostic: the **session/turn-taking/latency** model. The reader drives a fully
**mocked realtime stream**, implements endpointing and barge-in against it, and instruments a
per-stage latency budget — learning *why most "model" failures in voice are actually
turn-taking and latency failures* without spending a cent or needing a microphone. Real audio
is offered as an explicitly optional ⚠️ path, not a requirement.

## Planned notebooks

### 46-01 · `46-01-cascaded-vs-speech-to-speech.ipynb` — Two architectures, one latency budget
- **Type:** concept-lab
- **Maps to:** §46.1 (cascaded pipeline vs native speech-to-speech; 🧠 *mentalmodel*: realtime
  transport around a transport-agnostic core), §46.2 (the per-stage latency budget table)
- **Objective:** reason about the cascaded↔native trade-off (control/observability vs
  latency/prosody) and compute where a 500–800 ms budget is spent.
- **Prereqs:** Ch 40 (latency) · Ch 12 (the agent core that both architectures wrap).
- **Cell arc:**
  - 🧠 the two architectures side by side: a text-transcript seam (cascaded) vs an opaque
    audio-to-audio core (native), and what each buys/costs.
  - Encode the chapter's latency table as data; sum a sampled budget per turn.
  - 🔮 *predict* which stage dominates, then add up endpointing + STT + LLM-TTFT + TTS and see.
  - Show streaming overlap: stages that *pipeline* vs stages that *queue* (perceived latency).
  - ⚠️ pitfall: mistaking "the model" for the system — most voice failures are turn-taking/latency.
  - 🎯 senior lens: evaluate at two layers — *conversation* (Part VI transcript evals) and
    *audio* (endpointing precision, barge-in time, per-stage latency percentiles).
- **Datasets/fixtures:** the latency table as a small in-notebook dict (no external data).
- **APIs & cost:** none — fully offline (arithmetic + a mocked stage timeline).
- **You'll be able to:** choose cascaded vs native for a given workload and name the budget each stage owns.

### 46-02 · `46-02-realtime-session-loop.ipynb` — 🔧 Turn-taking & barge-in on a mock realtime stream
- **Type:** walkthrough
- **Maps to:** §46.1 (the realtime-session structural sketch — events, `turn_detection`, tools),
  §46.2 (turn-taking: endpointing/VAD, barge-in = cut TTS *and* cancel in-flight generation;
  #tip: stream TTS early, fillers for tool gaps; #pitfall: demo Wi-Fi vs real noisy audio)
- **Objective:** build an async event loop over a *simulated* realtime session that detects
  end-of-turn, dispatches a tool mid-conversation, and handles barge-in (interruption).
- **Prereqs:** 46-01; Ch 4 (async / `asyncio`); Ch 12 (tool dispatch — *same* tool schemas);
  Ch 14 (context compaction for long sessions).
- **Cell arc:**
  - A `MockRealtimeSession` yielding events (audio frames, `speech_started`, `turn.done`,
    `function_call_arguments.done`) — the same event shape as the chapter's sketch.
  - The session loop: on `turn.done` call the agent core; on tool-call events `dispatch_tool`
    and send the result back (reusing Ch 12 tools unchanged).
  - Endpointing: a simple VAD-style "caller stopped" signal + a semantic-cue stub.
  - 🔧 barge-in: on `speech_started` mid-response, cancel the in-flight generation *and* stop
    the (mock) TTS playback — 🔮 *predict* what a naive loop that only stops playback does wrong.
  - Latency instrumentation: timestamp each stage and print a per-turn budget vs §46.2's targets.
  - ⚠️ pitfall: endpointing tuned on quiet audio cuts real callers off — inject simulated noise /
    delayed packets and watch interruption/talk-over rates move (not just word error rate).
  - 🎯 senior lens: treat the session as *state* — long calls need the Ch 14 compaction discipline.
  - **Optional ⚠️ live path:** a clearly-flagged, opt-in cell sketching a real
    STT→agent→TTS or native-realtime session (`MOCK=0`, real key + audio) — *not* run in CI.
- **Datasets/fixtures:** a small scripted event timeline + an optional tiny WAV in `data/`
  (only used on the opt-in live path; mock path needs no audio).
- **APIs & cost:** mockable by default (no audio, no key); the optional live path documents
  realtime-session cost and is dry by default.
- **You'll be able to:** implement endpointing + barge-in over a realtime event stream and read
  a per-stage latency budget — the skills that actually decide whether a voice agent feels alive.

## Feeds (cross-pillar)
- **Blueprint(s):** — (transport layer is provider-specific; the *core* it wraps is the
  existing [`blueprints/agent-loop/`](../../blueprints/agent-loop/), reused unchanged —
  the notebook's point is that voice is a wrapper, not a new brain).
- **Template(s):** —
- **Capstone:** — (no dedicated module; the notebook notes the realtime transport would sit in
  front of the existing `capstone-project/agents/` core, which is built transport-agnostic).

## Dependencies
- Ch 4 (async) · Ch 12 (tool dispatch / agent core) · Ch 14 (long-session compaction) ·
  Ch 40 (latency budgets) · Ch 41 (guardrails on the conversation layer).

## Phase-2 definition of done
- [ ] Both notebooks run top-to-bottom in `MOCK=1` with no audio device, no key, no network.
- [ ] The session loop implements endpointing + barge-in (cancel generation *and* playback) and
      reuses Ch 12 tool schemas, matching §46.1–46.2 terminology.
- [ ] Latency instrumentation prints a per-stage budget compared to the chapter's table.
- [ ] The live/real-audio path is opt-in, clearly ⚠️-flagged, and skipped in CI; secrets from env.
- [ ] Recap + 2–4 exercises (e.g., add a semantic endpointing cue; tune the barge-in threshold).
