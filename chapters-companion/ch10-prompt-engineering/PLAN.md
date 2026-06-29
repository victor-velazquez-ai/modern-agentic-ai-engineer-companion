# Ch 10 — Prompt Engineering as Engineering

> Companion plan · Part III · book file `chapters/10-prompt-engineering.typ`
> Status: 📋 planned (Phase 1)

## Role in the companion
This chapter's thesis is that a prompt is an *interface spec* with owners, versions, and tests —
so the companion treats prompts like code and proves it. The notebooks move from technique
(few-shot, CoT, decomposition, self-consistency) to the engineering that makes prompts survive
model upgrades: schema-enforced structured output with a repair loop, and a versioned prompt
*registry* with an eval-style test suite. The chapter's 🔧 Build (the `PromptRegistry`) is built
here and graduates into [`templates/prompt-template/`](../../templates/prompt-template/).

## Planned notebooks

### 10-01 · `10-01-techniques-that-matter.ipynb` — Few-shot, CoT, decomposition, self-consistency
- **Type:** walkthrough
- **Maps to:** book §10.1 (the prompt as an interface), §10.2 (techniques that matter), §10.3
  (engineering against hallucination — ground + escape hatch)
- **Objective:** apply the four high-value technique families to a real task and *measure* the lift
  instead of eyeballing one good output.
- **Prereqs:** Ch 9 (sampling — self-consistency needs nonzero temperature);
  `learn/part-03-llm-substrate/09-*`.
- **Cell arc:**
  - 🧠 mental model: the system prompt is a spec for a capable new hire — role, goal, constraints,
    resources, output format, what to do when unsure; data delimited from instructions (XML-style
    tags) as the first line of defense against injection.
  - A baseline zero-shot prompt on a small ticket-triage task; record accuracy on a tiny labeled set.
  - Add **few-shot** examples covering the tricky cases (ambiguous ticket, empty input); re-measure.
  - Add **chain-of-thought** (reason first, answer last); show the lift on the multi-step items, and
    note reasoning models do this internally (depth via an effort param, Ch 9).
  - **Decomposition**: split a 5-job prompt into a 2–3 step pipeline; observe each step gets testable
    and better. **Self-consistency**: sample a hard item N× and take the majority.
  - 🔮 *predict* which technique helps which item type before revealing scores.
  - Hallucination first-aid from §10.3: *ground, don't recall* (answer only from provided context)
    and *grant an escape hatch* ("if the context doesn't cover it, say so and stop").
  - 🎯 senior lens: decomposition is the single most reliable quality move and the seed of agents
    (Ch 16) — an agent is decomposition made dynamic.
  - ⚠️ pitfall: "do not hallucinate" / "only state true facts" accomplishes nothing — there's no
    truth-checking faculty to invoke; the levers are grounding + the escape hatch.
- **Datasets/fixtures:** `data/` — ~8–12 labeled triage tickets (tiny, committed) + 2–3 context docs.
- **APIs & cost:** mockable — `MOCK=1` returns canned per-technique responses so scores are
  deterministic; `MOCK=0` runs the task live (self-consistency is N× calls — keep N small, flagged).
- **You'll be able to:** choose the right technique per problem and show its effect with numbers.

### 10-02 · `10-02-structured-output-and-repair.ipynb` — JSON, schemas, validate-and-repair
- **Type:** walkthrough  *(structured-output mechanism the chapter leans on)*
- **Maps to:** book §10.4 (structured output: JSON, schemas, tool-shaped outputs)
- **Objective:** get machine-consumable output reliably — escalate from prompted JSON to
  schema-enforced output, and wrap it in a Pydantic validate-and-repair loop.
- **Prereqs:** 10-01.
- **Cell arc:**
  - 🧠 mental model: most LLM calls end at a *parser*, not a human — "usually valid JSON" is a bug
    factory; the guarantee must be engineered.
  - The toolkit in increasing strength: prompted JSON → JSON mode → schema-enforced (strict mode /
    the *tool-shaped* trick: one tool whose input schema *is* your output shape).
  - Define a `Ticket` Pydantic model (category / urgency / summary); `model_validate_json` the raw.
  - 🔮 *predict* what a schema does *not* catch — then show a syntactically valid object with a
    wrong value in the right field ("shape, not sense").
  - Build the one-pass **repair** loop: on `ValidationError`, feed the error back and ask for a
    corrected object; validate again.
  - Note prefill caveat: several current models (incl. the book default) *reject* a trailing
    assistant prefill with a 400 — schema-constrained output has superseded prefill for guarantees.
  - 🎯 senior lens: validate at the boundary regardless of provider guarantees; this same pattern
    governs tool *inputs* in Ch 12 and the capstone's structured calls (Ch 15).
  - ⚠️ pitfall: trusting provider "JSON mode" to enforce *shape* — it only guarantees valid syntax.
