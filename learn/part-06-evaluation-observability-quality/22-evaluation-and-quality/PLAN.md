# Ch 22 — Evaluation & Quality

> Companion plan · Part VI · book file `chapters/22-evaluation-and-quality.typ`
> Status: 📋 planned (Phase 1)

## Role in the companion
This is the craft chapter of Part VI — "the single most differentiating skill in applied AI" —
and it earns three notebooks. The reader builds an oracle from the cheapest reliable scorer up
(code → similarity → LLM-judge → human), grades *behavior over time* (RAG decomposition,
agent trajectories, tool-call argument correctness), and then does the chapter's 🔧 **Build**:
a real `evals/` harness with a golden set, composite scorers, a calibrated judge, statistics,
and a CI gate that blocks any PR that regresses quality. The notebooks make every scorer
runnable and mockable; the judge is mockable so the whole thing runs free in CI. This is the
*evaluate* station of the flywheel, made into the capstone's referee.

## Planned notebooks

### 22-01 · `22-01-offline-evals-and-judges.ipynb` — Golden sets, scorers, and an honest LLM judge
- **Type:** walkthrough
- **Maps to:** §22.1 (eval as an executable judgment), §22.2 (offline evals: golden sets →
  code graders first → LLM-as-judge done responsibly → choosing & composing scorers, incl. the
  scorer taxonomy and pointwise/pairwise, reference-based/free), §22.8 (statistics: Wilson
  interval, κ inter-annotator agreement, data-leakage holdout)
- **Objective:** turn "is the agent good?" into a composite pass/fail verdict, reaching for the
  cheapest scorer that *reliably* captures each criterion — and report it with a confidence
  interval instead of a bare percentage.
- **Prereqs:** 21-01 (layered "good"); Ch 11 (model APIs) for the judge call shape.
- **Cell arc:**
  - 🧠 mental model: an eval is a unit test whose assertion is a judgment call; every technique
    is a strategy for building the *oracle* — pick the cheapest reliable one.
  - Build a tiny tagged **golden set** as JSONL (the book's `billing-007` shape:
    `input`, `expected_behavior`, `must_call_tools`, `must_not`, `tags`) — 30–100 real/hard
    cases in spirit, ~15 committed here; tags enable slice scoring.
  - **Code graders first** (§22.2): exact/normalized match, schema/JSON assertion,
    regex required/forbidden content, execution-based check, and trace-based "called X before
    answering." 🔮 *predict* which criteria code *can't* judge.
  - **LLM-as-judge, responsibly:** a real pass/fail-per-criterion rubric (grounded / resolves /
    safe_commitments), JSON output, judge call gated by `MOCK` (canned verdicts by default).
  - ⚠️ pitfall: scalar "rate 1–10" judges → noise centered on 7; verbosity/position/
    self-preference bias; **never let the system grade itself** and never tune against an
    uncalibrated judge (Goodhart). Show a biased prompt vs the rubric prompt side by side.
  - **Calibrate the judge:** hand-label ~10 cases, compute judge–human agreement and
    human–human **Cohen's κ**; show that κ < 0.6 means the *rubric* is ambiguous, not the
    annotators — fix the rubric before trusting the judge.
  - **Compose scorers** (§22.2 "choosing and composing"): per-criterion pass/fail aggregated,
    **safety criteria all-must-pass**; build the `composite_scorer` shape from the book.
    Note pointwise (gate a suite) vs pairwise (A/B "which is better?"), reference-based vs
    reference-free (most agentic criteria are reference-free).
  - **Are your numbers real?** wrap the pass-rate in a **Wilson interval**; show "84% ± 10%" on
    50 cases — a two-point gain inside overlapping intervals is noise, don't ship on it.
  - ⚠️ pitfall: **data leakage** — eval cases must stay disjoint from few-shot/retrieved/
    fine-tune data; partition harvested data into an eval holdout vs a few-shot/train pool.
  - 🎯 senior lens: the eval suite is the compounding moat — model swaps become a one-afternoon,
    slice-by-slice diff instead of a leap of faith.
- **Datasets/fixtures:** `data/golden-support.jsonl` (~15 tagged cases) + a small set of canned
  agent answers and canned judge verdicts so scorers and calibration run deterministically.
- **APIs & cost:** mockable — `MOCK=1` returns canned judge JSON (judges can be mocked); live ≈
  one judge call per case (a few hundred tokens each), only on `MOCK=0`.
- **You'll be able to:** assemble a tagged golden set, write code graders and a calibrated,
  responsibly-prompted judge, compose them into a safety-gated verdict, and report it with a
  confidence interval.

### 22-02 · `22-02-rag-agent-and-trajectory-evals.ipynb` — Grading behavior, not just the final answer
- **Type:** walkthrough
- **Maps to:** §22.3 (online evals: canaries, A/B with pre-registered metrics, implicit
  feedback), §22.4 (harvesting evals from production: signals, random-baseline + targeted
  mining, trace→versioned dataset, PII redaction), §22.5 (evaluating RAG / agents /
  trajectories + tool-call accuracy), §22.6 (standardized benchmarks, read critically),
  §22.7 (user-simulator for multi-turn agents)
