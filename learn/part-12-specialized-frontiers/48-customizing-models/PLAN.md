# Ch 48 — Customizing Models

> Companion plan · Part XII · book file `chapters/48-customizing-models.typ`
> Status: 📋 planned (Phase 1)

## Role in the companion
The chapter's spine is a **decision** ("should we fine-tune? — usually *not yet*"), so the
companion leads with a runnable **triage worksheet**, not a training run. The second notebook
makes one technique concrete — a LoRA/PEFT fine-tune on a *small/local* model — but it is
**clearly optional and heavy** ⚠️ (GPU-class, slow) with a fully-mocked default so the chapter
still runs free and green in CI. DPO, distillation, and the agent-training ladder (tool-use
fine-tuning → process reward models → agentic RL → synthetic trajectories) stay **conceptual**,
as the chapter frames them: things you'll *commission or evaluate*, not run.

## Planned notebooks

### 48-01 · `48-01-customization-triage.ipynb` — Prompt vs RAG vs fine-tune, decided on evidence
- **Type:** concept-lab  *(worksheet-flavored — a reusable decision tool)*
- **Maps to:** §48.1 (the customization-triage table; 🧠 *mentalmodel*: telling / showing /
  training the habit; #pitfall: fine-tuning to inject knowledge), §48 #keyidea (the eval *is*
  the prerequisite), §48 #seniorlens (portfolio decision under depreciation) + the closing #checklist
- **Objective:** apply the three-lever triage to a set of scenarios and justify, with a *measured*
  signal, when prompting/RAG plateau enough to consider training.
- **Prereqs:** Ch 10 (prompting) · Ch 13 (RAG) · Ch 22 (evals — the measured plateau).
- **Cell arc:**
  - 🧠 the three levers and what each *changes*: instructions (prompt) / knowledge (RAG) /
    weights = default behavior (fine-tune).
  - Encode the triage table as a small decision function; run several scenarios through it
    (new private facts → RAG; consistent format on a narrow task → maybe fine-tune; …).
  - 🔮 *predict* the right lever for "answers must cite current internal docs" before revealing it.
  - ⚠️ pitfall: fine-tuning to *inject knowledge* — show why it half-memorizes and hallucinates
    in-house-style, worse than vanilla RAG; facts belong in retrieval, form/behavior in weights.
  - A tiny mocked "plateau" demo: a metric that prompting/RAG can't move, motivating training —
    "an agent you cannot evaluate is an agent you cannot train."
  - 📋 fill-in the chapter's decision #checklist for a task of the reader's own.
  - 🎯 senior lens: customization is a *portfolio decision under depreciation* — the durable
    assets are the curated dataset and the eval; weights are a disposable artifact.
- **Datasets/fixtures:** a small `scenarios.json` (task → correct lever + rationale) for self-check.
- **APIs & cost:** none — fully offline (a decision function + a mocked metric).
- **You'll be able to:** make and defend a prompt-vs-RAG-vs-fine-tune call with a measured
  justification instead of fashion.

