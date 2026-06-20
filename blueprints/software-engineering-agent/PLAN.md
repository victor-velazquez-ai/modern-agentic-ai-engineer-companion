# Blueprint — Software-Engineering Agents  (solution)

> Appendix G use case · Status: 📋 planned (Phase 1)

## The problem it solves
Reviewer load, thin test coverage, and migrations that are too tedious and sprawling for
humans to do consistently. Engineering leaders and platform teams want faster review cycles,
better coverage, and mechanical migrations done in a fraction of the time — attacking toil
like a framework migration across hundreds of repositories.

## What it does
Agents pointed at the software-development lifecycle: automated code review, test generation,
large-scale refactors and framework migrations, dependency upgrades, and documentation. The
agent reads code, runs tests, and proposes diffs, **with the test suite and CI as the
verification loop** — a generated change is only accepted if tests and checks pass. The
environment is verifiable (tests, type-checkers, CI give ground truth most domains lack), and
human review stays on the merge (Appendix G → "Software-engineering agents"; the book's
thesis made literal — the AI writes the code, you own the architecture and test contract).

## Composes (pattern blueprints used)
- [`../agent-loop/`](../agent-loop/) — read code → run tests → propose diff loop; tests/CI as the verification signal (Ch 12, 16).
- [`../multi-agent-supervisor/`](../multi-agent-supervisor/) — decompose larger jobs across files/repos (Ch 17).
- [`../eval-harness/`](../eval-harness/) — **CI *is* the eval**: tests, linters, type-checkers as the pass/fail oracle (Ch 22).
- [`../observability-stack/`](../observability-stack/) — observability over agent runs to debug failures (Ch 23).
- *(reuses)* [`../mcp-server/`](../mcp-server/) — sandboxed repo/test/command tools, least-privilege, no prod access (Ch 12, 41).

## Planned structure
```text
software-engineering-agent/
├── README.md
├── PLAN.md
├── app/
│   ├── code_agent.py         # agent-loop: read repo, run tests, propose diff (Ch 12, 16)
│   ├── migrate.py            # per-file manifest → resumable/idempotent migration (Ch 31, 43)
│   └── pr.py                 # structured diff/PR for human review (Ch 15, 20)
├── tools/
│   └── sandbox_mock.py       # sandboxed read/test/exec tools, least-privilege (Ch 41)
├── sample_repo/              # tiny target repo with a failing test + a migration target
├── ci/
│   └── oracle.py             # tests+lint+types as pass/fail gate (guard the oracle itself)
└── demo.py                   # MOCK: generate a fix, run the oracle, emit a PR (no auto-merge)
```

## Maps to the book
- **Appendix G:** "Software-engineering agents" (tool use + multi-agent + CI gates; buyer = Eng leaders/platform teams).
- **Chapters showcased:** 12/41 (sandboxed least-privilege tools), 16 (test/CI verification
  loop), 17 (multi-agent across files/repos), 22 (CI-as-eval oracle), 31/43 (per-file
  manifest, resumable migration), 15/20 (structured diffs/PRs + human review on merge), 23
  (run observability).

## How to adapt it
- Point `tools/sandbox_mock.py` at your sandbox/runner with **strict least-privilege and no production access**.
- Replace `sample_repo/` with your codebase; wire `ci/oracle.py` to your real test/lint/type suite.
- **Invest in the test suite** — the value is capped by verification quality; never auto-merge without human review.
- For migrations, keep the per-file manifest so the job is resumable and idempotent across hundreds of files.
- Guard the oracle: reject changes that "fix" tests by deleting assertions.

## Phase-2 definition of done
- [ ] `demo.py` runs in MOCK mode; generates a change, runs the oracle, and emits a PR (never auto-merges).
- [ ] README frames problem → solution → pitch and links its Appendix-G section + chapters.
- [ ] Sandbox is least-privilege; migration manifest is resumable; composes agent-loop + multi-agent-supervisor without forking.
- [ ] CI-as-eval gate present and assertion-deletion is caught.
