"""Generate 38-01-streaming-event-protocol-lab.ipynb as valid nbformat-4.5.

Run:  python _build_nb.py   (then delete this helper; not part of the lab)
"""
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "38-01-streaming-event-protocol-lab.ipynb")


def md(text):
    # Split keeping newlines on each line, nbformat style (list of "line\n").
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
    text = text.rstrip("\n")
    lines = text.split("\n")
    return [l + "\n" for l in lines[:-1]] + [lines[-1]] if lines else [""]


cells = []

# 1. Title + header -----------------------------------------------------------
cells.append(md(
"""# Streaming agent UIs: the fold over a typed event stream

> 📓 *Companion to* **Modern Agentic AI Engineer** *· Ch 38 §38.1–38.2, §38.4 · type: concept-lab*

**The promise:** you will stop seeing a streaming agent UI as a "chat window" and start seeing it as what it is — `state = reduce(events)`, a fold over a typed, validated event stream. You'll mock the SSE stream in pure Python, validate each event at the boundary, fold it into message state, and render tool-call/citation/approval "parts" as text — the exact mental model the capstone's Next.js frontend implements.
"""))

# 2. Why this matters ---------------------------------------------------------
cells.append(md(
"""## 🧠 Why this matters

The backend doesn't send a "reply." It emits a *typed stream of events* — `token`, `tool_call`, `tool_result` (with citations), `approval_required`, `done`, `error` — the structured SSE events designed in Ch 25. The UI is a **fold** over that stream: each event updates state, and the state renders. That's it.

Get this one idea right and every feature in the chapter — streaming text, tool-call cards, citations, progress timelines, approval gates — is just *a different event kind acquiring a different visual*. Get it wrong and every feature becomes a special case bolted onto a string. The frontend is `useChat`/`useRunStream` in TypeScript; the *protocol and the fold* are language-agnostic, so we teach them here in Python where a Jupyter kernel can actually run them — then hand off to the real TypeScript surface.
"""))

# 3. Objectives + prereqs -----------------------------------------------------
cells.append(md(
"""## Objectives & prereqs

**By the end you can:**
- Model an agent event stream as a **discriminated union** keyed on `kind`, and validate each event **at the boundary** (the Python stand-in for the book's Zod `agentEventSchema.parse`).
- Write the **fold**: `reduce(events) -> {messages, tool_cards, citations, status}`, accumulating `token`s into streaming text and flipping `tool_call` cards from *executing* to *done*.
- Reproduce the **boundary-validation / retry** path — a malformed event surfaces a retry state instead of throwing-and-dropping silently — and render parts at **two fidelities** (user timeline vs. operator trace).

**Prereqs:** Ch 37 (discriminated unions; `UI = f(state)`; server/client + BFF). The event vocabulary comes from Ch 25 (SSE/WebSocket streaming backend) and Ch 20 (human-in-the-loop gates). Fixture: `data/run-events.jsonl`.

**Runs free & offline.** `MOCK=1` (default) *simulates* the SSE stream in pure Python — no Node, no network, no model call, deterministic in CI. There is intentionally **no live path**: a real agent run belongs to the backend chapters (Ch 25/26), not to this protocol lab.
"""))

# 4. Setup --------------------------------------------------------------------
cells.append(code(
'''# Setup — imports, env, and the MOCK switch.
import json
import os
import time
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

# MOCK=1 (default) keeps this notebook free, offline, and fully deterministic.
# This lab is mock-ONLY by design: the "stream" is simulated locally; there is
# no API key to set and no network call to make. A real agent run is a backend
# concern (Ch 25/26), not a frontend-protocol concern.
MOCK = os.getenv("COMPANION_MOCK", "1") == "1"

# Tiny sleeps simulate SSE delta pacing so you SEE tokens "arrive". Deterministic.
DELTA_PAUSE = 0.0 if not MOCK else 0.01

DATA = Path("data")
print("MOCK mode:", MOCK, "— offline, no API key, simulated SSE stream")
print("fixture exists:", (DATA / "run-events.jsonl").exists())
'''))

# 5. Body ---------------------------------------------------------------------

# 5a. the event union + boundary validator
cells.append(md(
"""## 1 · The event union (discriminated on `kind`)

The wire format is a **discriminated union**: every event is a JSON object with a `kind` tag, and the tag decides the rest of the shape. In the TypeScript frontend this is a Zod schema (`agentEventSchema`); here it's a set of dataclasses plus one `parse_event()` boundary function. Same contract, runnable kernel.

The kinds, straight from §38.2: `token` (a text delta), `tool_call` (the agent invoked a tool), `tool_result` (the result, carrying **citations** for RAG), `approval_required` (a Ch 20 human-in-the-loop gate), `done`, and `error`.
"""))

