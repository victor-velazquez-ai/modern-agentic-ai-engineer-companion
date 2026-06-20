# Blueprint — Eval Harness  (pattern)

> Realizes book Ch 22 (reused 41/43/45/47/48) · mirrors capstone `evals/` · Status: 📋 planned (Phase 1)

## What it is
A **quality gate for agents**: golden datasets (input → expected), a set of **graders**
(deterministic checks like exact/regex/JSON-schema, plus an **LLM-judge** for open-ended
quality), a runner that scores a candidate against the golden set and compares to a baseline, and
a **CI gate** that fails the build when a score regresses past a threshold. The standalone "how a
senior makes agent quality measurable instead of vibes."

## Why a blueprint (not a notebook)
- The Ch 22 notebook builds a teaching harness; the *real* one — dataset format, pluggable
  graders, baseline diffing, a CI entrypoint with a non-zero exit on regression — is tooling, not
  cells.
- It is **reused across five chapters** (41 injection red-teaming, 43 reference-arch eval, 45
  multimodal, 47 computer-use, 48 customization) and by most solution blueprints, so it must be an
  importable, stable package.
- The CI-gate behavior (exit code, threshold, baseline file) is exactly what you assert in tests.

## Planned structure
```text
eval-harness/
├── README.md                  # golden sets, grader menu, LLM-judge caveats, CI gate, adapt
├── pyproject.toml
├── src/eval_harness/
│   ├── __init__.py
│   ├── dataset.py             #   golden-set schema + loader (case: input, expected, tags)
│   ├── graders/
│   │   ├── base.py            #   Grader Protocol (score in [0,1] + rationale)
│   │   ├── deterministic.py   #   exact / regex / JSON-schema / contains
│   │   └── llm_judge.py       #   rubric-based LLM judge (mock judge default)
│   ├── runner.py              #   run candidate over the set, aggregate scores
│   └── gate.py                #   compare to baseline; non-zero exit on regression (CI)
├── tests/
│   ├── test_graders.py        #   each grader scores known pass/fail cases
│   ├── test_runner.py         #   aggregate + per-tag breakdown
│   └── test_gate.py           #   regression past threshold → failure exit code
├── datasets/
│   └── example.jsonl          #   tiny committed golden set for the demo
└── demo.py                    # runnable: score a mock agent, print report, run the gate, MOCK
```

## Composes / depends on
- **`llm-gateway`** — the LLM-judge calls models through it (mock judge keeps the harness
  deterministic and free standalone).
- **Foundational for quality** — other blueprints and chapters *import this*; it depends on none
  of them.

## Maps to the book
- **Ch 22 — Evaluation & Quality:** golden sets, graders, LLM-as-judge, the CI quality gate.
  Makes §22's 🔧 Build sections real.
- **Reused by:** Ch 41 (injection red-teaming as an eval), Ch 43 (reference-arch quality bars),
  Ch 45 (multimodal extraction accuracy), Ch 47 (computer-use task success), Ch 48 (pre/post
  customization comparison).
- **`learn/` walkthrough:** [`../../learn/part-06-evaluation-observability-quality/22-evaluation-and-quality/`](../../learn/part-06-evaluation-observability-quality/22-evaluation-and-quality/)
  builds the teaching harness + CI gate and **ends by pointing here** (its plan already links this
  slug).

## Maps to the capstone
Standalone version of capstone **`evals/`** — `datasets/` + `run_evals.py` (Ch 22), the same
harness the capstone wires into CI as a merge gate.

## Phase-2 definition of done
- [ ] `pytest tests/` passes; graders, runner aggregation, and gate exit-code all covered.
- [ ] `python demo.py` scores a mock agent and runs the gate in **`MOCK=1`** (no API spend).
- [ ] README explains trade-offs: deterministic-vs-judge graders, LLM-judge bias/variance and how
      to bound it, threshold/baseline choice, and reading per-tag breakdowns.
- [ ] Cross-links (`llm-gateway`, the Ch 22 walkthrough, capstone `evals/`) resolve.
