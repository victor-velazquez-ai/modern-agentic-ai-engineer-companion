# `evals/` — eval harness + CI quality gate

> Capstone subsystem · Appendix C `evals/` · built in **Ch 22** · mirrors the
> [`eval-harness`](../../../blueprints/eval-harness/) blueprint.

The *evaluate* station of the quality flywheel. This is how the platform makes agent quality
**measurable instead of vibes**: versioned golden sets, a menu of graders (deterministic +
an LLM-judge), a runner that scores a candidate and breaks the result down per tag, and a
**CI gate** that fails the build when a gated metric regresses past a tolerance.

Runs **free and deterministic** by default (`COMPANION_MOCK=1`, the repo default): the
LLM-judge falls back to an offline mock verdict, so the suite — and CI — needs no API keys
and spends nothing. On the live path the judge routes through `llm/gateway.py`, the platform's
single door to model APIs; secrets come from the environment only.

## Layout

```
evals/
├── dataset.py     golden-set schema {id, input, expected, tags[], notes} + JSONL loader
├── graders.py     ExactMatch / Contains / RegexMatch / JSONSchemaMatch + rubric LLMJudge
├── run_evals.py   runner (score + per-tag aggregate) AND the CI gate (the entrypoint)
└── datasets/
    ├── agent_golden.jsonl   the committed golden set (appendable, diff-able, PR-reviewed)
    └── baseline.json        the accepted scores; the gate diffs against this
```

## Run it

```bash
# from capstone/agentic-platform/ — offline, no keys, no spend
# write/refresh the baseline (do this on purpose, when you intend to move quality):
python -m evals.run_evals agent_golden.jsonl --baseline evals/datasets/baseline.json --update

# gate against the committed baseline (exit 0 ok / 1 regression / 2 usage):
python -m evals.run_evals agent_golden.jsonl --baseline evals/datasets/baseline.json
```

A bare dataset name resolves under `evals/datasets/`. The CLI ships a thin *echo* candidate so
the gate wiring is exercisable before a real agent exists; real use imports the API:

```python
from evals import run_grouped, gate, load_baseline, load_jsonl
from evals.run_evals import default_graders, save_baseline

cases  = load_jsonl("agent_golden.jsonl")
report = run_grouped(my_agent, cases, default_graders(), default=ExactMatch())
result = gate(report, load_baseline("evals/datasets/baseline.json"), tolerance=0.02)
raise SystemExit(result.exit_code)
```

## The gate is the point

`gate(report, baseline, tolerance)` turns the eval set into a **merge gate**. It flags a
regression two ways, both on by default:

- **overall** — the mean dropped more than `tolerance` below baseline, and
- **per-tag** — *any* tag's mean dropped more than `tolerance` below its baseline.

The per-tag check catches the dangerous regression that barely moves the global average while
quietly tanking one segment — `must-refuse` falling from 1.0 to 0.4. That is why every case
carries at least one tag and why the safety segment is non-negotiable. `tolerance` exists
because the live LLM-judge has run-to-run noise; set it a few points above the judge's
observed variance so the gate flags real drops, not jitter.

## CI wiring

The `.github/workflows/` pipeline runs this as a required check on every PR:

```yaml
- name: Eval gate
  run: python -m evals.run_evals agent_golden.jsonl --baseline evals/datasets/baseline.json
```

A non-zero exit fails the job. Commit the baseline; bump it deliberately with `--update` when
you *intend* to change quality — never to silence a red gate you don't understand.

## Adapting it

1. Add a case to `agent_golden.jsonl` the day you find a bug (tag it with the ticket id).
2. Route tags to graders in `default_graders()` — start deterministic, add the judge only for
   the genuinely subjective slice.
3. Point the candidate at the platform's agent (`agents/`), refresh the baseline on purpose,
   and keep the gate green.
