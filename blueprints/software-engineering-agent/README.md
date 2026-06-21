# 🛠️ Blueprint — Software-Engineering Agent (solution)

> **Appendix G** use case · *composes* five **pattern blueprints** · Status: ✅ built
>
> Buyer: engineering leaders & platform teams. The book's thesis made literal —
> **the AI writes the code, you own the architecture and the test contract.**

A software-engineering agent pointed at the development lifecycle: automated **code review / fix
generation** and large-scale **framework migrations**, where **the test suite and CI are the
verification loop**. A generated change is accepted *only* if the oracle goes green — tests pass,
the code still compiles, and no assertion was deleted to fake it — and a **human still owns the
merge** (this tool never auto-merges).

```bash
python demo.py            # MOCK mode (default): no API key, no spend, deterministic, never merges
COMPANION_MOCK=0 python demo.py   # live path — inject a gateway-backed model (not bundled)
```

The demo, in three acts: (1) fix a failing test behind the oracle and emit a PR; (2) prove the
oracle **rejects** a "fix" that deletes an assertion; (3) run a **resumable, oracle-gated
migration** across the repo and emit a second PR. Nothing merges — two PRs are proposed, zero
merges.

---

## The problem it solves

Reviewer load, thin test coverage, and migrations too tedious and sprawling for humans to do
consistently — toil like a framework migration across hundreds of repositories. The reason a code
agent *works* where many agent domains struggle: **the environment is verifiable.** Code has an
oracle — tests, type-checkers, CI — that says *objectively* whether a change is good. That oracle is
the ground truth most domains lack, and it is the spine of this blueprint.

## The solution — composition, not a monolith

```text
                 ┌──────────────────────── this solution ────────────────────────┐
   task ───────▶ │  CodeAgent / Migration                                          │
                 │     │ reads code, proposes a diff, writes it                     │
                 │     ▼                                                            │
                 │  agent-loop ──tools──▶ sandbox (mcp-server Tool: read/list/write)│
                 │     │                  least-privilege · no shell · no network   │
                 │     ▼                                                            │
                 │  ci/oracle.py  ── CI *is* the eval (eval-harness) ──────────────│
                 │     │  tests green? compiles? assertions preserved?              │
                 │     ▼                                                            │
                 │  PullRequest  ── structured diff, human review ── NEVER merges   │
                 └────────────── observability-stack traces the whole run ─────────┘
```

| Composes (pattern blueprint) | Role here | Chapters |
|---|---|---|
| [`../agent-loop/`](../agent-loop/) | read code → propose diff → run oracle loop | 12, 16 |
| [`../multi-agent-supervisor/`](../multi-agent-supervisor/) | fan a migration across files (per-file units) | 17 |
| [`../eval-harness/`](../eval-harness/) | **CI is the eval** — the pass/fail oracle | 22 |
| [`../observability-stack/`](../observability-stack/) | trace each run; attach the oracle verdict | 23 |
| [`../mcp-server/`](../mcp-server/) *(reused)* | sandboxed, least-privilege repo tools | 12, 41 |

> **Compose, don't fork.** There is no install step. [`_blueprints.py`](./_blueprints.py) puts each
> sibling's `src/` on `sys.path` and the app imports the *real* package. Edit a pattern blueprint
> and this solution moves with it.

## What's in here

| File | Role |
|---|---|
| [`app/code_agent.py`](app/code_agent.py) | Drives the **agent-loop** with sandboxed tools to fix a failing test; accepts **only** on a green oracle, else reverts. Returns a `FixAttempt`. |
| [`app/migrate.py`](app/migrate.py) | Resumable, idempotent, **oracle-gated** rename across the repo behind a per-file JSON manifest (`legacy_clean` → `normalize`). |
| [`app/pr.py`](app/pr.py) | The structured `PullRequest` (title, body, per-file unified diff, oracle evidence). **No `merge()`** — a human owns the merge. |
| [`tools/sandbox_mock.py`](tools/sandbox_mock.py) | The capability boundary: read/list/write **confined to the repo**; shell/network/prod are refused. Built on the **mcp-server** `Tool`. |
| [`ci/oracle.py`](ci/oracle.py) | The oracle: runs tests in-process, lints (must compile), and the **assertion-deletion guard**. Each gate is an **eval-harness** `Case`. |
| [`sample_repo/`](sample_repo/) | A tiny target repo with a **failing test** (the `slugify` bug) and a **migration target** (the deprecated `legacy_clean`). |
| [`demo.py`](demo.py) | The runnable, offline end-to-end (fix → reject-a-cheat → migrate). |

## Two things worth seeing

**Guard the oracle.** The cheapest way for a model to make tests "pass" is to delete the
assertions. `ci/oracle.py` counts `assert` statements (via `ast`, so comments don't fool it) and
**fails the gate if the count dropped** versus the pre-change baseline. Act 2 of the demo feeds the
agent a model that does exactly this — and watches it get rejected.

**Resumable, idempotent migration.** Every file is a unit of work in a JSON manifest written after
*each* file. Re-running skips files already `done` (idempotent) and resumes after a crash exactly
where it stopped (resumable); re-applying the rewrite to a migrated file is a no-op. The gate is
**no-regression** (the rename must not increase failures or drop assertions), which is why it
tolerates the sample's deliberately-red `slugify` test while still catching a rename that breaks
behaviour.

---

## How to adapt it to your domain

1. **Point the sandbox at your runner.** Swap [`tools/sandbox_mock.py`](tools/sandbox_mock.py) for a
   real container/jail with **strict least-privilege and no production access**. The schemas and the
   confinement contract don't change. *Never grant prod access; never expose an open shell.*
2. **Replace `sample_repo/` with your codebase**, and wire [`ci/oracle.py`](ci/oracle.py) to your
   **real** test/lint/type command (`pytest`, `ruff`, `mypy`). The oracle's *contract* — "a change
   that reddens CI is rejected before it merges" — is identical.
3. **Invest in the test suite.** The agent's value is capped by verification quality: the better
   your oracle, the more you can safely automate. A thin suite means a weak oracle means little you
   can trust to a machine.
4. **Keep the per-file manifest** for migrations so a job across hundreds of files is resumable and
   idempotent. Fan it across workers using [`../multi-agent-supervisor/`](../multi-agent-supervisor/).
5. **Guard the oracle.** Reject changes that "fix" tests by deleting assertions or weakening the
   contract — the deletion guard here is the minimum; add mutation testing if you can.
6. **Never auto-merge.** [`app/pr.py`](app/pr.py) deliberately has no merge path. Wire your forge's
   API (GitHub/GitLab) in an adapter — the *only* place a token lives — and keep human review on the
   merge.

## Maps to the book

- **Appendix G:** "Software-engineering agents" (tool use + multi-agent + CI gates).
- **Chapters showcased:** 12/41 (sandboxed least-privilege tools), 16 (test/CI verification loop),
  17 (multi-agent across files), 22 (CI-as-eval oracle), 31/43 (per-file manifest, resumable
  migration), 15/20 (structured diffs/PRs + human review on merge), 23 (run observability).

> Free & offline by default (`COMPANION_MOCK=1`). The MOCK model is scripted to do exactly what a
> real model would be *asked* to do — list the repo, read the red test, read the source, write the
> minimal fix — so you read this blueprint by **running** it, with zero spend and zero risk.