cells.append(code(
'''# The event types. Each carries exactly the fields its `kind` needs — the
# Python analog of a Zod discriminated union (`z.discriminatedUnion("kind", ...)`).

@dataclass
class Citation:
    id: str
    title: str
    url: str


@dataclass
class TokenEvent:
    text: str
    kind: str = "token"


@dataclass
class ToolCallEvent:
    id: str
    name: str
    args: dict
    kind: str = "tool_call"


@dataclass
class ToolResultEvent:
    id: str
    name: str
    citations: list  # list[Citation]
    kind: str = "tool_result"


@dataclass
class ApprovalRequiredEvent:
    id: str
    action: str       # human-readable: "Send this email to 1,200 customers?"
    component: str     # which card to render, from a CONSTRAINED palette
    kind: str = "approval_required"


@dataclass
class DoneEvent:
    finish_reason: str = "stop"
    kind: str = "done"


@dataclass
class ErrorEvent:
    message: str
    kind: str = "error"


# A constrained palette: event kind -> component name. Generative UI means the
# model picks WHICH card from this small set; it never emits arbitrary markup.
COMPONENT_FOR = {
    "tool_call": "ToolCard",
    "tool_result": "ToolCard",
    "approval_required": "ApprovalCard",
}


class EventValidationError(ValueError):
    """Raised at the boundary when a raw event is malformed or unknown."""


def parse_event(raw: dict):
    """Validate ONE raw event at the boundary and return a typed object.

    This is the Python stand-in for the book's `agentEventSchema.parse(...)`.
    It is strict on purpose: an unknown `kind` or a missing required field is an
    error to be SURFACED (retry state), never a thing to silently drop.
    """
    if not isinstance(raw, dict) or "kind" not in raw:
        raise EventValidationError(f"event has no 'kind': {raw!r}")
    kind = raw["kind"]
    try:
        if kind == "token":
            return TokenEvent(text=raw["text"])
        if kind == "tool_call":
            return ToolCallEvent(id=raw["id"], name=raw["name"], args=raw["args"])
        if kind == "tool_result":
            cites = [Citation(**c) for c in raw["citations"]]
            return ToolResultEvent(id=raw["id"], name=raw["name"], citations=cites)
        if kind == "approval_required":
            return ApprovalRequiredEvent(
                id=raw["id"], action=raw["action"], component=raw["component"]
            )
        if kind == "done":
            return DoneEvent(finish_reason=raw.get("finish_reason", "stop"))
        if kind == "error":
            return ErrorEvent(message=raw["message"])
    except (KeyError, TypeError) as exc:
        raise EventValidationError(f"malformed {kind!r} event: {raw!r} ({exc})") from exc
    raise EventValidationError(f"unknown event kind {kind!r}: {raw!r}")


print("event types + boundary validator defined")
'''))

# 5b. mock the stream
cells.append(md(
"""## 2 · Mock the SSE stream

A real frontend opens `new EventSource("/api/runs/{id}/stream")` and receives newline-delimited JSON deltas. We reproduce the *shape* with a generator that reads our fixture (`data/run-events.jsonl`) and yields raw JSON lines with a tiny `sleep` between them — no network, no model, deterministic. This is the only place "the wire" exists.
"""))

cells.append(code(
'''def sse_stream(path):
    """Yield raw event dicts as if they were arriving over SSE.

    The Python analog of EventSource delivering one `msg.data` line at a time.
    Each yielded value is still UNVALIDATED — exactly like `msg.data` is a raw
    string until `JSON.parse` + schema validation run at the boundary.
    """
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        time.sleep(DELTA_PAUSE)  # simulate decode/SSE pacing; deterministic & tiny
        yield json.loads(line)


# Peek at the raw stream shape (validation comes next).
for i, raw in enumerate(sse_stream(DATA / "run-events.jsonl")):
    print(f"{i:>2}: {raw['kind']:<18} {json.dumps(raw)[:70]}")
'''))

# 5c. the fold
cells.append(md(
"""## 3 · The fold — `state = reduce(events)`

This is the whole chapter in one function. The UI state is `{messages, tool_cards, citations, status}`; each event kind updates it:

- `token` → **accumulate** into the streaming assistant text.
- `tool_call` → add a card in status **`executing`**.
- `tool_result` → flip that card to **`done`** and stash its citations.
- `approval_required` → add an **approval card** (the Ch 20 gate, now visible).
- `done` / `error` → set terminal `status`.

In the frontend this is `RunTimeline` reading the validated `events` array. Same fold, different render target.
"""))

