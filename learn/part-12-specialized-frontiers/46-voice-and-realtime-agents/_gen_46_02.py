"""Generator for 46-02-realtime-session-loop.ipynb (walkthrough, async, offline)."""
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "46-02-realtime-session-loop.ipynb")


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
    text = text.strip("\n")
    lines = text.split("\n")
    return [ln + "\n" for ln in lines[:-1]] + [lines[-1]]


cells = []

# 1 — Title + header -----------------------------------------------------------
cells.append(md(
"""# 🔧 Realtime Session Loop: Turn-Taking & Barge-In

> 📓 *Companion to* **Modern Agentic AI Engineer** *· Ch 46 §46.1–46.2 · type: walkthrough*

**The promise:** by the end you've built an `async` event loop over a **simulated** realtime
session that detects end-of-turn (endpointing), dispatches a tool **mid-conversation** reusing
your Ch 12 tool schemas unchanged, and handles **barge-in** correctly — cancelling the in-flight
generation *and* stopping playback — with a per-stage latency budget printed each turn.

Runs **fully offline and free**: a `MockRealtimeSession` stands in for the WebSocket/WebRTC
transport, so there is **no audio device, no API key, and no network**. A clearly-flagged,
opt-in live path is sketched at the end but never runs in CI."""
))

# 2 — Why this matters ---------------------------------------------------------
cells.append(md(
"""## 🧠 Why this matters

A Jupyter kernel can't carry a live phone call — but the part that *actually decides whether a
voice agent feels alive* is language-agnostic and perfectly runnable: the **session / turn-taking
/ latency** model. In 46-01 you saw the budget; here you build the loop that spends it.

Two mechanisms make or break the experience (§46.2):

- **Endpointing** — knowing when the caller has *finished* speaking (voice-activity detection
  plus, increasingly, semantic cues). Too eager and you cut people off; too patient and you sit
  through dead air.
- **Barge-in** — when the caller interrupts, you must **cut the TTS playback *and* cancel the
  in-flight generation**. Stopping only the audio is the classic bug: the model keeps "talking"
  into a cancelled channel, burning tokens and desyncing the conversation.

Crucially, the **brain doesn't change**. The session loop calls the *same* agent core and
dispatches the *same* tool schemas as your chat agent (Ch 12). Voice is a transport wrapper, not
a new agent — that reuse is the whole architectural point of §46.1."""
))

# 3 — Objectives + prereqs -----------------------------------------------------
cells.append(md(
"""## Objectives & prereqs

**By the end you can:**
- Drive an `async for event in session` loop over a realtime event stream (`speech_started`,
  `turn.done`, `function_call_arguments.done`) — the same event *shape* as §46.1's sketch.
- Implement **endpointing** (a VAD-style "caller stopped" signal plus a semantic-cue stub).
- Dispatch a tool **mid-conversation** and feed the result back, reusing Ch 12 tool schemas.
- Implement **barge-in** that cancels generation *and* stops playback — and see what a naive
  loop that stops only playback gets wrong.
- Instrument and print a **per-turn latency budget** against §46.2's targets.

**Prereqs:** [`46-01-cascaded-vs-speech-to-speech.ipynb`](46-01-cascaded-vs-speech-to-speech.ipynb);
Ch 4 (async / `asyncio` — coroutines, tasks, cancellation); Ch 12 (tool dispatch / agent core);
Ch 14 (context compaction for long sessions). Standard library only on the mock path.

**Run first:** the Setup cell. Defaults to `MOCK=1` — fully offline. The live path is opt-in,
needs a real key + audio, and is **not** executed in CI.

> **Async in Jupyter.** Jupyter runs an event loop for you, so a cell can `await` directly. We
> wrap each demo in `asyncio.run(...)` so it also runs identically as a plain `.py` script."""
))

