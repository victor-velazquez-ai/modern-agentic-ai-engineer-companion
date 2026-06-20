# Template — GitHub Actions CI
> Realizes book Ch 7, 22, 36 · Status: 📋 planned (Phase 1)

## What it scaffolds
A drop-in GitHub Actions CI workflow for an agent project: lint → type-check → test →
**eval-gate**, with caching and a matrix-ready job — the distinguishing piece being that CI
also blocks on *agent-quality* regressions, not just unit tests.

## When to copy it
You have an agent repo and want CI that fails a PR when prompt/model changes regress quality
(or when lint/types/tests break). Copy `.github/` into your repo and the checks run on every
push and PR.

## Planned file tree
```text
github-actions-ci/
├── README.md                  # what each job does + how to enable the eval gate; "copy me"
└── .github/
    └── workflows/
        ├── ci.yml             # lint · type · test (matrix-ready); deps cached
        └── eval-gate.yml      # run the eval set in MOCK; non-zero score fails the PR
```

`ci.yml` job shape:
```yaml
# on: [push, pull_request]
# jobs: lint (ruff) → type (mypy) → test (pytest); uv + cache; ▢ python-version matrix
```
`eval-gate.yml` job shape:
```yaml
# runs: python evals/run.py  → COMPANION_MOCK=1 (no spend); exit code gates the PR
# ▢ nightly schedule with MOCK=0 behind a guarded environment to catch SDK drift
```

## Defaults baked in
- **Four stages, the right order:** lint (`ruff`) → type (`mypy`) → test (`pytest`) →
  eval-gate — fast checks first, the eval run last.
- **Eval-gate is the differentiator:** runs the golden set in `COMPANION_MOCK=1` so PR CI is
  **free and deterministic**; the score's non-zero exit blocks merge. A *guarded* nightly job
  can run `MOCK=0` against live APIs to catch SDK drift (opt-in, no secrets in PR runs).
- **Secrets via GitHub Secrets only:** referenced as `${{ secrets.* }}`; **never** in the YAML
  or repo; mock-mode means forks/PRs need none.
- **Caching + matrix-ready:** dependency cache keyed on the lockfile; Python-version matrix
  stubbed for easy fan-out.
- **Least privilege:** `permissions:` scoped to read by default.

## Maps to the book
- **Ch 7 — Version Control, Testing & Quality:** CI for pytest + testing non-determinism (the
  chapter that produces this template).
- **Ch 22 — Evaluation & Quality:** the eval-as-a-gate idea wired into CI.
- **Ch 36 — Infrastructure as Code:** CI/CD pipelines that also build/deploy.
- **Templates:** runs [`../eval-dataset-template/`](../eval-dataset-template/PLAN.md)'s
  `run.py` as the gate. **Blueprint:** executes
  [`../../blueprints/eval-harness/`](../../blueprints/eval-harness/PLAN.md). **Capstone:**
  mirrors `.github/workflows/` in
  [`../../../chapters/92-appendix-capstone.typ`](../../../chapters/92-appendix-capstone.typ).

## Phase-2 definition of done
- [ ] `ci.yml` runs lint + type + test green on the starter project; deps cached.
- [ ] `eval-gate.yml` runs the eval set in `MOCK=1` (no spend) and fails the build on a low score.
- [ ] No secret literals in any YAML; live (`MOCK=0`) path is a separate guarded job.
- [ ] `permissions:` are least-privilege; matrix/nightly hooks are clearly `▢ TODO`.