cells.append(code(
'''@dataclass
class UIState:
    text: str = ""                                   # streaming assistant message
    tool_cards: dict = field(default_factory=dict)   # id -> {name, args, status, result}
    citations: list = field(default_factory=list)    # list[Citation]
    status: str = "streaming"                        # streaming | done | error
    error: str | None = None


def fold(state: UIState, ev) -> UIState:
    """Apply ONE validated event to state. This is the reducer."""
    if isinstance(ev, TokenEvent):
        state.text += ev.text
    elif isinstance(ev, ToolCallEvent):
        state.tool_cards[ev.id] = {
            "name": ev.name, "args": ev.args, "status": "executing", "result": None,
        }
    elif isinstance(ev, ToolResultEvent):
        card = state.tool_cards.setdefault(ev.id, {"name": ev.name, "args": {}})
        card["status"] = "done"
        card["result"] = f"{len(ev.citations)} source(s)"
        state.citations.extend(ev.citations)
    elif isinstance(ev, ApprovalRequiredEvent):
        state.tool_cards[ev.id] = {
            "name": ev.action, "args": {}, "status": "awaiting_approval",
            "component": ev.component, "result": None,
        }
    elif isinstance(ev, DoneEvent):
        state.status = "done"
    elif isinstance(ev, ErrorEvent):
        state.status = "error"
        state.error = ev.message
    return state


def run_fold(path, on_error="surface"):
    """Consume the stream, validate each event at the boundary, fold into state.

    `on_error="surface"` reproduces the book's try/parse/catch -> setError -> close:
    a bad event stops the stream and surfaces a retry state. `on_error="drop"` is
    the WRONG behaviour we contrast against in the pitfall below.
    """
    state = UIState()
    for raw in sse_stream(path):
        try:
            ev = parse_event(raw)
        except EventValidationError as exc:
            if on_error == "surface":
                state.status = "error"
                state.error = "lost connection — retrying"  # drives a retry UI
                break                                          # es.close()
            else:  # on_error == "drop": silently swallow — DO NOT do this
                continue
        state = fold(state, ev)
        if state.status in ("done", "error"):
            break
    return state


print("fold + run_fold defined")
'''))

# 5d. Predict
cells.append(md(
"""## 🔮 Predict

Here's the fixed event script we'll fold (from `data/run-events.jsonl`):

```
token "Checking " · token "the docs now.\\n" ...
tool_call searchDocs {query: "vector index rebuild"}
tool_result searchDocs  -> 2 citations
token "Rebuild ... swap atomically [1][2]."
done
```

**Predict, before running the next cell:**
1. What is the final rendered **assistant text**?
2. How many **tool cards**, and in what final **status**?
3. How many **citations** end up anchored to `[1][2]`?

Decide, then run the fold and diff against your prediction.
"""))

cells.append(code(
'''state = run_fold(DATA / "run-events.jsonl")

print("status   :", state.status)
print("text     :", repr(state.text))
print("tool cards:")
for tid, card in state.tool_cards.items():
    print(f"   {tid}: {card['name']} [{card['status']}] -> {card['result']}")
print("citations:")
for i, c in enumerate(state.citations, 1):
    print(f"   [{i}] {c.title} <{c.url}>")
'''))

cells.append(md(
"""**What you just saw.** The text accumulated *only* from `token` events; the `searchDocs` card was created by `tool_call` and flipped to `done` by the matching `tool_result` (same `id`); the two citations are exactly the ones the `[1][2]` markers point at. Nothing here special-cased "rendering" — every visual is a consequence of an event kind hitting the reducer. That is the payoff of the fold: the renderer is boring on purpose.
"""))

# 5e. render parts as text (switch over part.type)
cells.append(md(
"""## 4 · Render "parts" as text — a `switch(part.type)`

A message in the modern SDK is **not a string** — it's a list of typed *parts* (text, `tool-*`, citation). The renderer is a `switch` over `part.type`, the discriminated-union pattern from §37 "arriving exactly where the mental model predicted." Here we render at **user fidelity**: a clean transcript a person can trust.
"""))

cells.append(code(
'''def render_user_timeline(state: UIState) -> str:
    """User fidelity: progress + provenance, no raw JSON. The product surface."""
    parts = []
    for tid, card in state.tool_cards.items():
        if card["status"] == "awaiting_approval":
            parts.append(f"[ {card['component']} ] {card['name']}  (Approve / Reject)")
        else:
            icon = "✓" if card["status"] == "done" else "…"
            parts.append(f"[ {card['name']} {icon} ] {card.get('result') or 'executing'}")
    parts.append(state.text.strip())
    out = "\\n".join(p for p in parts if p)
    if state.citations:
        out += "\\n\\nSources:"
        for i, c in enumerate(state.citations, 1):
            out += f"\\n  [{i}] {c.title} — {c.url}"
    if state.status == "error":
        out += f"\\n\\n⚠️  {state.error}  [Retry]"
    return out


print(render_user_timeline(state))
'''))