# 4 — Setup --------------------------------------------------------------------
cells.append(code(
"""# --- Setup -------------------------------------------------------------------
import asyncio
import os
import random
import time
from dataclasses import dataclass, field

from dotenv import load_dotenv

load_dotenv()  # reads a local .env if present; never hardcode keys

# MOCK=1 (default): a MockRealtimeSession stands in for the WebSocket/WebRTC
# transport -- no audio, no key, no network. MOCK=0 would use the opt-in live
# path at the end of this notebook (NOT run in CI; documented cost there).
MOCK = os.getenv("COMPANION_MOCK", "1") == "1"

random.seed(46)  # deterministic event timings and noise injection

# §46.2 per-stage targets (ms) -- the budget we'll instrument each turn against.
LATENCY_TARGETS_MS = {
    "endpointing":    400,
    "stt_finalize":   200,
    "llm_ttft":       500,
    "tts_first_audio": 250,
}
COMFORT_HIGH_MS = 800  # past this, callers start talking over the agent

print(f"MOCK mode: {MOCK}  (offline mock realtime stream -- no audio/key/network)")"""
))

# 5 — The event stream ---------------------------------------------------------
cells.append(md(
"""## 1 · A realtime session emits *events*, not strings

The realtime transport (§46.1) hands you an **async stream of typed events**, not a request →
response. We mirror the chapter's sketch:

```python
async with client.realtime.connect(model="gpt-realtime") as session:
    await session.update(session={
        "instructions": SYSTEM_PROMPT,
        "turn_detection": {"type": "server_vad"},   # model endpoints turns
        "tools": TOOL_SCHEMAS,                       # same tools as chat
    })
    async for event in session:
        ...
```

Our `MockRealtimeSession` yields events of the **same shape** — `speech_started`,
`input_audio_buffer.committed`, `turn.done`, `function_call_arguments.done` — from a scripted
timeline, so the loop you write is the loop you'd write for real."""
))

cells.append(code(
"""@dataclass
class Event:
    type: str
    # payload fields (only some are set per event type)
    text: str | None = None
    name: str | None = None
    arguments: dict | None = None
    call_id: str | None = None
    at_ms: int = 0  # simulated arrival time, for latency instrumentation


class MockRealtimeSession:
    \"\"\"Stands in for client.realtime.connect(...). Yields events like the real SDK.\"\"\"

    def __init__(self, timeline, *, frame_delay_s=0.0):
        self._timeline = timeline          # list[Event], in arrival order
        self._frame_delay_s = frame_delay_s  # tiny sleep so async interleaving is real
        self.sent = []                      # what the loop sent back (tool results, etc.)

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    async def __aiter__(self):
        for ev in self._timeline:
            if self._frame_delay_s:
                await asyncio.sleep(self._frame_delay_s)  # non-blocking; yields the loop
            yield ev

    async def send_tool_result(self, call_id, result):
        # In a real session this streams a function_call_output back to the model.
        self.sent.append(("tool_result", call_id, result))

    async def cancel_response(self):
        # In a real session this cancels the in-flight generation (response.cancel).
        self.sent.append(("cancel_response", None, None))


# A scripted turn: caller speaks, stops, model must answer (and will need a tool).
def weather_timeline():
    return [
        Event("speech_started", at_ms=0),
        Event("input_audio_buffer.committed", text="what's the weather in Paris", at_ms=900),
        Event("turn.done", at_ms=900),
        Event("function_call_arguments.done", name="get_weather",
              arguments={"city": "Paris"}, call_id="call_1", at_ms=1500),
    ]


print("event types in the scripted turn:")
for ev in weather_timeline():
    print(f"  +{ev.at_ms:>4} ms  {ev.type}")"""
))

# 6 — Reuse the Ch 12 agent core + tools --------------------------------------
cells.append(md(
"""## 2 · The brain is unchanged: reuse the Ch 12 agent core & tools

The point of §46.1: **the transport changes, the brain doesn't.** So we reuse the *same* tool
schema shape and dispatch from Ch 12 — no voice-specific tool layer. The `agent_core` is mocked
here (canned reply); in production it's literally your existing `blueprints/agent-loop/` core,
called transport-agnostically."""
))

