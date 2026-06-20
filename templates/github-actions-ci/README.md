# Template — GitHub Actions CI (lint · type · test · eval-gate)

> **Copy me.** Drop the `.github/` folder into your repo, fill the `TODO` / `▢`
> markers, and CI runs on every push and pull request. Delete this notice once
> you've adapted it.

A drop-in CI pipeline for an agent project. It runs the usual code gates —
**lint → type-check → test** — and then the distinguishing piece: an
**eval-gate** that fails a PR when a prompt/model change *regresses agent
quality*, not just when a unit test breaks.

```text
github-actions-ci/
├── README.md                  # you are here
└── .github/
    └── workflows/
        ├── ci.yml             # lint (ruff) → type (mypy) → test (pytest); deps cached
        └── eval-gate.yml      # run the eval set in MOCK mode; non-zero score fails the PR
```

---

## Copy and use

```bash
# 1. Copy the workflows into your repo (merge with any existing .github/).
cp -r templates/github-actions-ci/.github ./

# 2. Find every placeholder and resolve it.
grep -rn "TODO\|▢" .github/

# 3. Push a branch and open a PR — the checks run automatically.
```

The workflows assume the [`agent-project-starter`](../agent-project-starter/PLAN.md)
layout: a **uv-managed** project (`uv.lock` present), a `src/` package, and
`ruff` / `mypy` / `pytest` configured. Each gate calls a `make` target first and
falls back to a direct `uv run …` command, so it works with **or** without a
`Makefile` — keep whichever you use.

---

## What each job does

### `ci.yml` — code gates (no secrets, no spend)

| Job | Runs | Why this order |
|-----|------|----------------|
| `lint` | `make lint` → `ruff check .` | Cheapest check first — fail fast on style/imports. |
| `type` | `make type` → `mypy src` | Catch type errors before running anything. |
| `test` | `make test` → `pytest -q` | Unit tests last of the fast checks. |

- **Dependency cache** is keyed on `uv.lock`, so installs are warm until your
  deps change.
- **Python-version matrix** is stubbed and commented in the `test` job
  (`▢ TODO`) — uncomment the `strategy.matrix` block to fan out across
  interpreters; the job already reads `${{ matrix.python-version }}`.
- `COMPANION_MOCK=1` is set workflow-wide so any stray SDK call in a test uses
  mock mode and never spends.

### `eval-gate.yml` — the quality gate (the differentiator)

| Job | When | Mode | Secrets |
|-----|------|------|---------|
| `eval-gate` | every push / PR | `COMPANION_MOCK=1` (free, deterministic) | **none** |
| `eval-nightly` | `▢` opt-in `schedule:` | `COMPANION_MOCK=0` (live) | from a **protected Environment** |

- `eval-gate` runs `python evals/run.py`, which scores your golden set and
  **exits non-zero below threshold** — that exit code blocks the merge. Because
  it runs in mock mode it is **free, deterministic, and fork-safe** (no secrets
  required to open a PR).
- `eval-nightly` is the **opt-in** live drift check. It is disabled until you
  (1) uncomment the `schedule:` trigger and (2) create the `eval-live`
  protected Environment with your API key. It is gated on the `schedule` event
  so it can **never** run from a fork PR.

This gate runs the `run.py` produced by the
[`eval-dataset-template`](../eval-dataset-template/PLAN.md) (copy it into
`evals/`). The harness it executes is the
[`eval-harness`](../../blueprints/eval-harness/PLAN.md) blueprint.

---

## Enabling the eval gate (step by step)

1. **Have an eval set.** Copy `eval-dataset-template/` into `evals/` so that
   `evals/run.py` and `evals/datasets/golden.jsonl` exist.
2. **Confirm it gates locally:** `COMPANION_MOCK=1 python evals/run.py` should
   print a pass/fail table and exit non-zero when the score is too low.
3. **Match the CLI.** Update the `Run eval set (gate)` step in `eval-gate.yml`
   to your harness's flags (e.g. `--dataset … --min-score 0.9`).
4. **(Optional) Turn on the nightly live check:**
   - Uncomment the `schedule:` trigger in `eval-gate.yml`.
   - In **Settings → Environments**, create an Environment named `eval-live`
     (add required reviewers / branch restrictions).
   - Add `ANTHROPIC_API_KEY` as a **secret on that Environment** (see
     [`.env.example`](.env.example) for the variable names — those values live
     in GitHub Secrets, never in the repo).

---

## Secrets policy

- **Never** put a key in a workflow file or anywhere in the repo. Live secrets
  are referenced as `${{ secrets.NAME }}` and supplied through **GitHub Secrets
  / Environments** only.
- PR and fork runs need **no secrets** because the gate runs in mock mode.
- `.env.example` documents the variables a maintainer registers as repo/
  Environment secrets — it is a checklist, not a place for real values.

---

## `permissions`

Both workflows set `permissions: contents: read` (least privilege). If you add
steps that comment on PRs, push, or publish, grant the *specific* extra scope on
that job only — do not widen the workflow default.

---

## Realizes (book chapters)

- **Ch 7 — Version Control, Testing & Quality:** CI for pytest and testing
  non-determinism (the chapter that produces this template).
- **Ch 22 — Evaluation & Quality:** the eval-as-a-gate idea, wired into CI.
- **Ch 36 — Infrastructure as Code:** CI/CD pipelines that build and deploy.