cells.append(md(
"""**What you just saw.** One `switch`-style loop turns validated state into a transcript: the tool card shows *what it did* (not a JSON blob), and citations anchor the claim. Swap the body of this function and you get a different surface from the *same* state — which is exactly the senior move below.
"""))

# 5f. Pitfall 1 — boundary
cells.append(md(
"""## ⚠️ Pitfall 1 — the boundary: surface, don't drop

A malformed event (bad JSON, schema mismatch, unknown `kind`) is **not** a thing to swallow inside the handler. The book's frontend does `try { agentEventSchema.parse(...) } catch { setError("lost connection — retrying"); es.close() }`. The failure becomes a **retry state the user sees** — never a silently-dropped event that leaves the UI quietly wrong.

We append one malformed event to the script and fold it two ways: `surface` (correct) vs. `drop` (the tidy-looking bug).
"""))

cells.append(code(
'''# Build a stream WITH a malformed event in the middle (unknown kind + missing field).
good = [json.loads(l) for l in (DATA / "run-events.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
bad_event = {"kind": "tool_result", "id": "tc_oops"}   # missing name + citations
corrupted = good[:4] + [bad_event] + good[4:]

# Write a throwaway corrupted fixture next to the lab (tiny; safe to overwrite).
corrupt_path = DATA / "_run-events-corrupted.jsonl"
corrupt_path.write_text("\\n".join(json.dumps(e) for e in corrupted) + "\\n", encoding="utf-8")

surfaced = run_fold(corrupt_path, on_error="surface")
dropped = run_fold(corrupt_path, on_error="drop")

print("SURFACE (correct):")
print("   status:", surfaced.status, "| error:", surfaced.error)
print("   -> the UI shows a retry affordance; the user knows something broke.\\n")

print("DROP (the bug):")
print("   status:", dropped.status, "| error:", dropped.error)
print("   -> stream 'completes' but the searchDocs card is stuck 'executing'")
print("      and citations are MISSING — a confident, wrong transcript.")

# Clean up the throwaway fixture so the repo stays tidy.
corrupt_path.unlink()
'''))

cells.append(md(
"""**What you just saw.** `surface` stops the fold and sets a retry state — honest. `drop` lets the run *look* finished while the tool card never resolves and the citations vanish: the display lies. The boundary validator is the one line standing between "trustworthy" and "confidently wrong."
"""))

# 5g. Pitfall 2 — perf, named not coded
cells.append(md(
"""## ⚠️ Pitfall 2 — the perf trap (named, not coded)

The naive frontend appends every streamed token *with a state update*, re-rendering the **entire** message list hundreds of times per response — fine in a demo, visibly janky on long transcripts with markdown. This is React-specific and has nothing to teach in a Python kernel, so we name it rather than fake it:

- **Throttle** stream-driven updates (the Vercel AI SDK exposes a knob).
- **Memoize** rendered messages so only the *growing* one re-renders.
- **Render markdown incrementally** instead of re-parsing the whole buffer per token.

These knobs live in [`../../../capstone/web/`](../../../capstone/web/) (the throttle/memo config), not here. If your real chat stutters while streaming, this — not the network — is almost always why.
"""))

# 6. Senior lens --------------------------------------------------------------
cells.append(md(
"""## 🎯 Senior lens — one stream, two fidelities; spend the honesty budget

Decide *who* each surface is for. **End users** need progress and provenance — *what is it doing, why should I believe it* — not raw tool JSON. **Operators** need the full trace. The architecture that serves both: render the **same** validated event stream at **two fidelities** — a polished timeline in the product, and a debug view (or a link into the Ch 23 observability stack) behind a flag. Teams that skip the second view end up debugging production agents through screenshots of the first.

Two more judgments a senior applies here:
- **Generative UI is a constrained palette.** A `tool_result` can map to a *component* (an `ApprovalCard` with Approve/Reject), not prose — but the model only ever picks *which* card from a small set you designed (`COMPONENT_FOR`). Letting a model emit arbitrary markup is `innerHTML` with extra steps: a security hole and a design disaster.
- **The interface's honesty budget is the product's.** Show failures, label retries, and keep what the user *saw* stable — never silently retry into a different answer than the one they watched stream.
"""))

