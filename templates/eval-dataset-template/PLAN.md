# Template — Eval Dataset
> Realizes book Ch 22 · Status: 📋 planned (Phase 1)

## What it scaffolds
A golden-set layout for evaluating an LLM feature: a documented **tagged JSONL schema**, a
small seed dataset, a scorer stub you fill with your checks, and the folder structure a real
eval set grows into — the dataset side of an eval harness.

## When to copy it
You're about to ship (or already shipped) an LLM feature and want to *measure* it — catch
regressions on prompt/model changes — instead of eyeballing a few outputs. Copy this into
`evals/` and start adding cases the day you find a bug.

## Planned file tree
```text
eval-dataset-template/
├── README.md                  # the schema, tagging convention, "copy me" usage
├── SCHEMA.md                  # one row's fields, types, and what each tag means
├── datasets/
│   ├── golden.jsonl           # ~10 seed cases: {id, input, expected, tags[], notes}
│   └── adversarial.jsonl      # a few edge/should-refuse cases (▢ grow these)
├── scorer.py                  # # TODO: exact / contains / regex / LLM-judge stubs → score
├── run.py                     # load dataset → run target() → score → print pass/fail table
└── tests/
    └── test_schema.py         # every row parses, has required fields + ≥1 tag (CI guard)
```

## Defaults baked in
- **One row per case, JSONL:** `{id, input, expected, tags[], notes}` — appendable, diff-able,
  reviewable in a PR; `SCHEMA.md` is the contract and `test_schema.py` enforces it.
- **Tags are first-class:** every case carries tags (capability, difficulty, `must-refuse`,
  regression-ticket) so you can slice scores by segment, not just a single accuracy number.
- **Scorer is pluggable:** stubs for deterministic checks (exact/contains/regex) **and** an
  LLM-judge path — the judge call is gated by `COMPANION_MOCK` so the suite runs free offline.
- **Separate adversarial set:** edge/should-refuse cases kept apart so safety regressions are
  visible (mirrors the blueprints' "permission-probe" / refusal cases).
- **`run.py` prints a table, exits non-zero on fail:** drop-in for a CI quality gate.
- **No secrets:** datasets hold no keys/PII; judge key (if used) comes from `.env` only.

## Maps to the book
- **Ch 22 — Evaluation & Quality:** the golden-set + grader discipline the chapter builds
  (🔧 eval harness + CI gate); this template is the *dataset + scorer* half.
- **Blueprint:** consumed by [`../../blueprints/eval-harness/`](../../blueprints/eval-harness/PLAN.md)
  (graders, LLM-judge, gate). **Template:** `run.py`'s non-zero exit is what
  [`../github-actions-ci/`](../github-actions-ci/PLAN.md) calls as the **eval-gate** step.
  **Capstone:** mirrors `evals/datasets/` in
  [`../../../chapters/92-appendix-capstone.typ`](../../../chapters/92-appendix-capstone.typ).

## Phase-2 definition of done
- [ ] `python run.py` scores `datasets/golden.jsonl` against a target stub and prints pass/fail.
- [ ] `make test` passes: every JSONL row validates against `SCHEMA.md` and has ≥1 tag.
- [ ] LLM-judge path runs in `MOCK=1` with a canned verdict (no API spend); `run.py` exits non-zero on failure.
- [ ] No PII/secrets in any dataset; `scorer.py` checks are clearly marked `TODO`.
