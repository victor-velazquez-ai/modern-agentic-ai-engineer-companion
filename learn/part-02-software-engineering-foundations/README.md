# Part II — Software Engineering Foundations (Ch 4–7)

> 📓 Companion to **Modern Agentic AI Engineer** · Part II · `learn/part-02-software-engineering-foundations/`
> Status: 📋 planned (Phase 1) — these folders hold `PLAN.md` files; notebooks land in Phase 2.

## What this part adds to the book

Part II is the craft layer the rest of the platform stands on: production Python, clean design,
the data structures that actually show up, and the safety harness of tests and CI. Because it's
**practice, not new machinery**, its companion leans on **drills** and **concept-labs** rather
than big builds — the point is *fluency you feel*, not another framework to clone:

- You don't read about a shared-mutable-state bug — you run it, predict the alias, and fix it.
- You don't read that `id in list` is quadratic — you *time* it against the `set` fix at scale
  and watch one melt.
- You don't read "test the deterministic shell, not the model" — you write the `FakeLLM` unit
  test and see a bare `async` test pass green having run nothing.

Three small but load-bearing pieces of the **capstone** are seeded here and imported by every
later part: the `core/` trio (config, errors, structured logging — Ch 4), the provider/domain
seams (`LLMProvider` + adapter + factory, domain objects that own their rules — Ch 5), and the
**CI safety harness** that protects `main` (Ch 7 → the `templates/github-actions-ci/` template).
Everything stays **offline and free**: these notebooks need no API key — fakes, mocks, and tiny
timed stubs stand in for the network and the model.

## Chapters in this part

| Ch | Title | Companion emphasis | Notebooks | Plan |
|---|---|---|---|---|
| 04 | Production Python | Drills + concept-lab: mutability/typing, async & the event loop, packaging → the `core/` build | 3 | [PLAN](04-production-python/PLAN.md) |
| 05 | Clean Code & Design that Lasts | Refactoring drill + patterns concept-lab; seeds `providers/` + `domain/` | 2 | [PLAN](05-clean-code-and-design/PLAN.md) |
| 06 | Data Structures, Algorithms & Complexity | Drill (Big-O you can feel) + 🔧 the topo-sort plan executor | 2 | [PLAN](06-data-structures-and-algorithms/PLAN.md) |
| 07 | Version Control, Testing & Quality | pytest + testing non-determinism drill → CI template; git bisect & quality gates | 2 | [PLAN](07-version-control-testing-quality/PLAN.md) |

## Feeds at a glance

- **Templates:** Ch 07 → [`templates/github-actions-ci/`](../../templates/github-actions-ci/)
  (uv + ruff + mypy + pytest CI workflow and pre-commit config).
- **Capstone:** Ch 04 → `core/` (config, errors, logging) · Ch 05 → `providers/` + `domain/`
  (seams + rules-in-the-domain) · Ch 06 → the plan executor / scheduling core · Ch 07 → the
  `tests/` harness (`FakeLLM`) + branch-protected CI.
- **Blueprints:** none authored in this part — the patterns recur, but their standalone
  reference versions live with later, build-heavy chapters.

## Suggested path

Run the notebooks in chapter order: Ch 4 establishes typing/async/`core/` that Ch 5–7 assume,
Ch 5 introduces the injected `LLMProvider` seam that makes Ch 7's `FakeLLM` testing possible,
Ch 6 is independent practice, and Ch 7 ties it together into the gate every later chapter's code
passes through. New to the repo? Start with Part I's
[`03-mental-model`](../part-01-landscape-and-mindset/03-mental-model/PLAN.md) for the map, then
come here.

See [`docs/REPO-PLAN.md`](../../docs/REPO-PLAN.md) for the full chapter→asset map and
[`docs/CONVENTIONS.md`](../../docs/CONVENTIONS.md) for the `PLAN.md` template these follow.
