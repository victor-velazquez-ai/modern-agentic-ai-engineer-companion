# Eval Harness — a quality gate for agents

> Pattern blueprint · realizes book **Ch 22 — Evaluation & Quality** (reused by Ch 41, 43, 45, 47, 48) · mirrors capstone [`evals/`](../../capstone/)

This is how a senior makes agent quality **measurable instead of vibes**: golden datasets
(input → expected), a menu of **graders** (deterministic checks plus an **LLM-judge**), a
**runner** that scores a candidate over the set and breaks the result down per tag, and a
**CI gate** that fails the build when a score regresses past a threshold.

It runs **free and deterministic by default** (`COMPANION_MOCK=1`): the LLM-judge uses an
offline mock verdict, so the whole harness — and everything that imports it — works with **no
API keys and no spend**. It depends on no other blueprint; on the live path the judge routes
through [`llm-gateway`](../llm-gateway/).

---

## Quick start

```bash
# from this folder — no install needed, demo shims `src/` onto the path
python demo.py
```

The demo loads `datasets/example.jsonl`, scores a good mock agent to set a baseline, then
re-runs a deliberately **regressed** agent and shows the gate failing with a non-zero exit
code — exactly what CI keys off. It never touches the network.

Run the tests:

```bash
pip install -e ".[dev]"   # or just: pip install pytest
pytest tests/
```

Use it as a CLI gate (the echo candidate is a thin demo wiring — real use imports the API):

```bash
python -m eval_harness.gate datasets/example.jsonl --baseline baseline.json --update   # write baseline
python -m eval_harness.gate datasets/example.jsonl --baseline baseline.json             # gate; exit 1 on regression
```

---

## The pieces

```
src/eval_harness/
├── dataset.py            golden-set schema {id, input, expected, tags[], notes} + JSONL loader
├── graders/
│   ├── base.py           Grader Protocol — grade(expected, actual) -> GradeResult(score∈[0,1], rationale)
│   ├── deterministic.py  exact / contains / regex / JSON-schema
│   └── llm_judge.py       rubric LLM-judge (offline mock judge by default)
├── runner.py             run a candidate over the set; aggregate + per-tag breakdown
└── gate.py               compare to baseline; non-zero exit on regression (the CI entrypoint)
```

### The dataset

One case per line of JSONL — appendable, diff-able, reviewable in a PR:

```json
{"id": "capital-france", "input": "What is the capital of France?", "expected": "Paris", "tags": ["exact", "geography"], "notes": "Closed-form factual answer."}
```

`tags` are **first-class and required**: every case carries at least one so you can slice
scores by segment (capability, difficulty, `must-refuse`, a regression-ticket id) instead of
trusting a single accuracy number. A duplicate `id` is an error — silently overwriting cases
is how a golden set rots.

### The grader menu

| Grader | Use it when | Scores |
|---|---|---|
| `ExactMatch` | closed-form answer (a label, a slug, a number) | 1.0 / 0.0 |
| `Contains` | the answer must mention specific things | fraction of needles found |
| `RegexMatch` | output must match a format | 1.0 / 0.0 |
| `JSONSchemaMatch` | a tool returned JSON of the right shape | 1.0 / 0.0 (dependency-free validator) |
| `LLMJudge` | open-ended quality (faithfulness, an appropriate refusal) | normalized rubric score |

A grader is anything matching the tiny `Grader` Protocol — a class, a closure, a lambda — so
custom checks plug in with no base class to inherit. Graders **never raise** on a malformed
candidate output: a bad answer is a score of 0 with a rationale, so one broken case can't
crash a run.

### The runner

`run(candidate, cases, grader)` feeds each case's `input` to your candidate (an agent, a
prompt, a stub — just `input -> output`), grades the output, and returns a `Report` with the
overall mean **and** `by_tag()` / `tag_scores()`. `run_grouped(...)` routes each case to a
grader by its first matching tag, so deterministic checks and the LLM-judge coexist in one
run. A candidate that raises on one input scores that case 0 (with the exception in the
rationale) rather than aborting the suite.

### The gate

`gate(report, baseline, tolerance=...)` is what turns an eval set into a **merge gate**.
Commit a `baseline.json` (the scores you accept today). On every PR, CI re-runs the suite and
calls the gate; if the overall mean **or any per-tag score** drops more than `tolerance`
below baseline, it fails with exit code `1` and a readable diff. The exit-code contract is
`0` ok / `1` regression / `2` usage error.

