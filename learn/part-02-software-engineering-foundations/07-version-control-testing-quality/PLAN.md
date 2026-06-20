# Ch 07 — Version Control, Testing & Quality

> Companion plan · Part II · book file `chapters/07-version-control-testing-quality.typ`
> Status: 📋 planned (Phase 1)

## Role in the companion
This is where the safety harness gets built. The drill turns pytest + the `FakeLLM` fixture
into muscle memory and tackles the AI-era question head-on — *how do you test a
non-deterministic system?* — by separating the deterministic shell from the probabilistic
core. It feeds the CI template that protects `main` for the whole capstone: the gates that let
a codebase absorb generated code at the speed it arrives.

## Planned notebooks

### 07-01 · `07-01-pytest-and-testing-nondeterminism.ipynb` — Testing a system with a model in it
- **Type:** drill
- **Maps to:** book §7.2 (the testing pyramid + testing non-determinism), §7.3 (pytest deeply)
- **Objective:** unit-test agent logic at millisecond speed with a `FakeLLM`, mock the model's
  *contract* at the HTTP layer, and know what belongs in CI vs. an eval.
- **Prereqs:** Ch 4 (async), Ch 5 (the injected `LLMProvider` seam — testability is a design
  property earned at construction).
- **Cell arc:**
  - 🧠 the pyramid as the harness that makes speed safe: many unit, fewer integration, few
    e2e; push every check as far down as it runs.
  - The architectural move: split *deterministic logic* (routing, parsing, budgets, dispatch —
    unit-test with a fake) from *model behavior* (an eval, Ch 22 — not a CI red/green test).
  - 🔧 build the book's `FakeLLM` (scripted replies, records prompts) as a pytest fixture;
    write `test_agent_dispatches_search_tool` asserting *structure* (`action.tool == "search"`,
    `"Oslo" in prompts[0]`), never exact strings.
  - ⚠️ pitfall: a bare `async def` test is *collected but never awaited* without
    `pytest-asyncio` — it passes green having run nothing. Mark it / set `asyncio_mode="auto"`.
  - `parametrize` a chunker's edges into a table; `monkeypatch` an env var with auto-cleanup;
    `respx` to assert the client retries on 429 at the HTTP boundary (no key, no flakes).
  - 🔮 *predict* the Hypothesis counterexample, then `@given` a chunker invariant — assert
    *coverage* (`set(text) <= set("".join(chunks))`), not exact reconstruction (overlap
    double-counts), and watch shrinking find a minimal failing case.
  - ⚠️ pitfall: mock at boundaries you *own* (Protocol, repo, transport), not vendor internals
    like `Messages.create` — that couples tests to a private API and breaks each SDK release.
  - 🎯 senior lens: assert *properties* (parses as JSON, tool is registered, under token cap)
    — they survive model upgrades; golden transcripts don't.
- **Datasets/fixtures:** all in-notebook (`FakeLLM` replies, a tiny chunker, mocked HTTP); no
  network, no committed data.
- **APIs & cost:** none / offline (`FakeLLM` + `respx`; never hits a live model).
- **You'll be able to:** test deterministic agent logic exhaustively and fast, and draw the
  line between a unit test and an eval.

### 07-02 · `07-02-git-and-quality-gates.ipynb` — Bisect, and the gates that hold the line
- **Type:** drill
- **Maps to:** book §7.1 (git beyond the basics), §7.4 (quality gates: ruff, mypy,
  pre-commit), §7.5 (CI/CD foundations) — the chapter's 🔧 Build (full harness + CI workflow)
- **Objective:** binary-search history for the commit that broke a test, and assemble the
  mechanical quality gates (ruff + mypy + pytest, pre-commit and CI) that protect `main`.
- **Prereqs:** 07-01; Ch 4 (`pyproject.toml`, `uv`).
- **Cell arc:**
  - 🧠 git history as a debugging instrument, not a save button; trunk-based dev (short
    branches, `main` always releasable; flags hide unfinished work); rebase-own / merge-to-
    integrate / never rewrite shared history (`--force-with-lease`).
  - 🔧 in a throwaway temp repo: seed a few commits where one breaks a test, then
    `git bisect run pytest ...` and watch it find the bad commit in O(log n) checkouts.
  - 🔮 *predict* how many steps bisect needs across N commits (≈log₂N), then read the output.
  - 🔧 the gate stack: ruff (lint + format, replacing flake8/isort/Black) and mypy/pyright
    configured in `pyproject.toml`; the book's `.pre-commit-config.yaml` (pinned `rev`).
  - 🔧 the book's GitHub Actions `ci` workflow verbatim: `setup-uv` → `uv sync --all-groups`
    (exact lockfile env) → ruff check / ruff format --check / mypy src / pytest — then require
    it green to merge.
  - 🧠 shift-left: each defect class caught at its earliest, cheapest gate; the local run is
    courtesy, the CI run is law.
  - ⚠️ pitfall: skipping the lockfile in CI — `uv sync` against the committed lock is what makes
    CI test the dependency tree production runs; drift hides here.
  - 📋 the version-control & quality checklist as a self-audit.
  - 🎯 senior lens: gates change role when AI writes the code — a model never internalizes
    feedback, so ruff/mypy/tests become the always-on reviewers of machine output.
  - **Closes by pointing at** [`templates/github-actions-ci/`](../../../templates/github-actions-ci/)
    — the copy-me version of the workflow built here.
- **Datasets/fixtures:** a temp git repo created in-cell (commits + a trivial failing test);
  the YAML configs shown as text, not executed against a real CI.
- **APIs & cost:** none / offline (git + ruff + mypy + pytest run locally; no model calls).
- **You'll be able to:** bisect a regression in minutes and stand up the exact gate set that
  guards the capstone's `main`.

## Feeds (cross-pillar)
- **Blueprint(s):** —
- **Template(s):** [`templates/github-actions-ci/`](../../../templates/github-actions-ci/) —
  this chapter contributes the CI workflow (uv + ruff + mypy + pytest, lockfile-pinned) and the
  `.pre-commit-config.yaml`. 07-02 ends by pointing here.
- **Capstone:** seeds the capstone's test harness (`FakeLLM` fixture + first agent tests under
  `tests/`), `pyproject.toml` tool config, and the branch-protected CI that every later
  chapter's code — human or generated — enters through (the chapter's 🔧 Build).

## Dependencies
- Ch 4 (async, packaging, `uv`) · Ch 5 (the injected `LLMProvider` — without it, `FakeLLM`
  testing is impossible). Forward link: Ch 22 (evals — model *quality* lives there, not CI).

## Phase-2 definition of done
- [ ] Both notebooks run top-to-bottom in `MOCK=1` (offline) with no errors; the bisect demo
      uses a self-contained temp repo and cleans up after itself.
- [ ] `FakeLLM`, the Hypothesis invariant (coverage, not reconstruction), the `pre-commit`
      config, and the GitHub Actions workflow match the book's §7 code exactly.
- [ ] The `pytest-asyncio` "collected but never awaited" pitfall is demonstrated, not just told.
- [ ] Recap + 2–4 exercises per notebook; the link to `templates/github-actions-ci/` resolves.
