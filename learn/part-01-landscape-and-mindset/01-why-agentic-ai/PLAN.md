# Ch 1 — Why Agentic AI, and Why Now

> Companion plan · Part I · book file `chapters/01-why-agentic-ai.typ`
> Status: 📋 planned (Phase 1)

## Role in the companion
Part I is orientation, so this chapter gets a single, low-friction **concept lab** rather
than a build. The chapter's whole argument is "a model talks; an agent *accomplishes*" — the
notebook makes that one sentence runnable by wrapping a frozen model call in the smallest
possible reason→act→observe loop, so the reader *feels* the difference before any framework
or production concern arrives. It plants the seed the entire repo grows from (`agents/raw/`,
`blueprints/agent-loop/`) without yet handing over the real thing.

## Planned notebooks

### 01-01 · `01-01-talker-vs-doer.ipynb` — From frozen model to a minimal agent loop
- **Type:** concept-lab
- **Maps to:** §1.1 (from models to agents: the paradigm shift), §1.2 (what "agentic"
  actually means — the four properties), §1.5 (demo vs system ⚠️)
- **Objective:** run the same task two ways — a single model call vs a tiny tool loop — and
  name exactly where the model supplies *judgment* and where *your* code supplies the loop,
  tools, and guardrails.
- **Prereqs:** none (one of the first runnable notebooks; Ch 1 read). No prior chapters.
- **Cell arc:**
  - 🧠 mental model: model as a *reasoning engine*, your system as the *body* (sense / act /
    remember) — the chapter's central reframing, as one diagram.
  - The "talker": one mocked model call answering a question it cannot actually look up;
    watch it guess or refuse.
  - 🔮 *predict* whether a bare model can answer a question needing a live lookup (a made-up
    fact / a calculation), then run it and see it fail.
  - The "doer": wrap that same model in a ~15-line reason→act→observe loop with one tiny tool
    (a lookup over an in-memory dict); watch it call the tool, read the result, then answer.
  - Score the run against the chapter's four properties (autonomy · tool use · goals ·
    feedback loops) — print where each shows up in the trace.
  - Slide the autonomy "knob": cap max-steps at 1 vs 3 and re-read the trace — agentic is a
    *spectrum*, not a label (§1.2 key idea).
  - ⚠️ pitfall: mistaking a happy-path *demo* for a *system* — point at everything this toy
    skips (validation, errors, cost, eval) that Parts II–VI will fill in.
  - 🎯 senior lens: "not a drop more autonomy than you can evaluate and control" — why each
    degree of freedom is a thing you must observe and bound.
- **Datasets/fixtures:** 2–3 tiny in-memory "facts" for the lookup tool; no external services.
- **APIs & cost:** none by design — fully offline/mock (`MOCK=1` returns canned model turns)
  so Part I stays zero-friction and zero-cost; an optional live path (`MOCK=0`) is ≈ 2 short
  calls and is documented but never required.
- **You'll be able to:** explain, with a trace you produced, why "agent = model + loop +
  tools + guardrails," and place any system on the agentic spectrum.

## Feeds (cross-pillar)
- **Blueprint(s):** — (conceptual; the toy loop foreshadows
  [`blueprints/agent-loop/`](../../../blueprints/agent-loop/), built for real in Ch 12).
- **Template(s):** —
- **Capstone:** no code yet; the notebook closes by pointing at `capstone/agents/raw/` as
  "the real version of this toy, which you'll build starting in Ch 12" — frame is *build
  yours first*, not copy.

## Dependencies
- None. Safe to run before any other notebook (offline, no key). Pairs with Ch 3's
  four-planes lab as the two orientation notebooks of Part I.

## Phase-2 definition of done
- [ ] Runs top-to-bottom fully offline (no key, no services), deterministically in `MOCK=1`.
- [ ] The four agentic properties and "spectrum" framing match the book's §1.2 wording exactly.
- [ ] The talker-vs-doer contrast is unmistakable in the printed trace; loop stays minimal
      (no framework) so the mechanism is visible.
- [ ] Recap + 2–3 reflection exercises (e.g., "add a second tool"; "where would this break in
      production?") and a forward link to Ch 12 / `blueprints/agent-loop/`.
