# Ch 21 — Quality-First: Why Eval & Observability Come Before Scale

> Companion plan · Part VI · book file `chapters/21-quality-first.typ`
> Status: 📋 planned (Phase 1)

## Role in the companion
This chapter is the *why* of Part VI, and the book deliberately places it before backends and
clouds. The single concept-lab makes the chapter's central claim physical: an agent is a
*distribution* of behaviors, not a function, so "it worked when I tried it" is one lucky
sample. The reader runs a tiny noisy agent many times, watches the spread, then turns the
crank of the quality flywheel once (instrument → observe → evaluate → improve) and *sees* the
distribution shift — the intuition every later eval/observability asset depends on.

## Planned notebooks

### 21-01 · `21-01-quality-flywheel.ipynb` — From vibes to a number: one turn of the flywheel
- **Type:** concept-lab
- **Maps to:** §21.1 ("you can't ship what you can't measure" — agent as a distribution),
  §21.2 (the quality flywheel: instrument→observe→evaluate→improve), §21.3 (defining "good":
  constraints / task success / quality gradients), §21.4 (quality culture — error analysis,
  gate-on-evals)
- **Objective:** stop judging an agent by a single run; characterize it as a distribution,
  define "good" as checkable criteria, and run one full flywheel rotation that moves the
  measured score.
- **Prereqs:** none beyond Ch 1–3 read; fully offline. (This is the first notebook of Part VI;
  it sets up the harness vocabulary that Ch 22 turns into real code.)
- **Cell arc:**
  - 🧠 mental model: function vs distribution — the same input, sampled many times, yields a
    spread; quality is the center, variance, and *tail*, not one anecdote.
  - A toy "support agent" (fully mocked, seeded RNG) whose canned outputs carry built-in
    failure modes (a fabricated refund promise, an ungrounded claim) at known rates.
  - Run it once on one friendly input — it looks great. 🔮 *predict* the success rate across
    100 realistic inputs before sampling them.
  - Sample the distribution: plot the pass-rate and surface the alarming tail the demo hid;
    contrast "the friendliest corner of the input space" with the real spread.
  - **Define "good" as layered criteria** (§21.3): hard *constraints* (no fabricated citation,
    no PII leak, valid JSON) that gate; *task success* (issue resolved); *quality gradients*
    (concise, grounded). Encode each as a checkable predicate over a run.
  - 🔧 *instrument*: emit a minimal per-run trace (input, steps, output, latency, est. cost) —
    a hand-rolled foreshadow of Ch 23's OTel spans.
  - *observe → evaluate*: read ten traces, bucket the failures into an error taxonomy, turn
    the buckets into a tiny golden set with tags.
  - *improve*: apply one fix (tighten the system prompt to forbid the bad commitment), re-run
    the suite, and watch the score and the tail move — the flywheel's "edge from observe back
    into evaluate" made concrete.
  - ⚠️ pitfall: *shipping on vibes* — a four-query demo "passes" while a measurable slice is
    confidently wrong; show the gap between the cherry-picked run and the sampled distribution.
  - 🎯 senior lens: writing the success criteria *is* the product decision (eval design as
    requirements engineering); the eval suite, not the prompt, is the durable asset.
  - 📋 the chapter's day-one quality checklist (trace every run, "good" written down, a golden
    set exists, failures feed the suite, one named owner, no change ships without an eval diff).
- **Datasets/fixtures:** a tiny in-notebook set of ~12 realistic support inputs + a seeded mock
  agent with planted failure modes; all generated in-cell, nothing external.
- **APIs & cost:** none — fully offline/mock by design (keeps the Part VI opener zero-friction;
  the *concepts* preview Ch 22's real harness and Ch 23's real tracing).
- **You'll be able to:** describe an agent as a distribution, write layered task-success
  criteria, and run one instrument→observe→evaluate→improve loop that demonstrably moves a
  number — the mindset the next two chapters operationalize.

## Feeds (cross-pillar)
- **Blueprint(s):** — (conceptual; the *evaluate* station foreshadows
  [`blueprints/eval-harness/`](../../../blueprints/eval-harness/) and the *instrument* station
  foreshadows [`blueprints/observability-stack/`](../../../blueprints/observability-stack/)).
- **Template(s):** — (the golden-set sketch here previews
  [`templates/eval-dataset-template/`](../../../templates/eval-dataset-template/), fleshed out
  in Ch 22).
- **Capstone:** no code yet; this is the mental model behind `capstone/evals/` (Ch 22) and the
  telemetry in `capstone/telemetry.py` (Ch 23). The notebook closes by pointing at both.

## Dependencies
- None hard (offline). Conceptually anchors Ch 22 (Evaluation) and Ch 23 (Observability),
  which build the real *evaluate* and *instrument*/*observe* stations of this flywheel.

## Phase-2 definition of done
- [ ] Runs top-to-bottom fully offline (no key, no services), deterministically (seeded).
- [ ] Uses the book's exact vocabulary: distribution/sample, the four flywheel stations, and
      the constraints / task-success / quality-gradients decomposition of "good."
- [ ] Demonstrates a measurable score change across one flywheel rotation; ends with the §21.4
      day-one checklist and links to Ch 22's harness and Ch 23's tracing.
- [ ] Recap + 2–3 reflection exercises (e.g. "add a new failure mode and a criterion to catch
      it; predict then measure the new pass-rate").