### 48-02 · `48-02-lora-peft-small-model.ipynb` — ⚠️ Optional/heavy: a LoRA fine-tune you can read
- **Type:** walkthrough  *(explicitly optional · heavy · GPU-class)*
- **Maps to:** §48.2 (🔧 LoRA/PEFT — freeze base, train <1% of params; QLoRA; adapters as
  swappable files; #unglamorous-truth: *data curation* wins fine-tunes, define the eval first),
  §48.3 (RLHF/RLAIF/**DPO** — conceptual), §48.4 (**distillation** / small + edge — conceptual),
  §48.5 ("training agents not just models": tool-use FT, PRMs, agentic RL, synthetic trajectories
  — the cost-ladder table, all conceptual)
- **Objective:** read and run a *minimal* LoRA adapter fit on a tiny local model, see that
  trainable params are a fraction of the base, and understand the technique is a commodity while
  **data curation + a pre-defined eval** are the real work — then place DPO/distillation/agent-RL
  on the conceptual cost ladder.
- **Prereqs:** 48-01 · Ch 22 (define the eval/held-out set *before* training) · Ch 39 (serving:
  adapters on a shared base, rollback) — referenced, not required to run.
- **Cell arc:**
  - ⚠️ **gate cell up front**: this notebook is optional and heavy. `MOCK=1` (default) loads a
    *canned* training log + adapter stats so it runs free and green; `MOCK=0` actually trains and
    needs a GPU and extra deps (`peft`, `transformers`, a tiny base model) — declared here.
  - Curate a *toy* dataset of a few dozen format-shaping examples; hold out a test set first.
  - Configure LoRA on a **tiny/local** base (low rank, a few target modules);
    `print_trainable_parameters()` shows the <1% point — the entire reason for PEFT.
  - 🔮 *predict* whether the adapter can *recall a new fact* (no) vs *enforce a format* (yes),
    then evaluate on the held-out set and confirm form-not-facts.
  - ⚠️ pitfall: a dirty/duplicated/under-curated dataset — a few thousand clean examples beat a
    million scraped ones; PII/licensing/versioning matter.
  - 🧠 **conceptual** map (no training): DPO over (prompt, preferred, rejected) triples;
    distillation (teacher→student, the 10–50× cost-down); and the agent-training ladder —
    tool-use FT → process reward models → agentic RL on rollouts → synthetic trajectories —
    each as "what it buys / when / cost," echoing the chapter's two tables.
  - 🎯 senior lens: every fine-tune is an asset that *depreciates*; keep the prompt fallback
    alive so a base-model swap is an afternoon, not a quarter.
- **Datasets/fixtures:** a tiny toy training/holdout pair + a canned `train_log.json` and
  `adapter_stats.json` in `data/` for the default mock run.
- **APIs & cost:** mock-first (no GPU, no key); the real fit is opt-in `MOCK=0`, GPU-class,
  uses a small local model — **clearly flagged optional/heavy**, skipped in CI.
- **You'll be able to:** explain what LoRA changes (and doesn't), run a toy adapter fit if you
  have the hardware, and locate DPO/distillation/agentic-RL on the cost ladder.

## Feeds (cross-pillar)
- **Blueprint(s):** — (no standalone blueprint; the eval that gates every technique reuses
  [`blueprints/eval-harness/`](../../../blueprints/eval-harness/) — the chapter's #keyidea is
  that the eval suite *is* the reward function and the rejection-sampling verifier).
- **Template(s):** — (the curated-dataset-as-product idea connects to an eval-dataset template
  under Appendix B/F; no template owned here).
- **Capstone:** — (no dedicated module; a fine-tuned/distilled model is "an adapter or a
  deployment on the same serving plane" — `capstone/` serving + rollback, per Ch 39. Noted in recap.)

## Dependencies
- Ch 10 (prompting) · Ch 13 (RAG) · Ch 22 (evals — prerequisite to any training) ·
  Ch 39 (serving adapters / rollback).

## Phase-2 definition of done
- [ ] 48-01 runs fully offline; the triage decisions and the "don't fine-tune to inject
      knowledge" pitfall match §48.1.
- [ ] 48-02 runs **green in `MOCK=1` with no GPU/key/network** (canned log + stats); the real fit
      is opt-in, ⚠️-flagged optional/heavy, declares its extra deps, and is skipped in CI.
- [ ] DPO, distillation, and the agent-training ladder are presented **conceptually**, matching
      the chapter's two tables (no attempt to run RL).
- [ ] LoRA shapes (freeze base, low-rank adapters, <1% trainable) and the "data curation wins"
      message match §48.2; held-out set defined *before* training.
- [ ] Recap + 2–4 exercises (e.g., change LoRA rank and predict the trainable-% shift; draft a
      DPO triple); secrets from env.
