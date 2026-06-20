# 🛠️ Template — Eval Dataset (tagged golden set + scorer)

> Realizes book **Ch 22 — Evaluation & Quality**. Copy this folder into your repo's
> `evals/` and start measuring an LLM feature instead of vibe-checking it.

A minimal, copy-me scaffold for the **dataset + scorer** half of an eval harness:

- a documented, tagged **JSONL schema** ([`SCHEMA.md`](SCHEMA.md)),
- a small **seed golden set** and a separate **adversarial set**,
- a **pluggable scorer** with deterministic and LLM-judge stubs ([`scorer.py`](scorer.py)),
- a **runner** that prints a pass/fail table and exits non-zero on failure ([`run.py`](run.py)) —
  a drop-in CI quality gate,
- a **CI guard test** that validates every row against the schema ([`tests/test_schema.py`](tests/test_schema.py)).

There is **no business logic** here — only sane defaults and clearly marked `TODO`s. Fill the
TODOs and it is valid and buildable.

---

## When to copy it

You are about to ship (or already shipped) an LLM feature and want to *measure* it — to catch
regressions when you change a prompt or model — instead of eyeballing a few outputs. Copy this
into `evals/` and add a case the day you find a bug.

---

## Copy & use (5 steps)

1. **Copy** this folder into your project:

   ```bash
   cp -r templates/eval-dataset-template my-project/evals
   cd my-project/evals
   ```

2. **Wire your feature in.** Open [`run.py`](run.py) and replace the `target()` stub (an echo)
   with a call to your agent / prompt / pipeline. That is the only function you *must* edit.

3. **Pick your checks.** In [`scorer.py`](scorer.py), the `score_case()` dispatcher routes each
   case to a scorer (`exact` / `contains` / `regex` / `llm_judge`). Adjust the routing and the
   `TODO` blocks (normalization, refusal detection, judge rubric) for your feature.

4. **Replace the seed cases.** The 10 rows in [`datasets/golden.jsonl`](datasets/golden.jsonl)
   and the 5 in [`datasets/adversarial.jsonl`](datasets/adversarial.jsonl) are placeholders.
   Swap in cases from *your* product. Keep adding cases — especially the day you find a bug
   (tag it `regression` + the ticket number).

5. **Run it:**

   ```bash
   python run.py                       # scores datasets/golden.jsonl
   python run.py datasets/golden.jsonl datasets/adversarial.jsonl
   pytest tests/                       # schema guard: every row is well-formed
   ```

`run.py` prints a per-case table, a per-tag breakdown, and a summary line, then **exits non-zero
if the pass rate is below the threshold** — that exit code is what CI gates on.

---

## How it runs free (mock mode)

The LLM-judge scorer is gated by the **`COMPANION_MOCK`** environment variable (the repo-wide
convention — see the repo-root [`.env.example`](../../.env.example)):

| `COMPANION_MOCK` | Behavior |
|------------------|----------|
| `1` (default) | Canned, offline, deterministic verdicts. **No API key, no spend.** CI runs here. |
| `0`           | Real model call. Requires a key in `.env` (e.g. `ANTHROPIC_API_KEY`) and costs tokens. |

So `python run.py` and `pytest tests/` work out of the box with **no secrets**. Copy the
repo-root `.env.example` to `.env` and set `COMPANION_MOCK=0` (plus a key) only when you want to
grade against live models. `.env` is git-ignored; **datasets are committed, so they must never
contain keys or PII** — `tests/test_schema.py` includes a tripwire for common secret formats.

> `make test` / `make eval` (mentioned in the book): if your project has a `Makefile`, add
> `pytest tests/` and `python evals/run.py` as targets. This template intentionally ships
> without one so it drops cleanly into a repo that already has its own.

---

## File map

```text
eval-dataset-template/
├── README.md                  # you are here — schema, tagging, "copy me" usage
├── SCHEMA.md                  # the row contract: fields, types, tag convention
├── datasets/
│   ├── golden.jsonl           # ~10 seed cases  {id, input, expected, tags[], notes}
│   └── adversarial.jsonl      # edge / should-refuse cases (grow these)
├── scorer.py                  # exact / contains / regex / LLM-judge stubs → Score
├── run.py                     # load → target() → score → table; non-zero exit on fail
└── tests/
    └── test_schema.py         # CI guard: every row parses, has fields + ≥1 tag
```

---

## How it fits the companion repo

- **Blueprint** — the hardened version of this is
  [`../../blueprints/eval-harness/`](../../blueprints/eval-harness/PLAN.md) (pluggable graders,
  baseline diffing, LLM-judge). This template is the *dataset + scorer* starter that feeds it.
- **CI** — [`../github-actions-ci/`](../github-actions-ci/PLAN.md)'s **eval-gate** job runs
  `run.py` (in `COMPANION_MOCK=1`); its exit code blocks the PR.
- **Capstone** — mirrors the capstone's `evals/datasets/` layout.

See [`PLAN.md`](PLAN.md) for the full rationale and the Phase-2 definition of done.

---

*Part of the [Modern Agentic AI Engineer](../../README.md) companion. MIT-licensed — copy it
into your work.*