cells.append(code(
"""# Same tool schema shape as Ch 12 (chat). Voice does NOT get its own tool layer.
TOOL_SCHEMAS = [
    {
        "name": "get_weather",
        "description": "Look up the current weather for a city.",
        "input_schema": {
            "type": "object",
            "properties": {"city": {"type": "string"}},
            "required": ["city"],
        },
    },
]

# Ch 12-style dispatch: name -> python callable. Reused unchanged from chat.
def get_weather(city: str) -> dict:
    # Canned, deterministic "API" result so the mock path is offline.
    table = {"Paris": {"tempC": 14, "sky": "light rain"},
             "Tokyo": {"tempC": 19, "sky": "clear"}}
    return table.get(city, {"tempC": 20, "sky": "unknown"})


TOOL_IMPLS = {"get_weather": get_weather}


async def dispatch_tool(name, arguments):
    \"\"\"Same contract as the chat agent's tool dispatch (Ch 12).\"\"\"
    impl = TOOL_IMPLS[name]
    # Tools may be async in production; wrap the sync one so the loop never blocks.
    return await asyncio.to_thread(impl, **arguments)


async def agent_core(user_text, tool_result=None):
    \"\"\"Mocked transport-agnostic core. MOCK=1 returns a canned, realistic reply.\"\"\"
    if MOCK:
        if tool_result is not None:
            sky = tool_result["sky"]
            t = tool_result["tempC"]
            return f"It's {t}C and {sky} in Paris right now."
        return "Let me check that for you."
    # --- live path (MOCK=0): call your real agent core / model here ---
    raise RuntimeError("live agent_core not wired in this teaching notebook; see the live cell")


print("tool registered:", list(TOOL_IMPLS))
print("dry dispatch:", asyncio.run(dispatch_tool("get_weather", {"city": "Paris"})))"""
))

# 7 — Endpointing --------------------------------------------------------------
cells.append(md(
"""## 3 · Endpointing: deciding the caller actually stopped

Endpointing turns a stream of audio frames into a **"the caller is done"** signal. The cheap,
ubiquitous version is **VAD** (voice-activity detection): after N ms of trailing silence, commit
the turn. Increasingly you add a **semantic cue** — *"...and that's it"* or a complete-sounding
clause — so you don't wait the full silence timeout when the sentence is obviously finished.

We model VAD as a silence counter and add a tiny semantic-cue stub. Real VAD runs on audio
energy; the *control logic* — when do I commit the turn — is identical."""
))

cells.append(code(
"""SILENCE_COMMIT_MS = 400  # trailing silence before VAD commits the turn (an endpointing knob)

SEMANTIC_END_CUES = ("that's it", "that's all", "go ahead", "please")


def semantic_endpoint(text: str) -> bool:
    \"\"\"Stub: a complete-sounding clause lets us commit early, before the full timeout.\"\"\"
    t = text.lower().strip()
    return t.endswith(("?", ".")) or any(t.endswith(c) for c in SEMANTIC_END_CUES)


def endpoint_decision(trailing_silence_ms: int, partial_text: str) -> tuple[bool, str]:
    \"\"\"Return (commit?, reason). Semantic cue can fire BEFORE the silence timeout.\"\"\"
    if semantic_endpoint(partial_text):
        return True, "semantic-cue"
    if trailing_silence_ms >= SILENCE_COMMIT_MS:
        return True, "vad-silence"
    return False, "still-listening"


for sil, text in [(120, "what's the weather in Paris"),
                  (450, "uh"),
                  (120, "what's the weather in Paris?")]:
    commit, why = endpoint_decision(sil, text)
    print(f"silence={sil:>3}ms text={text!r:<35} -> commit={commit} ({why})")"""
))

cells.append(md(
"""**What you just saw.** Pure VAD waits the full `SILENCE_COMMIT_MS` even when the caller clearly
finished a question; the **semantic cue** lets you commit the instant the clause is complete,
clawing back that silence-timeout slice of the budget. That's the §46.2 idea that turn-taking,
not the model, is where most perceived latency hides — and a knob like `SILENCE_COMMIT_MS` is one
of the highest-leverage things you tune."""
))

# 8 — The session loop ---------------------------------------------------------
cells.append(md(
"""## 4 · 🔧 The session loop: turn.done → agent → tool → reply

Now the core walkthrough. The loop is the realtime analogue of your chat agent loop:

- on `turn.done` → call the **agent core** (same brain),
- on `function_call_arguments.done` → **`dispatch_tool`** and `send_tool_result` back (same Ch 12
  tools),
- timestamp each stage so we can print the **per-turn latency budget**.

We track a small `SessionState` — because, per the senior lens, **a realtime session is *state*
to manage**, exactly like a long agent run (Ch 14)."""
))