- **Objective:** decompose a pipeline so an eval tells you *where* it broke — retrieval vs
  generation for RAG, and the *trajectory* (tool selection, argument values, efficiency,
  recovery, path-safety) for agents — and evaluate a multi-turn dialogue with a user-simulator.
- **Prereqs:** 22-01; concepts from Ch 13 (RAG retrieval metrics) and Ch 16–17 (trajectories).
- **Cell arc:**
  - 🧠 mental model: grading only the shipped unit hides *where* the factory failed —
    decompose.
  - **RAG split:** retrieval graded classically (recall/precision@k, MRR vs labeled relevant
    chunks) + generation graded by **faithfulness** and answer-relevance (rubric judge). 🔮
    *predict* whether a wrong answer is a retrieval miss or a generation miss, then read the
    decomposed scores and see which fork to fix.
  - **Trajectory evals:** score the path — tool selection, **efficiency** (steps/tokens/cost vs
    a budget), **recovery** after a failed tool call, and **path-safety** (no forbidden tools,
    asked for approval where policy demands).
  - **Tool-call accuracy as its own scorer** (the book's `tool_call_score`): right tool, valid
    args, **right argument *values*** (`month="June"` when the user said May parses but fails),
    no hallucinated tool/param, not over-calling, no missing required call.
  - ⚠️ pitfall: a schema-valid call can still be wrong — score argument *values* against the
    case's expected call, not just the tool name.
  - **User-simulator (§22.7):** the τ-bench pattern made local — persona + goal + constraints
    drive a multi-turn loop; grade the whole trajectory **and the final side effects** (was the
    refund actually issued, only within policy?). Build the book's `simulate` loop shape.
  - ⚠️ pitfall: a strong model **breaks character** and solves the task for your agent →
    manufactured success; pin it with a strict system prompt, use a *different, cheaper* model
    than the agent, and validate simulated transcripts against real ones.
  - **Harvesting (§22.4):** map production signals → eval data (thumbs, rephrase/retry, **human
    edit of a draft = free gold label**, escalation, low-confidence); keep a **random baseline**
    sample plus **targeted, slice-stratified mining**; the weekly triage→annotate→curate ritual.
  - ⚠️ pitfall: **anonymize/redact PII before anything lands in a dataset** — raw production
    traffic is radioactive until scrubbed (governance, Ch 41).
  - **Benchmarks (§22.6):** read τ-bench / SWE-bench / WebArena·GAIA / BFCL / AgentBench as
    *"what oracle does it use"* — borrow the user-simulator and execution-grading designs, not
    the score; mind contamination + distribution mismatch.
  - 🎯 senior lens: triage by *distribution, not drama* — fix the biggest failure cluster, file
    the dramatic one-off as an eval case.
- **Datasets/fixtures:** `data/rag-cases.jsonl` (questions + labeled relevant chunk ids + tiny
  context corpus) and `data/trajectory-cases.jsonl` (expected tool calls with argument values);
  a mock retriever, mock agent traces, and a mock persona-simulator (all seeded/canned).
- **APIs & cost:** mockable — retriever, agent, judge, and simulator all canned under `MOCK=1`;
  live ≈ a handful of judge + simulator turns per case on `MOCK=0` (use a cheaper model for the
  simulator).
- **You'll be able to:** decompose RAG and agent runs into where-it-broke scores, grade
  tool-call argument correctness, run a persona-driven multi-turn eval graded on final side
  effects, and convert a production signal into a (redacted) golden case.

### 22-03 · `22-03-eval-harness-and-ci-gate.ipynb` — 🔧 Build the capstone's eval harness + CI gate
- **Type:** walkthrough  *(this is the chapter's 🔧 Build, §22.10)*
- **Maps to:** §22.10 (🔧 Build: an eval harness and CI gate for the capstone), reusing the
  scorers from §22.2 and the statistics/thresholds from §22.8; §22.9 (tooling landscape —
  when to graduate from JSONL+pytest to a platform)
- **Objective:** wire the pieces into the capstone's `evals/` package — golden set + graders +
  a concurrent harness that reports per-slice scores + a pytest gate with slice tolerances and
  a perfect-or-blocked safety slice + the GitHub Actions workflow — so no behavior-changing PR
  ships unmeasured.
- **Prereqs:** 22-01 (scorers + judge), 22-02 (trajectory/tool-call scorers); Ch 7 (pytest/CI).
- **Cell arc:**
  - 🧠 mental model: the eval suite is *just another test target* — `pytest evals/` — gated in
    CI like any other check; the asset is the data, not the architecture.
  - Lay out the book's `capstone/evals/` structure: `golden/support.jsonl`, `graders.py`,
    `run_evals.py`, `baselines.json`, `.github/workflows/evals.yml`.
  - **Harness** (`run_evals.py`): run the (mock) agent over every case **concurrently**
    (`asyncio.gather`), apply code checks `|=` judge, aggregate **per tag/slice**, and write
    `eval_report.json` with overall + slice pass-rates and per-row cost/steps.
  - 🔮 *predict* which slice will fail the gate after a deliberately planted prompt regression,
    then run and read the slice diff.
  - **The gate** (`test_gate.py`): `test_overall_quality` (≥ baseline − 1pt),
    `test_slice_quality` (no slice drops > `SLICE_TOLERANCE` = 2pts), and
    `test_safety_slice_is_perfect` (safety == 100%). Show a red run, fix, then green.
  - **The baseline ratchet:** raising quality means updating `baselines.json` *in the same PR* —
    a deliberate, reviewed ratchet, not an automatic one.
  - **CI** (`evals.yml`): trigger only on behavior-relevant paths (`agents/**`, `prompts/**`,
    `tools/**`, `evals/**`); upload the report artifact `if: always()`; key from
    `secrets.ANTHROPIC_API_KEY` (mockable in the notebook).
  - ⚠️ pitfall: non-determinism — pin model+params in CI, score pass-rates over multiple shots
    for flaky cases, and set gates as **thresholds with tolerances**, not exact-match-or-fail;
    a failing eval is sometimes the eval's bug.
  - 🎯 senior lens / 📋: "how fast can you *safely* change models?" is a direct measure of eval
    maturity; forward pointers — Ch 23 adds *instrument*/*observe*, Ch 31 moves big suites onto
    Celery off the CI clock.
  - **Ends pointing at the blueprint:** you built the teaching harness; the production version
    lives in [`blueprints/eval-harness/`](../../../blueprints/eval-harness/) and ships in
    `capstone/evals/`. Note when to graduate to a platform (§22.9: Langfuse / LangSmith /
    Braintrust / Ragas / promptfoo / OpenAI Evals).
- **Datasets/fixtures:** `data/support.jsonl` (the capstone golden slice, tagged incl.
  `safety`) + `data/baselines.json`; a mock `SupportAgent.for_eval()` with a pinned canned
  policy so the gate is deterministic; the `evals.yml` shown as a committed text artifact.
- **APIs & cost:** mockable — `MOCK=1` runs the whole gate with a canned agent + canned judge
  (free, deterministic, CI-safe); live ≈ one agent run + one judge call per case on `MOCK=0`.
- **You'll be able to:** stand up a slice-aware eval harness with a CI gate and a reviewed
  baseline ratchet that turns "I think this prompt is better" into a green/red check on the PR —
  the capstone's quality referee.

## Feeds (cross-pillar)
- **Blueprint(s):** [`blueprints/eval-harness/`](../../../blueprints/eval-harness/) — the
  production-grade harness (golden sets, composite scorers, calibrated judge, statistics, CI
  gate) that 22-03 builds the toy version of; every notebook ends pointing here.
- **Template(s):** [`templates/eval-dataset-template/`](../../../templates/eval-dataset-template/)
  — the tagged golden-set / JSONL case schema (the `billing-007` shape with `tags`,
  `must_call_tools`, `must_not`, and an eval-holdout vs few-shot/train pool partition) seeded by
  22-01/22-02.
- **Capstone:** advances `capstone/evals/` (`golden/`, `graders.py`, `run_evals.py`,
  `baselines.json`, `.github/workflows/evals.yml`); checkpoint `checkpoints/ch22-eval-harness`.

## Dependencies
- Ch 21 (layered "good", the flywheel's *evaluate* station) · Ch 11 (model APIs for the judge)
  · Ch 13 (RAG retrieval metrics) · Ch 16–17 (agent trajectories) · Ch 7 (pytest/CI for the
  gate). Ch 23 then supplies the *instrument*/*observe* stations that feed cases back in; Ch 31
  scales the harness onto Celery.

## Phase-2 definition of done
- [ ] All three notebooks run top-to-bottom in `MOCK=1` with no errors and no API spend (judge,
      retriever, agent, and simulator all canned).
- [ ] Golden-set shape, the `composite_scorer`/`tool_call_score`/`simulate` shapes, the Wilson
      interval, and the `run_evals.py` + `test_gate.py` + `evals.yml` structures match the
      book's §22 code exactly (incl. safety all-must-pass and slice tolerances).
- [ ] Judge is calibrated against human labels (κ shown) and never grades itself; data-leakage
      holdout enforced; PII-redaction step present in the harvesting cells.
- [ ] Each notebook ends with recap + 2–4 change-and-predict exercises and a link to
      `blueprints/eval-harness/`, `templates/eval-dataset-template/`, and `capstone/evals/`.
- [ ] Secrets read from env only; canned mock judge/agent responses are realistic.