cells.append(code(
'''def render_operator_trace(state: UIState) -> str:
    """Operator fidelity: the SAME state, rendered as a full debug trace.

    In production this view links into the Ch 23 trace; here it just dumps the
    raw card args + status so an engineer can audit the run.
    """
    lines = [f"status={state.status} error={state.error!r}", "tool_cards:"]
    for tid, card in state.tool_cards.items():
        lines.append(f"  {tid}  {card['status']:<16} name={card['name']!r} args={card.get('args')}")
    lines.append(f"citations: {[c.id for c in state.citations]}")
    lines.append(f"text_len: {len(state.text)} chars")
    return "\\n".join(lines)


# Same fold output, two renderers — that's the whole point.
state = run_fold(DATA / "run-events.jsonl")
print("=== OPERATOR TRACE (debug view, behind a flag) ===")
print(render_operator_trace(state))
print("\\n=== USER TIMELINE (the product) ===")
print(render_user_timeline(state))
'''))

# 7. Recap --------------------------------------------------------------------
cells.append(md(
"""## Recap

- A streaming agent UI is **not a chat window** — it's an **event-stream renderer**: `state = reduce(events)`.
- Events are a **discriminated union** on `kind` (`token`, `tool_call`, `tool_result`, `approval_required`, `done`, `error`), **validated at the boundary** (the Zod `agentEventSchema.parse` / our `parse_event`).
- The **fold** folds events into `{text, tool_cards, citations, status}`: `token`s accumulate, `tool_call` → `tool_result` flips a card *executing → done*, approvals become cards.
- A **malformed event must surface a retry state**, never be dropped — `drop` produces a confident, wrong transcript.
- Render the **same** state at **two fidelities** (user timeline / operator trace); generative UI is a **constrained component palette**; the perf trap is React-side throttle + memoize, owned by the capstone.
- The 🔧 **Build (§38.5) is a Next.js app, not a notebook** — this lab teaches the protocol it implements and hands off.
"""))

# 8. Exercises ----------------------------------------------------------------
cells.append(md(
"""## Exercises

Each one *changes the event stream or the fold* — predict the rendered result first, then run it.

1. **Render an approval gate.** Insert an `approval_required` event (`{"kind":"approval_required","id":"ap_1","action":"Send this email to 1,200 customers?","component":"ApprovalCard"}`) before `done`. Predict what `render_user_timeline` shows, then fold the new stream and confirm the card reads "Approve / Reject".
2. **Interleave two tool calls.** Add a second `tool_call`/`tool_result` pair (`name="lookupCustomer"`) between the existing ones, with one citation. Predict the final card count and citation numbering, then verify the `[n]` markers still line up.
3. **Stream dies mid-sentence.** Replace `done` with `{"kind":"error","message":"upstream timeout"}` after the last token. Predict `state.status`, what the user timeline appends, and why keeping the partial `state.text` matters (§38.4 honesty). Then show it.
4. **Markdown-part stub (design).** Without coding React, sketch in a markdown cell how `render_user_timeline` would change if `token` text were *incremental markdown* — which line throttles, which memoizes, and why (tie it to Pitfall 2).
"""))

cells.append(code('''# Exercise 1 — your code here.
'''))
cells.append(code('''# Exercise 2 — your code here.
'''))
cells.append(code('''# Exercise 3 — your code here.
'''))

# 9. Next ---------------------------------------------------------------------
cells.append(md(
"""## Next

You built the *toy*: the protocol and the fold in pure Python. Here's the **real surface** that implements exactly this:

- **Template (start here):** [`../../../templates/web-starter/`](../../../templates/web-starter/) — the copy-into-your-job Next.js streaming-chat starter (app skeleton from §38.5, `lib/api.ts` typed-fetch + Zod, `lib/events.ts` = the `agentEventSchema` this lab mirrors, session helper, TODO markers).
- **Capstone (the finished thing):** [`../../../capstone/web/`](../../../capstone/web/) — the complete reference frontend wired to the FastAPI backend: streaming chat, `RunTimeline`, `ToolCard`, `ApprovalCard`, the BFF stream proxy, and `iron-session` auth. Milestone: `checkpoints/ch38-web-frontend`. The browser talks **only** to the Next.js origin; FastAPI ([`../../../capstone/app/`](../../../capstone/app/), Ch 25/26) stays on a private network.
- **Book:** §38.1 (streaming UIs / Vercel AI SDK), §38.2 (tool calls, citations, agent steps), §38.4 (optimistic UX & error states), §38.5 (the Build). Event vocabulary: §25 (SSE backend); approval gates: §20; the trace the debug view links to: §23.
"""))

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

print("wrote", OUT)
print("cells:", len(cells))