---

## Trade-offs a senior reasons about

**Deterministic graders vs. the LLM-judge.** Reach for deterministic checks first. They are
free, fast, and never drift — most quality bars (valid JSON, the right entity named, a
matched format) are checkable without a model in the loop, and a green deterministic check
*stays* green for the same output forever. Use the judge **only** for the open-ended slice no
string check captures (is this summary faithful? is this refusal appropriate?). A good set is
mostly deterministic with a thin judge layer on the genuinely subjective cases.

**LLM-judge bias and variance — and how to bound it.** A model judge is powerful but
**biased and noisy**: position bias (it favors the first answer shown), verbosity bias (longer
looks better), self-preference (a model rates its own family higher), and plain run-to-run
variance. Bound it deliberately:

- **Pin the judge** (a fixed model at `temperature=0`) and keep it *different* from the model
  under test to blunt self-preference.
- **Anchor every rubric level** with a concrete description so a "4" means the same thing
  across cases and across weeks.
- **Average several votes** (`samples=N`) and, when comparing two answers, **randomize their
  position** to cancel position bias.
- **Validate the judge against humans** on a labeled slice before you trust it — and set the
  gate `tolerance` a few points above the judge's observed variance so it flags real drops,
  not jitter. The mock judge here is deterministic, so it has zero variance — but it is a
  stand-in, not a substitute for that human calibration on the live path.

**Threshold and baseline choice.** Two knobs: the per-case **pass `threshold`** (the bar a
single score must clear to count as a pass) and the gate **`tolerance`** (how far the
*aggregate* may slip below baseline before the build fails). Set the threshold from what
"acceptable" means for that grader; set the tolerance from measured noise. Refresh the
baseline deliberately (`--update`) when you *intend* to move quality — never to silence a red
gate you don't understand. A baseline you bump without reading is a gate that no longer gates.

**Read the per-tag breakdown, not just the headline.** The dangerous regression is the one
that barely moves the global average while quietly tanking one segment — `must-refuse` drops
from 1.0 to 0.4 while overall slips two points. That is why the gate checks **every tag**, not
just the mean, and why adding a `must-refuse`/safety segment is non-negotiable. When the gate
fails, the per-tag diff tells you *which capability* broke.

---

## Live (`MOCK=0`) path

Set `COMPANION_MOCK=0` to use a real judge. Build it with `LLMJudge.from_gateway(...)`, which
routes model calls through the [`llm-gateway`](../llm-gateway/) blueprint — the single door
that owns routing, caching, cost metering, and guards. The import is lazy, so the harness
still imports with only the stdlib + `requirements.txt` installed, and the gateway is needed
only when you actually opt into spend. Document the approximate token cost wherever you enable
it. Keys come from the environment (`.env`, git-ignored) only — never commit a secret, and no
PII lives in any dataset.

---

## How to adapt it

1. Copy `datasets/example.jsonl` to your own golden set; add a case the day you find a bug.
2. Pick graders per tag (start deterministic; add a judge only for the subjective slice).
3. `run_grouped(your_agent, cases, graders, default=...)`, then `save_baseline(report, ...)`.
4. Wire `python -m eval_harness.gate <dataset> --baseline baseline.json` into CI as a required
   check. Commit the baseline; bump it on purpose.

---

## Maps to the book & repo

- **Ch 22 — Evaluation & Quality:** golden sets, graders, LLM-as-judge, the CI quality gate.
  This makes §22's 🔧 Build sections real.
- **Reused by:** Ch 41 (injection red-teaming as an eval), Ch 43 (reference-arch quality
  bars), Ch 45 (multimodal extraction accuracy), Ch 47 (computer-use task success), Ch 48
  (pre/post-customization comparison).
- **Composes:** [`llm-gateway`](../llm-gateway/) (live judge only). **Dataset side:**
  [`templates/eval-dataset-template`](../../templates/eval-dataset-template/).
- **Walkthrough:** [`learn/part-06-evaluation-observability-quality/22-evaluation-and-quality/`](../../learn/part-06-evaluation-observability-quality/22-evaluation-and-quality/)
  builds the teaching harness and ends by pointing here.
- **Capstone:** standalone version of capstone `evals/` (`datasets/` + `run_evals.py`), the
  same harness wired into CI as a merge gate.