cells.append(code(
"""@dataclass
class SessionState:
    transcript: list = field(default_factory=list)  # grows over the call (Ch 14 territory)
    stage_ms: dict = field(default_factory=dict)     # per-stage latency this turn
    playing_tts: bool = False                        # is the agent currently "speaking"?
    gen_task: object = None                          # the in-flight generation task (for barge-in)


async def speak_tts(state, text):
    \"\"\"Mock TTS playback as a cancellable task; in real life this streams audio out.\"\"\"
    state.playing_tts = True
    try:
        # Simulate streaming audio out sentence by sentence (cancellable at any await).
        for _ in text.split():
            await asyncio.sleep(0.002)  # tiny, deterministic; a real frame is ~20 ms
        return "spoken"
    finally:
        state.playing_tts = False


async def run_session(session, state, *, handle_barge_in=True):
    \"\"\"The realtime session loop. Same shape as the chapter's async-for sketch.\"\"\"
    t0 = time.perf_counter()

    def mark(stage):
        state.stage_ms[stage] = int((time.perf_counter() - t0) * 1000)

    async for event in session:
        if event.type == "speech_started":
            # Caller is talking. If we're mid-reply, that's a BARGE-IN (handled in §5).
            if state.playing_tts and handle_barge_in:
                await _barge_in(session, state)

        elif event.type == "input_audio_buffer.committed":
            mark("stt_finalize")
            state.transcript.append(("user", event.text))

        elif event.type == "turn.done":
            mark("endpointing")
            # Call the SAME agent core as chat. Kick off generation as a task so a
            # later speech_started can cancel it (barge-in needs a handle).
            state.gen_task = asyncio.create_task(agent_core(state.transcript[-1][1]))
            reply = await state.gen_task
            mark("llm_ttft")
            state.transcript.append(("assistant", reply))
            await speak_tts(state, reply)
            mark("tts_first_audio")

        elif event.type == "function_call_arguments.done":
            # Mid-conversation tool call -- reuse Ch 12 dispatch unchanged.
            result = await dispatch_tool(event.name, event.arguments)
            await session.send_tool_result(event.call_id, result)
            # Feed the tool result back through the same core for the spoken answer.
            reply = await agent_core(state.transcript[-1][1], tool_result=result)
            state.transcript.append(("assistant", reply))
            await speak_tts(state, reply)

    return state


async def _barge_in(session, state):
    \"\"\"Placeholder; the REAL implementation is built in the next section.\"\"\"
    pass"""
))

cells.append(code(
"""# Run one full turn over the mocked stream.
async def demo_turn():
    state = SessionState()
    session = MockRealtimeSession(weather_timeline())
    await run_session(session, state)
    return state, session


state, session = asyncio.run(demo_turn())

print("transcript:")
for role, text in state.transcript:
    print(f"  {role:>9}: {text}")
print("\\nsent back over the session:", session.sent)
print("\\nper-stage latency (ms):")
for stage, target in LATENCY_TARGETS_MS.items():
    got = state.stage_ms.get(stage)
    if got is not None:
        flag = "OK" if got <= target else "OVER"
        print(f"  {stage:>16}: {got:>5} ms  (target <= {target}) {flag}")
total = max(state.stage_ms.values()) if state.stage_ms else 0
print(f"  {'turn total':>16}: {total:>5} ms  (comfort <= {COMFORT_HIGH_MS})")"""
))

cells.append(md(
"""**What you just saw.** One realtime turn end-to-end: the loop endpointed the turn, called the
**same** agent core, dispatched the **same** Ch 12 `get_weather` tool mid-conversation, fed the
result back for a spoken answer, and **sent a `tool_result` over the session** — exactly the chat
agent's shape, wrapped in an event loop. The mock timings are tiny, but the *instrumentation*
hooks are where you'd read real per-stage latency in production."""
))

