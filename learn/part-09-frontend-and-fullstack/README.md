# Part IX — Frontend & Full-Stack for AI

> Companion to **Modern Agentic AI Engineer**, Part IX · book chapters 37–38
> Status: 📋 planned (Phase 1)

## Companion emphasis

The capstone finally gets a **face**. Two chapters take a backend/ML engineer from "I think
in types and data flow" to a streaming, tool-aware, trust-conscious chat surface wired to the
FastAPI backend. The arc: install the modern-frontend mental model — TypeScript through a
Python lens, React as *UI = f(state)*, Next.js's server/client split, Tailwind + shadcn/ui
(Ch 37) → then build the AI interface itself as a **fold over a typed event stream**: streaming
text, tool-call cards, citations, generative UI, optimistic/error states, and a secure
BFF bridge that keeps the backend token off the browser (Ch 38). Two through-lines run the
whole part: **validate every boundary twice** (the compiler *and* Zod at runtime), and
**the UI is a fold over a typed event stream** — get the event model right and every feature
is just another part type acquiring a visual.

## ⚠️ The real frontend code lives in `templates/` and the capstone — notebooks here teach the protocol

This is the one part where a **Jupyter Python kernel fights the medium**: React/Next.js is
TypeScript that compiles and runs in a browser, not something a Python kernel executes. We are
honest about that rather than forcing janky notebooks:

- **The shipped UI is a *template* and the *capstone*, not a notebook.** The production
  Next.js App Router app (TypeScript · Tailwind · shadcn/ui · Vercel AI SDK) lives in
  [`templates/web-starter/`](../../templates/web-starter/) (copy-into-your-job starter) and
  [`capstone/web/`](../../capstone/web/) (the complete reference frontend). That is where you
  read, run, and build the real interface — `npm install && npm run dev`, not a kernel.
- **The notebooks here teach the *protocol and the concepts* that the UI renders** — the part
  that genuinely *is* runnable from Python and language-agnostic: the **SSE/streaming event
  protocol**, the **discriminated-union event model**, **boundary validation**, and the
  **render/data-flow mental model**. A notebook *mocks an SSE stream in Python* and folds it
  into state so you understand the wire format and the fold before you write a line of React.
- **TypeScript-in-a-notebook is offered, not required.** Ch 37 can use a Deno/`tslab` TS
  kernel for tiny type-level concept-labs (discriminated unions, narrowing) where it adds
  clarity; every such cell has a pure-Python fallback so the part still runs green in CI with
  no Node/Deno toolchain. We never route the *application* build through a notebook.

The rule for this part: **if the medium fights the artifact, name it and point at the
template/capstone.** Notebooks make you *understand the stream and the boundary*; the template
and capstone are where you *build the product*.

## Chapters

| Ch | Title | Companion note | Plan |
|---|---|---|---|
| 37 | Modern Frontend Essentials | Concept-labs — TS-via-Deno/`tslab` (with Python fallbacks) and Python cells that *diagram* the React render & one-way data-flow model and the Next.js server/client boundary. Teaches the mental model; routes the real code to `templates/web-starter/` + `capstone/web/`. | [`37-modern-frontend-essentials/PLAN.md`](37-modern-frontend-essentials/PLAN.md) |
| 38 | Building AI Interfaces | Concept-lab — **mock an SSE/`useChat`-style stream in Python**, fold typed events into state, and render tool-call/citation parts as text so the protocol is tangible. The real artifact (🔧 **Build §38.5** — the Next.js frontend) is the **`templates/web-starter/` + `capstone/web/`** app, explicitly *not* a notebook. | [`38-building-ai-interfaces/PLAN.md`](38-building-ai-interfaces/PLAN.md) |

## Run order

Read in chapter order. **37** installs the vocabulary — types at the boundary, state-driven
components, server-first rendering — and is where you first meet the discriminated-union event
model that the next chapter leans on entirely. **38** uses that model to build the agent
surface: its concept-lab makes the streaming protocol concrete in Python, then explicitly hands
off the 🔧 **Build (§38.5)** to the web template and `capstone/web/`, which is the milestone
(`checkpoints/ch38-web-frontend`) that gives the platform a user-facing front end. The build
artifacts of this part — `templates/web-starter/` and `capstone/web/` — are the face that
Part X (Production LLMOps) then operates, serves, and scales behind.
