# Ch 37 — Modern Frontend Essentials

> Companion plan · Part IX · book file `chapters/37-modern-frontend-essentials.typ`
> Status: 📋 planned (Phase 1)

## Role in the companion

This chapter hands a backend/ML engineer the *mental model* of the modern frontend — TypeScript,
React, Next.js, Tailwind/shadcn — so they can direct generation, review output, and own the
boundaries. The honest constraint: **a Python kernel cannot run React/Next.js**, so these are
**concept-labs**, not application builds. They make the ideas runnable in the medium that *does*
fit — TS-via-Deno/`tslab` for tiny type-level demos (with Python fallbacks), and Python cells
that *diagram and simulate* the React render loop, one-way data flow, and the Next.js
server/client split. The actual UI you'll build lives in `templates/web-starter/` and
`capstone-project/web/`; every notebook ends by pointing there.

## Planned notebooks

### 37-01 · `37-01-typescript-for-python-engineers.ipynb` — TS through a Python lens
- **Type:** concept-lab
- **Maps to:** book §37.1 (TypeScript for backend engineers), §37.4 (styling — light touch)
- **Objective:** read and reason about TypeScript — structural typing, discriminated unions +
  narrowing, generics, and *why types vanish at runtime* — by mapping each idea to its Python
  equivalent (`Protocol`, `Literal`, `TypeVar`, Pydantic-at-the-boundary).
- **Prereqs:** Ch 4 (typing/async mental model); a Deno or `tslab` kernel **optional** —
  every TS cell has a pure-Python fallback so the notebook runs with the Python kernel alone.
- **Cell arc:**
  - 🧠 mental model: "find the types, the data flow, the boundaries" — a frontend is a typed app
    with the same shape as the backend (table mapping TS ↔ Python concepts).
  - Structural typing: an object with the right shape satisfies an `interface` (vs Python classes);
    show the `RunEvent` shape from §37.1.
  - Discriminated unions: model an `AgentEvent` (`token | tool_call | done`) and `switch`-narrow it
    — the single most useful pattern for streamed agent events (foreshadows Ch 38).
  - 🔮 *predict*: which `case` can touch `.text` vs `.answer`? Then run the narrowing and confirm.
  - ⚠️ pitfall: TS types are *erased* — declaring a `fetch` result is `RunEvent` validates nothing;
    a malformed response "explodes three components later." The fix: validate at the boundary with
    **Zod** (the ecosystem's Pydantic). Side-by-side a Python/Pydantic `parse` to anchor it.
  - 🎯 senior lens: *type every boundary twice* — once for the compiler, once for reality.
- **Datasets/fixtures:** none — a few inline event objects (`data/` not needed).
- **APIs & cost:** none — fully offline/mock by design. No model calls; optional TS kernel is the
  only non-Python dependency and is degradable to Python.
- **You'll be able to:** read TS agent-frontend code fluently, spot the "types validate nothing"
  trap, and recognize discriminated unions as the backbone of streamed-event UIs.

### 37-02 · `37-02-react-and-nextjs-mental-model.ipynb` — UI = f(state), server-first
- **Type:** concept-lab
- **Maps to:** book §37.2 (the React mental model), §37.3 (Next.js server/client split)
- **Objective:** internalize *the UI is a function of state* and the Next.js **server/client
  component boundary** without writing React — by simulating the render-on-state-change loop and
  the server-vs-client decision in Python, then reading the real `.tsx` it corresponds to.
- **Prereqs:** 37-01.
- **Cell arc:**
  - 🧠 mental model: state is the only thing that changes; everything else is *derived in render*.
    Diagram one-way dataflow — props down, events up.
  - Simulate it in Python: a tiny `render(state) -> markup-string` pure function + a `set_state`
    that re-invokes `render`; show that changing state (not the "page") drives the UI.
  - Read the real thing: annotate the book's `RunCard`/`useState` `.tsx` snippet against the Python
    simulation, line by line (hooks = capabilities; rules-of-hooks = call order).
  - 🔮 *predict*: given a derived value, should it be stored in state or computed in render? Predict
    the bug if you store it, then show the "duplicated state = denormalized data, no sync" failure.
  - ⚠️ pitfall: **`useEffect` abuse** — using effects to copy props→state / compute derived values /
    chain updates causes extra renders, stale data, infinite loops. Rule: an effect is *only* for
    synchronizing with something *outside* React. Simulate an effect-driven infinite loop to feel it.
  - Next.js server/client split: a Python "renderer" that tags each node *server* (async, can hit
    the DB/FastAPI, ships zero JS) vs *client* (`"use client"`, gets state/handlers); walk the
    `RunsPage` server-component snippet (no `useEffect`, no spinner, no leaked credentials).
  - ⚠️ pitfall: `"use client"` is *infectious* — a stray directive near the root layout drags the
    whole app into the browser bundle. Show the import-graph contagion as a small reachability sim.
  - 🎯 senior lens: **thin BFF, thick service** — the Next.js server half owns presentation
    (sessions, request shaping, streaming pass-through); FastAPI owns the domain. (Sets up Ch 38.)
  - 📋 the chapter's review checklist (types/events/state/effects/boundary/secrets/BFF) as the
    rubric for reviewing AI-generated components.
- **Datasets/fixtures:** none — in-memory toy state; optional tiny SVG/ASCII of the RSC boundary.
- **APIs & cost:** none — fully offline/mock. Pure Python simulation; no Node runtime required.
- **You'll be able to:** decide *what is the minimal source-of-truth state and where it lives*,
  place the server/client boundary at the interactive leaves, and review AI-written React by
  hunting the effects first — then open `templates/web-starter/` and know what you're looking at.

## Feeds (cross-pillar)
- **Blueprint(s):** —
- **Template(s):** the mental model and conventions here are the "read me first" for
  [`templates/web-starter/`](../../templates/web-starter/) — the Next.js App Router starter
  (TypeScript · Tailwind · shadcn/ui) the reader copies into a job. Notebooks close by pointing
  here for the *real* code.
- **Capstone:** orients the reader to [`capstone-project/web/`](../../capstone-project/web/) (the complete
  reference frontend, built in Ch 38). No capstone code is produced in this chapter.

## Dependencies
- Ch 4 (Production Python — typing/async mental model) · Ch 25/26 (the FastAPI backend + auth the
  BFF fronts) for context. Directly sets up Ch 38 (Building AI Interfaces).

## Phase-2 definition of done
- [ ] Both notebooks run top-to-bottom in `MOCK=1` with **no Node/Deno required** (TS cells have
      Python fallbacks); deterministic and fully offline.
- [ ] TS/React/Next.js terminology, the `AgentEvent` union, the server/client split, and the
      `useEffect`/`"use client"` pitfalls match the book's §37 exactly.
- [ ] Each notebook ends with recap + exercises and a link to `templates/web-starter/` and
      `capstone-project/web/` for the real implementation.
- [ ] No secrets; no live API calls; the "the medium can't run React — here's where the real code
      lives" caveat is stated up front in each notebook.