- **Datasets/fixtures:** reuse `data/` triage tickets; one fixture crafted to trip validation.
- **APIs & cost:** mockable — `MOCK=1` returns a canned malformed-then-fixed pair to exercise the
  repair path deterministically; `MOCK=0` ≈ 1–2 short calls (plus one repair).
- **You'll be able to:** ship structured output with a real guarantee and a cheap repair fallback.

### 10-03 · `10-03-prompts-as-code-registry-and-evals.ipynb` — 🔧 Versioned prompts + an eval suite
- **Type:** walkthrough  *(this is the chapter's 🔧 Build: the `PromptRegistry`)*
- **Maps to:** book §10.5 (prompts as code: templating, versioning, testing), §10.6 (optimizing
  prompts automatically — surveyed, not built), §10.7 (anti-patterns & brittleness)
- **Objective:** manage prompts like code — templated files with name + version, version-stamped on
  every call — and gate changes on a small property-based eval suite.
- **Prereqs:** 10-01, 10-02.
- **Cell arc:**
  - 🧠 mental model: prompts change behavior exactly like code, so they need source control, review,
    versions, and tests; the highest-velocity change is the most common silent regression.
  - 🔧 build the `PromptRegistry` from the book: `prompts/<name>/<version>.txt` loaded via
    `string.Template.substitute(...)`; render `ticket_triage` `v3` with variables.
  - Stamp the prompt name+version onto a (mock) call's log record — pair with Ch 9's replay log so
    incidents are debuggable.
  - Build a tiny **eval**: a handful of representative inputs (incl. ugly ones) with *expected
    properties* (category correct, JSON validates, refusal triggers when it should); run it and score.
  - 🔮 *predict* whether deleting one "load-bearing" instruction changes the eval score — then delete
    it and let the suite answer ("could you delete any instruction and prove it mattered?").
  - Survey **automatic optimization** (§10.6) conceptually — DSPy / OPRO / GEPA / meta-prompting as a
    map of capabilities — and run a manual meta-prompt loop ("here's my prompt + 3 failing cases,
    propose a better one") as a no-framework optimizer.
  - 🎯 senior lens: make the safe path the easy path — prompts in one place, versions in logs, evals
    in CI — so the team can iterate fast *because* the net exists.
  - ⚠️ pitfall (anti-patterns): the kitchen-sink prompt, negative instructions doing positive work,
    cargo-culted magic phrases, conflicting instructions; and **optimizer overfit** — score on a
    held-out test split the optimizer never sees (Goodhart).
- **Datasets/fixtures:** `data/` — 2–3 versioned prompt template files + the small eval set from
  10-01 reused as the regression set.
- **APIs & cost:** mockable — registry + eval harness run fully offline against canned responses;
  the manual optimizer loop is mockable, `MOCK=0` adds a few generation calls.
- **You'll be able to:** stand up a versioned prompt registry with a CI-style eval gate — the
  starting point you copy from `templates/prompt-template/`.

## Feeds (cross-pillar)
- **Blueprint(s):** the structured-output validate-and-repair pattern (10-02) seeds the reliability
  work realized in [`blueprints/llm-gateway/`](../../blueprints/llm-gateway/) (Ch 11) and the
  eval discipline in [`blueprints/eval-harness/`](../../blueprints/eval-harness/) (Ch 22).
- **Template(s):** the `PromptRegistry` 🔧 Build graduates into
  [`templates/prompt-template/`](../../templates/prompt-template/) — versioned prompt files +
  the loader + the eval-stub the reader copies into a job. 10-03 ends by pointing here.
- **Capstone:** advances the capstone's `prompts/` registry and the structured-call wrapper used
  platform-wide (the book's §10.5 🔧 Build and the Ch 15 structured-output home).

## Dependencies
- Ch 9 (sampling/temperature for self-consistency; the replay-log habit) ·
  `learn/part-03-llm-substrate/09-*`. Ch 15 deepens structured-output reliability; Ch 22 turns the
  eval stub into full production machinery; Ch 41 adds runtime groundedness guardrails.

## Phase-2 definition of done
- [ ] All three notebooks run top-to-bottom in `MOCK=1` with no errors (techniques, repair loop,
      registry, and eval all exercised against canned responses).
- [ ] System-prompt-as-spec, the four technique families, the structured-output ladder, the
      validate-and-repair shape, and the registry code match the book's §10.
- [ ] Each notebook ends with recap + exercises; 10-03 ends pointing at `templates/prompt-template/`.
- [ ] Secrets from env only; self-consistency / live token costs documented; optimizer overfit
      guarded by a held-out split.
