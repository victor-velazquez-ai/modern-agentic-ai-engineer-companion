# Ch 3 — The Mental Model of a Modern AI System

> Companion plan · Part I · book file `chapters/03-mental-model.typ`
> Status: 📋 planned (Phase 1)

## Role in the companion
Part I is orientation, not construction — so this chapter gets a single, high-impact
**concept lab** rather than a build. Its job is to make the book's central diagram *tangible*:
the reader watches one request flow through the four planes and feels where "intelligence"
ends and "engineering" begins. Everything later in the repo is an expansion of one box in
this picture; this notebook is the map they'll keep coming back to.

## Planned notebooks

### 03-01 · `03-01-four-planes-traced.ipynb` — One request through the four planes
- **Type:** concept-lab
- **Maps to:** §3.1 (🧠 anatomy of an agentic app), §3.2 (intelligence vs engineering),
  §3.3 (the four planes), §3.4 (cost/latency/reliability/safety trade-offs)
- **Objective:** trace a single user request end-to-end and label each hop as model,
  orchestration, data, or infrastructure — and name the force being traded at each.
- **Prereqs:** none (first runnable notebook; Ch 1–2 read).
- **Cell arc:**
  - 🧠 the four planes, one diagram (model · orchestration · data · infrastructure).
  - A deliberately tiny, *fully mocked* mini-agent: one retrieval + one model step + one tool.
  - Instrument it: print a labeled trace of each hop (which plane, how long, est. cost).
  - 🔮 *predict* which hop dominates latency, then read the trace and see.
  - Toggle one knob (add a cache hit / a second model call) and re-read the trace.
  - 🎯 senior lens: every design choice later in the book moves one of the four forces —
    cost, latency, reliability, safety — and you can usually see it in this trace.
  - ⚠️ pitfall: mistaking "the model" for "the system" — most failures live in the other
    three planes.
- **Datasets/fixtures:** 2–3 tiny in-memory "documents" (no external services).
- **APIs & cost:** none — fully offline/mock by design (keeps Part I zero-friction).
- **You'll be able to:** point at any future chapter and say which plane and which force it's
  about — the orientation the whole book hangs on.

## Feeds (cross-pillar)
- **Blueprint(s):** — (conceptual; foreshadows `blueprints/observability-stack/` tracing).
- **Template(s):** —
- **Capstone:** no code yet, but this is the mental map of the whole `capstone/` layout
  (Appendix C). Notebook closes by overlaying the four planes on the capstone directory tree.

## Dependencies
- None. This is the recommended **first notebook to run** in the whole repo.

## Phase-2 definition of done
- [ ] Runs top-to-bottom fully offline (no key, no services), deterministically.
- [ ] The four-plane labels and the four forces match the book's §3 terminology exactly.
- [ ] Ends by mapping the planes onto the capstone tree + linking Appendix C.
- [ ] Recap + 2–3 reflection exercises ("which plane is Ch N about?").
