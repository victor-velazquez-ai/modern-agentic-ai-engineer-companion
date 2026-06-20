# Ch 38 — Building AI Interfaces

> Companion plan · Part IX · book file `chapters/38-building-ai-interfaces.typ`
> Status: 📋 planned (Phase 1)

## Role in the companion

This chapter builds the capstone's actual face: a streaming, tool-aware, trust-conscious chat
surface. Its **🔧 Build (§38.5 — the capstone's Next.js frontend)** is a TypeScript/Next.js app —
which a **Jupyter Python kernel cannot run** — so the real artifact is the **`templates/web-starter/`
+ `capstone/web/`** application, *not* a notebook. What a notebook *can* teach, and teach well, is
the part that is genuinely runnable and language-agnostic: the **streaming event protocol** and the
**fold over a typed event stream** that is this chapter's whole mental model. So the single
concept-lab here **mocks an SSE stream in Python**, folds typed events into state, and renders
tool-call/citation "parts" as text — making the wire format and the fold tangible before the reader
opens the TypeScript app. The 🔧 build is explicitly routed to the template/capstone.

## Planned notebooks

### 38-01 · `38-01-streaming-event-protocol-lab.ipynb` — The fold over a typed event stream
- **Type:** concept-lab
- **Maps to:** book §38.1 (streaming UIs / Vercel AI SDK — *protocol only*), §38.2 (rendering
  tool calls, citations, agent steps), §38.4 (optimistic UX & error states). **Not** §38.5: the
  🔧 **Build (the Next.js frontend) is a `templates/web-starter/` + `capstone/web/` app, not a
  notebook** — this lab teaches the protocol the app implements and hands off to it.
- **Objective:** understand a streaming agent UI as a **fold over a typed, validated event stream**
  — `state = reduce(events)` — by mocking the SSE/`useChat`-style stream in Python: emit typed
  events, validate each at the boundary, fold them into message state, and render parts as text.
- **Prereqs:** 37-01 and 37-02 (discriminated unions; UI = f(state); server/client + BFF). The book's
  Ch 25 SSE/streaming backend and Ch 20 human-in-the-loop give the event vocabulary.
- **Cell arc:**
  - 🧠 mental model: *not a chat window — an event-stream renderer.* The backend emits typed events
    (`token`, `tool_call`, `tool_result`/citation, `approval_required`, `done`, `error`); the UI is
    a fold: each event updates state, state renders. (Mirror the book's `useRunStream` exactly.)
  - Define the event union as a Python `dataclass`/`TypedDict` discriminated on `kind`, with a
    boundary validator (the Python stand-in for the book's **Zod `agentEventSchema.parse`**).
  - Mock the stream: a generator yields JSON event lines with small `sleep`s to mimic SSE deltas
    (no network, no model) — the Python analog of `EventSource("/api/runs/{id}/stream")`.
  - The fold: `reduce` events into `{messages, tool_cards, citations, status}`; `token` events
    accumulate into streaming text, `tool_call` flips a card to *executing*, its result to *done*.
  - 🔮 *predict*: given a fixed event script, predict the rendered transcript (text + which tool
    cards + which citations), then run the fold and diff against your prediction.
  - Render "parts" as text: a `switch(part.type)` over `text` / `tool-*` / citation parts — the
    discriminated-union pattern from §37 "arriving exactly where the mental model predicted."
  - ⚠️ pitfall (boundary): a malformed event (bad JSON / schema mismatch) must surface a **retry
    state**, never throw-and-drop silently inside the handler — reproduce the book's `try/parse/catch
    → setError → close` path in Python and show the difference between "drop" and "surface."
  - ⚠️ pitfall (perf, *named not coded*): the naive append-token-then-re-render-everything churn —
    production throttles stream updates, memoizes rendered messages, renders markdown incrementally.
    Explain why (React-specific), and point to `capstone/web/` where the throttle/memo knobs live.
  - 🎯 senior lens: **render the same stream at two fidelities** — a polished timeline for users
    (progress + provenance), a full debug trace for operators (link to the Ch 23 observability
    stack). Honesty budget: show failures, label retries, keep what the user saw stable.
  - 🧩 generative UI & HITL, *conceptually*: a tool result can map to a *component* (an approval
    card with Approve/Reject), not prose — the model picks *which* card from a constrained palette;
    the lab models this as "event kind → component name," with the real components in the capstone.
- **Datasets/fixtures:** a tiny committed event script in `data/` (e.g. `run-events.jsonl`:
  tokens → a `searchDocs` tool_call + result with citations → `done`) plus one malformed event to
  trip the boundary validator. No binaries.
- **APIs & cost:** none — fully offline/mock by design. The stream is *simulated*; no model call, no
  network, deterministic in CI. (A live agent run belongs to the backend chapters, not here.)
- **You'll be able to:** see any streaming agent UI as a fold over a typed event stream, validate
  events at the boundary, reason about tool-card/citation/approval rendering and two-fidelity
  views — then build the real surface in `templates/web-starter/` + `capstone/web/`.

## 🔧 Build (§38.5) routing — the real artifact is a template + capstone, not a notebook

The chapter's 🔧 **Build** assembles a Next.js App Router app (TypeScript · Tailwind · shadcn/ui ·
Vercel AI SDK) with a chat workspace, a run timeline, BFF proxy/route handlers
(`api/chat/route.ts`, `api/runs/[id]/stream/route.ts`), and an `httpOnly`-session auth bridge to
FastAPI. **A Python kernel cannot run or test this.** Phase 2 therefore delivers it as:
- **`templates/web-starter/`** — the copy-into-your-job Next.js starter (app skeleton from §38.5,
  `lib/api.ts` typed-fetch + Zod, session helper, TODO markers, no business logic).
- **`capstone/web/`** — the complete reference frontend wired to the capstone backend (chat,
  `RunTimeline`, `ToolCard`, `ApprovalCard`, BFF stream proxy, `iron-session` auth), at checkpoint
  `checkpoints/ch38-web-frontend`.

The notebook above teaches the protocol/concepts and **ends by pointing here**; it never tries to
"build the frontend" in a cell.

## Feeds (cross-pillar)
- **Blueprint(s):** —
- **Template(s):** [`templates/web-starter/`](../../../templates/web-starter/) — the Next.js
  streaming-chat starter; this chapter's §38.5 Build is its primary source. (The notebook
  contributes only the *protocol/fold* understanding, not code.)
- **Capstone:** advances [`capstone/web/`](../../../capstone/web/) — the platform's user-facing
  frontend (streaming chat, run timeline, tool/citation/approval rendering, BFF auth bridge);
  checkpoint `checkpoints/ch38-web-frontend`. The browser talks only to the Next.js origin; FastAPI
  (`capstone/app/`, Ch 25/26) stays on a private network.

## Dependencies
- Ch 37 (TS/React/Next mental model + discriminated unions) · Ch 25 (SSE/WebSocket streaming
  backend + `POST /runs`, `GET /runs/{id}/stream`) · Ch 26 (auth/JWT the BFF fronts) · Ch 20
  (human-in-the-loop gates rendered as approval cards) · Ch 23 (the trace the debug view links to).
  Requires `capstone/app/` (the FastAPI backend) to exist as the thing the frontend proxies.

## Phase-2 definition of done
- [ ] The notebook runs top-to-bottom in `MOCK=1` with **no Node/network** — the SSE stream is
      simulated in pure Python, deterministically, and green in CI.
- [ ] The event union, the fold, the boundary-validation/retry path, the tool-card/citation/approval
      rendering, and the two-fidelity + honesty principles match the book's §38 exactly.
- [ ] The notebook is explicit that **§38.5's Build is the `templates/web-starter/` + `capstone/web/`
      app, not a notebook**, and ends by linking both.
- [ ] `templates/web-starter/` and `capstone/web/` PLAN/scaffold own the actual UI; the
      `checkpoints/ch38-web-frontend` milestone is referenced. Secrets from env only; no token in
      JS-readable storage anywhere in the examples.