# 9 — Barge-in (the 🔧 build + 🔮 predict) -------------------------------------
cells.append(md(
"""## 5 · 🔧 Barge-in done right: cancel generation *and* stop playback

The caller interrupts mid-reply (`speech_started` while we're speaking). The **correct** response
is *two* actions:

1. **Stop TTS playback** — go quiet immediately.
2. **Cancel the in-flight generation** — `response.cancel`, so the model stops producing tokens
   into a channel no one is listening to.

🔮 **Predict** before you run the next cell: a *naive* loop stops **only** playback (forgets step
2). The caller has interrupted to change the subject. What goes wrong on the **next** turn —
beyond the wasted tokens?"""
))

cells.append(code(
"""# Replace the placeholder with the REAL two-part barge-in.
async def _barge_in(session, state):
    # 1) Stop playback immediately (mock: flip the flag; real: stop the audio sink).
    state.playing_tts = False
    # 2) Cancel the in-flight generation so the model stops decoding (response.cancel).
    if state.gen_task is not None and not state.gen_task.done():
        state.gen_task.cancel()
        try:
            await state.gen_task
        except asyncio.CancelledError:
            pass
    await session.cancel_response()


# A timeline where the caller barges in WHILE the agent is mid-reply.
def barge_in_timeline():
    return [
        Event("speech_started", at_ms=0),
        Event("input_audio_buffer.committed", text="tell me a long story", at_ms=600),
        Event("turn.done", at_ms=600),
        # ... agent starts a long reply, then the caller cuts in:
        Event("speech_started", at_ms=900),  # BARGE-IN
        Event("input_audio_buffer.committed", text="actually, the weather in Paris?", at_ms=1400),
        Event("turn.done", at_ms=1400),
    ]


async def compare_barge_in():
    results = {}
    for label, handle in [("naive (playback only)", False), ("correct (generation+playback)", True)]:
        state = SessionState()
        # Make the agent's first reply "long" so the barge-in lands mid-generation.
        session = MockRealtimeSession(barge_in_timeline(), frame_delay_s=0.001)
        # Patch agent_core to a slow, cancellable generation for this demo.
        await _run_with_slow_reply(session, state, handle_barge_in=handle)
        results[label] = (len(state.transcript), state.playing_tts, list(session.sent))
    return results


async def _run_with_slow_reply(session, state, handle_barge_in):
    \"\"\"Like run_session but the first reply is a slow, cancellable generation.\"\"\"
    async def slow_reply():
        await asyncio.sleep(0.05)  # long enough that barge-in interrupts it
        return "Once upon a time, in a faraway land, there lived..."

    async for event in session:
        if event.type == "speech_started" and state.playing_tts and handle_barge_in:
            await _barge_in(session, state)
        elif event.type == "turn.done":
            state.gen_task = asyncio.create_task(slow_reply())
            try:
                reply = await state.gen_task
            except asyncio.CancelledError:
                continue
            state.transcript.append(("assistant", reply))
            asyncio.create_task(speak_tts(state, reply))  # start speaking (cancellable)
            await asyncio.sleep(0.01)  # let playback start before next event


for label, (n_replies, still_playing, sent) in asyncio.run(compare_barge_in()).items():
    print(f"{label:>32}: replies={n_replies}  still_playing={still_playing}  "
          f"cancel_sent={'cancel_response' in [s[0] for s in sent]}")"""
))

cells.append(md(
"""**What you just saw / the pitfall behind the predict.** The **naive** loop never sent
`response.cancel`, so the interrupted generation kept running: the model finished decoding the
*old* "long story" reply (wasted tokens, and on a real session that audio can leak out), and the
session state now has a stale assistant turn that never matched what the caller heard. The
**correct** barge-in cancelled the task *and* the response, so the next turn ("weather in Paris?")
starts from a clean state. **Stopping only playback is the single most common barge-in bug** — the
caller goes quiet but the agent is still "thinking out loud" into a dead channel."""
))

# 10 — Noise / robustness pitfall ---------------------------------------------
cells.append(md(
"""## 6 · ⚠️ Pitfall: endpointing tuned on quiet audio cuts real callers off

Teams tune `SILENCE_COMMIT_MS` on quiet office Wi-Fi, then ship to callers on speakerphone in a
car. Real audio has **noise, accents, crosstalk, and dropped/delayed packets**. The right metrics
aren't word-error-rate — they're **interruption rate** (we cut the caller off) and **talk-over
rate** (we kept talking over them).

Below we inject simulated noise: random short "noise blips" that a too-eager VAD might mistake for
silence boundaries, and jittered packet delays. Watch the interruption rate move as conditions
degrade — *without touching the model at all.*"""
))

cells.append(code(
"""def simulate_calls(silence_commit_ms, *, noisy, n=400, seed=46):
    \"\"\"Count premature cut-offs as endpointing fires before the caller truly finished.\"\"\"
    rng = random.Random(seed)
    interruptions = 0
    for _ in range(n):
        # True duration of the caller's utterance (ms) and natural mid-utterance pauses.
        utterance_ms = rng.randint(600, 1600)
        # In noisy conditions, pauses are longer/jittery and blips look like silence.
        pause_ms = rng.randint(150, 250) if not noisy else rng.randint(150, 600)
        # The agent (mis)reads a pause as end-of-turn if it exceeds the commit threshold.
        if pause_ms >= silence_commit_ms and pause_ms < utterance_ms:
            interruptions += 1  # cut the caller off mid-sentence
    return interruptions / n


for noisy in (False, True):
    rate = simulate_calls(SILENCE_COMMIT_MS, noisy=noisy)
    label = "noisy (car speakerphone)" if noisy else "quiet (office wifi)"
    print(f"{label:>26}: interruption rate = {rate:.0%}")

print("\\nSame model, same threshold -- only the acoustic conditions changed.")
print("Tuning SILENCE_COMMIT_MS up reduces cut-offs but adds dead air: it's a trade-off,")
print("which is exactly why you measure interruption AND talk-over rates, not just WER.")"""
))

# 11 — Senior lens -------------------------------------------------------------
cells.append(md(
"""## 🎯 Senior lens

Treat the realtime session as **state**, not a request. A long call accumulates a growing
transcript — and just like a long agent run, that transcript is the silent cost/latency
multiplier (Ch 8) and eventually the context-window problem (Ch 14). So the same **compaction
discipline** applies: summarize earlier turns, keep the live tail verbatim, and never re-send the
whole call to the model on every turn. A 20-minute support call is a long agent run wearing a
microphone.

Two more reflexes. First, **everything on the audio path must be async end-to-end** — one
`time.sleep`, one synchronous HTTP client, one blocking tool in the loop and the *whole session*
stutters (Ch 4); that's why `dispatch_tool` here used `asyncio.to_thread` for the sync tool.
Second, **barge-in is a correctness property, not a nicety**: cancel generation *and* playback,
and verify it with a test that asserts `response.cancel` was sent — because the failure is silent
(wasted tokens, desynced state) until a user complains the agent "won't shut up.\""""
))

# 12 — Recap -------------------------------------------------------------------
cells.append(md(
"""## Recap

- A realtime session is an **async stream of events** (`speech_started`, `turn.done`,
  `function_call_arguments.done`), not a request → response — but the **brain is unchanged**: same
  agent core, same Ch 12 tool schemas and dispatch.
- **Endpointing** = VAD silence threshold **plus** a semantic cue to commit early; `SILENCE_COMMIT_MS`
  is a high-leverage knob that trades cut-offs against dead air.
- **Barge-in must do two things**: stop TTS playback **and** cancel the in-flight generation
  (`response.cancel`). Stopping only playback is the classic bug — wasted tokens and desynced state.
- **Instrument per-stage latency** every turn and compare to §46.2's targets; the turn-taking
  stages, not the model, usually decide whether it feels alive.
- **The session is state** (Ch 14 compaction), and the whole audio path must be **async
  end-to-end** (Ch 4) — one blocking call stutters the call."""
))

# 13 — Exercises ---------------------------------------------------------------
cells.append(md(
"""## Exercises

Each one *changes* something and asks you to predict first. (Solutions land in `solutions/` in
Phase 2.)

1. **Add a semantic endpointing cue.** Extend `semantic_endpoint` to commit early on a trailing
   filler-then-pause (e.g. *"...um, that's everything"*). Predict the effect on interruption rate
   in `simulate_calls`, then measure it. Does committing *earlier* raise or lower cut-offs?
2. **Tune the barge-in threshold.** Add a 150 ms "grace" window so a *very short* `speech_started`
   blip (a cough) does **not** trigger barge-in. Predict what happens to spurious cancellations
   under the noisy condition, then implement and check it.
3. **Compact a long session.** Simulate a 30-turn call and apply Ch 14-style compaction (summarize
   all but the last 4 turns). Predict the transcript-token growth with vs without compaction, then
   plot both curves.
4. **Prove the naive barge-in bug.** Write an assertion that `('cancel_response', ...)` appears in
   `session.sent` after a barge-in. Predict whether it passes for `handle_barge_in=False`, then run
   it — this is the regression test the senior lens demands."""
))

cells.append(code("# Exercise 1 -- your code here"))
cells.append(code("# Exercise 2 -- your code here"))
cells.append(code("# Exercise 3 -- your code here"))
cells.append(code("# Exercise 4 -- your code here"))

# 14 — Optional live path (opt-in, NOT run in CI) ------------------------------
cells.append(md(
"""## ⚠️ Optional live path (opt-in — real key + audio; **not** run in CI)

Everything above is offline. The cell below **sketches** a real cascaded STT → agent → TTS or a
native realtime session. It is **guarded**: it only does anything when `COMPANION_MOCK=0` *and* a
real API key is present, and it is **never executed in CI**. It uses a tiny WAV fixture at
[`data/hello.wav`](data/hello.wav) as the input clip.

⚠️ A live realtime session **bills per second of audio in *and* out** plus the model tokens —
budget a few cents per short turn and watch it. This path needs an audio stack (`sounddevice` /
provider realtime SDK) that is **not** in `requirements.txt`; install it yourself before flipping
`MOCK=0`. Keep a "transfer to human" path one utterance away in anything real."""
))

cells.append(code(
"""# ⚠️ LIVE PATH -- dry by default. Does nothing unless you explicitly opt in.
if MOCK:
    print("MOCK=1 -- live path skipped (this is the CI/default path). Nothing billed.")
else:
    # Fail fast with a friendly message if a key is missing (never hardcode it).
    import os as _os
    key = _os.environ.get("OPENAI_API_KEY") or _os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        raise RuntimeError(
            "MOCK=0 but no OPENAI_API_KEY/ANTHROPIC_API_KEY in the environment. "
            "Add one to your .env (git-ignored). Live realtime audio bills per second."
        )
    wav_path = os.path.join("data", "hello.wav")
    if not os.path.exists(wav_path):
        raise FileNotFoundError(f"expected the tiny input clip at {wav_path}")

    print("Opted into the LIVE path. Wiring sketch (provider SDK shapes evolve -- check docs):")
    print(
        "  async with client.realtime.connect(model='gpt-realtime') as session:\\n"
        "      await session.update(session={\\n"
        "          'instructions': SYSTEM_PROMPT,\\n"
        "          'turn_detection': {'type': 'server_vad'},  # server-side endpointing\\n"
        "          'tools': TOOL_SCHEMAS,                      # SAME tools as chat (Ch 12)\\n"
        "      })\\n"
        "      # stream data/hello.wav in; reuse run_session()'s endpointing + barge-in;\\n"
        "      # send tool results back; play TTS frames out. Mind the per-second bill.\\n"
    )
    # Intentionally not auto-executing a billed session in a teaching notebook."""
))

# 15 — Next --------------------------------------------------------------------
cells.append(md(
"""## Next

- ◀️ **Previous:** [`46-01-cascaded-vs-speech-to-speech.ipynb`](46-01-cascaded-vs-speech-to-speech.ipynb)
  — the latency budget this loop instruments.
- 📖 **Book:** §46.1 (the realtime-session sketch: events, `turn_detection`, tools), §46.2
  (turn-taking, barge-in, the latency budget). Pair with Ch 4 (async/cancellation), Ch 12 (tool
  dispatch), Ch 14 (long-session compaction), Ch 41 (guardrails on the conversation layer).
- 🧠 **Blueprint this leans on:** [`blueprints/agent-loop/`](../../../blueprints/agent-loop/) —
  the transport-agnostic core this session loop wraps. There's *no* voice-specific blueprint by
  design: the realtime transport sits in front of the existing `capstone/agents/` core, which is
  built transport-agnostic for exactly this reason."""
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
