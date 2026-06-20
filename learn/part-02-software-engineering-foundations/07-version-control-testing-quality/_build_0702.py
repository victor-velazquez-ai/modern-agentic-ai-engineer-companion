import json, os

DIR = os.path.dirname(os.path.abspath(__file__))

def md(text):
    lines = text.split("\n")
    src = [l + "\n" for l in lines[:-1]] + ([lines[-1]] if lines[-1] != "" else [])
    return {"cell_type": "markdown", "metadata": {}, "source": src}

def code(text):
    lines = text.split("\n")
    src = [l + "\n" for l in lines[:-1]] + ([lines[-1]] if lines[-1] != "" else [])
    return {"cell_type": "code", "execution_count": None, "metadata": {}, "outputs": [], "source": src}

cells = []

cells.append(md(
"""# Bisect, and the gates that hold the line

> 📓 *Companion to* **Modern Agentic AI Engineer** *· Ch 07 §7.1, §7.4–7.5 · type: drill*

**One-line promise:** binary-search your own history for the commit that broke a test with `git bisect run`, then assemble the mechanical quality gates — ruff + mypy + pytest, in pre-commit and CI — that keep `main` always releasable."""
))

cells.append(md(
"""## 🧠 Why this matters

History is a **debugging instrument**, not a save button. When a test that passed last week is red today and you have no idea which of 80 commits did it, `git bisect` finds the culprit in `O(log n)` checkouts — and *fully automatically* if a test can detect the bug. That is the payoff of committing small and often: you can't bisect inside a 2,000-line commit.

The other half is the **gate stack**. Style debates and trivial bugs should be settled by machines, instantly, before a human reviews anything: ruff for lint+format, mypy for types, pytest for logic — run locally as a pre-commit *courtesy* and again in CI as *law*. This matters double in the AI era: a code-generating model never internalizes feedback, so the gates become the always-on reviewers of machine output. This drill builds both, in a throwaway temp repo that cleans up after itself — no network, no risk to your real repos."""
))

cells.append(md(
"""## Objectives & prereqs

**By the end you can:**
- Drive `git bisect run` over a seeded history and watch it pin the bad commit in `~log2(N)` steps.
- Predict the number of bisect steps for N commits before you run it.
- Configure ruff and mypy in `pyproject.toml`, and the book's pinned `.pre-commit-config.yaml`.
- Read the book's GitHub Actions `ci` workflow (`setup-uv` -> `uv sync` -> ruff/mypy/pytest) and explain why the **lockfile** step is load-bearing.
- Self-audit against the version-control & quality checklist.

**Prereqs:** notebook **07-01** (the tests bisect searches for); Ch 4 (`pyproject.toml`, `uv`). Requires a local `git` (standard on dev machines); **no GitHub account, no network, no API key** — the temp repo is local and disposable."""
))

cells.append(code(
'''# --- Setup: imports, env, and the MOCK switch ---------------------------------
# stdlib only (+ python-dotenv from requirements.txt). We shell out to the local
# `git` you already have. Everything happens in a throwaway temp dir we delete at
# the end — your real repos are never touched, and nothing goes over the network.
import os
import sys
import shutil
import subprocess
import tempfile
import textwrap
import math
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# Offline by design: git + pytest run locally; there is no model call to mock.
MOCK = os.getenv("COMPANION_MOCK", "1") == "1"

HAS_GIT = shutil.which("git") is not None
print(f"MOCK mode   : {MOCK}")
print(f"git present : {HAS_GIT}")
if not HAS_GIT:
    print("NOTE: git not found on PATH. The bisect cells will SIMULATE the search")
    print("      with a pure-Python binary search so the notebook still runs.")'''
))

cells.append(md(
"""## 1 · Git as a debugging instrument (§7.1)

Before bisect, the one-sentence rules that make history *bisectable* in the first place:

- **Trunk-based development:** short-lived branches merged into `main` within a day or two; `main` always releasable. Feature flags — not long branches — hide unfinished work.
- **Rebase vs merge:** rebase your *own unpushed* branch onto fresh `main` for linear, reviewable history; **merge** (via PR) to integrate; *never rewrite history others have pulled*.
- **`--force-with-lease`, never `--force`:** a safe push that fails if the remote moved under you.
- **Commit small and often:** you can squash on merge, but you cannot bisect inside one giant commit."""
))

cells.append(code(
'''# The senior workflow as runnable reference (printed, not executed against a remote).
WORKFLOW = textwrap.dedent("""\\
    git switch -c feat/tool-retries     # short-lived branch
    git fetch origin
    git rebase origin/main              # replay MY commits onto fresh main
    git push --force-with-lease         # safe force: fails if the remote moved
""")
print(WORKFLOW)
print("Rule of thumb:")
print("  rebase OWN unpushed work   -> linear, reviewable history")
print("  merge via PR to integrate  -> shared history is never rewritten")
print("  --force-with-lease only    -> refuses to clobber someone else's push")'''
))

cells.append(md(
"""## 2 · 🔮 Predict: how many steps does bisect need?

`git bisect` is a **binary search** over commits. Each step halves the suspect range, so for `N` commits between the last-known-good and the first-known-bad, it converges in about `log2(N)` checkouts. Twelve steps search four thousand commits.

**Predict before running:** we're about to seed a history where commit #7 (0-indexed) of ~15 breaks a test. **How many `git bisect` steps will it take to find it?** Compute `ceil(log2(N))` in your head, then check."""
))

cells.append(code(
'''N_COMMITS = 16        # we'll build 16 commits; exactly one introduces the bug
worst_case = math.ceil(math.log2(N_COMMITS))
print(f"commits to search : {N_COMMITS}")
print(f"predicted steps   : ~ceil(log2({N_COMMITS})) = {worst_case} checkouts")
print(f"(linear search would be up to {N_COMMITS} — bisect turns O(n) into O(log n).)")'''
))

cells.append(md(
"""## 3 · 🔧 Seed a throwaway repo and let `git bisect run` find the bad commit

We build a temp git repo with `N_COMMITS` commits to a tiny module. The function returns the right answer until commit #7, which introduces a regression; a committed test detects it. Then `git bisect run pytest ...` binary-searches the history automatically. If `git` is unavailable, we fall back to a pure-Python binary search so the lesson still lands.

> ⚠️ This runs entirely inside a `tempfile.mkdtemp()` directory and is **deleted at the end of the notebook**. It never touches your real repositories and uses an isolated git identity via env vars (no global config writes)."""
))

cells.append(code(
'''def run(cmd, cwd, env=None, check=True):
    """Run a command, return CompletedProcess. Output captured (kept quiet)."""
    return subprocess.run(
        cmd, cwd=cwd, env=env, check=check,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
    )


def make_git_env(workdir):
    """Isolated git identity: no global config touched, deterministic commits."""
    env = dict(os.environ)
    env.update({
        "GIT_AUTHOR_NAME": "Drill", "GIT_AUTHOR_EMAIL": "drill@example.test",
        "GIT_COMMITTER_NAME": "Drill", "GIT_COMMITTER_EMAIL": "drill@example.test",
        "GIT_CONFIG_GLOBAL": os.path.join(workdir, ".gitconfig_none"),
        "GIT_CONFIG_SYSTEM": os.path.join(workdir, ".gitconfig_none_sys"),
    })
    return env


BAD_COMMIT_INDEX = 7   # the commit that introduces the regression (0-indexed)

def good_module():
    # returns the CORRECT answer
    return "def add(a, b):\\n    return a + b\\n"

def bad_module():
    # the regression: subtracts instead of adds
    return "def add(a, b):\\n    return a - b\\n"

TEST_SRC = textwrap.dedent("""\\
    from calc import add

    def test_add():
        assert add(2, 3) == 5
""")

tmpdir = None
bisect_found = None

if HAS_GIT:
    tmpdir = tempfile.mkdtemp(prefix="bisect_drill_")
    repo = Path(tmpdir)
    env = make_git_env(tmpdir)
    run(["git", "init", "-q", "-b", "main"], cwd=repo, env=env)
    # Keep line endings as-is so git stays quiet and the demo is reproducible.
    run(["git", "config", "core.autocrlf", "false"], cwd=repo, env=env)

    # The test is present from the very first commit so bisect can run it everywhere.
    (repo / "test_calc.py").write_text(TEST_SRC, encoding="utf-8")

    shas = []
    for i in range(N_COMMITS):
        body = bad_module() if i >= BAD_COMMIT_INDEX else good_module()
        (repo / "calc.py").write_text(body, encoding="utf-8")
        run(["git", "add", "-A"], cwd=repo, env=env)
        # --allow-empty: consecutive good commits write identical content, but we
        # still want each to be a distinct point in history for bisect to search.
        run(["git", "commit", "-q", "--allow-empty", "-m", f"commit {i}: feature work"],
            cwd=repo, env=env)
        sha = run(["git", "rev-parse", "HEAD"], cwd=repo, env=env).stdout.strip()
        shas.append(sha)

    good_sha, bad_sha = shas[0], shas[-1]

    # Sanity: the root commit passes the test, the tip (HEAD) fails it.
    def test_passes_at(sha):
        run(["git", "checkout", "-q", sha], cwd=repo, env=env)
        rc = run([sys.executable, "-m", "pytest", "-q", "test_calc.py"],
                 cwd=repo, env=env, check=False).returncode
        return rc == 0
    assert test_passes_at(good_sha), "root commit should be GOOD"
    assert not test_passes_at(bad_sha), "tip commit should be BAD"
    run(["git", "checkout", "-q", bad_sha], cwd=repo, env=env)  # back to a broken HEAD
    print(f"seeded {N_COMMITS} commits in a temp repo; bug introduced at commit #{BAD_COMMIT_INDEX}")
    print(f"  good (root) : {good_sha[:10]}   bad (HEAD): {bad_sha[:10]}")
else:
    print("git unavailable -> will simulate bisect in pure Python below.")'''
))

cells.append(code(
'''# Now the star: git bisect run drives pytest across history automatically.
if HAS_GIT:
    run(["git", "bisect", "start"], cwd=repo, env=env)
    run(["git", "bisect", "bad", bad_sha], cwd=repo, env=env)
    run(["git", "bisect", "good", good_sha], cwd=repo, env=env)
    proc = run(
        ["git", "bisect", "run", sys.executable, "-m", "pytest", "-q", "test_calc.py"],
        cwd=repo, env=env, check=False,
    )
    out = proc.stdout
    # The last "<sha> is the first bad commit" line names the culprit.
    first_bad_line = [ln for ln in out.splitlines() if "is the first bad commit" in ln]
    steps = out.count("Bisecting:")
    run(["git", "bisect", "reset"], cwd=repo, env=env)

    bisect_found = first_bad_line[0].split()[0] if first_bad_line else None
    expected_sha = shas[BAD_COMMIT_INDEX]
    print(f"bisect performed ~{steps} checkout step(s) (predicted ~{worst_case}).")
    if bisect_found:
        print(f"first bad commit found: {bisect_found[:10]}")
        print(f"expected (commit #{BAD_COMMIT_INDEX}): {expected_sha[:10]}")
        print("MATCH:", bisect_found == expected_sha)
else:
    # Pure-Python stand-in: binary search over a boolean history.
    def is_good(i):
        return i < BAD_COMMIT_INDEX
    lo, hi, steps = 0, N_COMMITS - 1, 0
    while lo < hi:
        mid = (lo + hi) // 2
        steps += 1
        if is_good(mid):
            lo = mid + 1
        else:
            hi = mid
    print(f"simulated bisect: {steps} step(s) (predicted ~{worst_case}).")
    print(f"first bad commit index found: {lo}  (expected {BAD_COMMIT_INDEX})")
    print("MATCH:", lo == BAD_COMMIT_INDEX)'''
))

cells.append(md(
"""**What you just saw.** bisect ran the test at `~log2(N)` commits — not all N — and named the exact commit that flipped the test from green to red. The cost is `O(log n)` checkouts; the prerequisite is a *fast, deterministic* test (which is precisely what notebook 07-01 built) and *small* commits (you can't isolate a bug inside a 2,000-line one)."""
))

cells.append(md(
"""## 4 · 🔧 The gate stack: ruff + mypy in `pyproject.toml` (§7.4)

As of early 2026 the standard Python quality stack is small: **ruff** (one fast tool for lint *and* format, replacing flake8 + isort + Black) and **mypy** (or pyright) for types. Configure both in `pyproject.toml` so the same settings drive your editor, pre-commit, and CI."""
))

cells.append(code(
'''PYPROJECT_TOOL_CONFIG = textwrap.dedent("""\\
    # pyproject.toml — the single source of truth for the gates
    [tool.ruff]
    line-length = 100
    target-version = "py312"

    [tool.ruff.lint]
    select = ["E", "F", "I", "B", "UP"]   # pyflakes, pycodestyle, isort, bugbear, pyupgrade

    [tool.mypy]
    python_version = "3.12"
    strict = true
    warn_unused_ignores = true

    [tool.pytest.ini_options]
    asyncio_mode = "auto"                 # the 07-01 fix: async tests actually run
""")
print(PYPROJECT_TOOL_CONFIG)
print("One config; three consumers (editor, pre-commit, CI) -> no 'works on my machine'.")'''
))

cells.append(md(
"""## 5 · 🔧 The book's `.pre-commit-config.yaml` (§7.4)

The `pre-commit` hook runs the cheap gates at *commit time*, so broken formatting or obvious lint never even reaches CI. Note the **pinned `rev`** — you update the gate version deliberately, never silently."""
))

cells.append(code(
'''PRE_COMMIT_CONFIG = textwrap.dedent("""\\
    # .pre-commit-config.yaml
    repos:
      - repo: https://github.com/astral-sh/ruff-pre-commit
        rev: v0.9.0          # pin; update deliberately
        hooks:
          - id: ruff         # lint (+ autofix)
            args: [--fix]
          - id: ruff-format  # formatting
""")
print(PRE_COMMIT_CONFIG)
print("Install once with:  pre-commit install   (then it runs on every `git commit`).")
print("shift-left: catch formatting/lint at the cheapest point — before review, before CI.")'''
))

cells.append(md(
"""## 6 · 🔧 The GitHub Actions `ci` workflow, verbatim (§7.5)

CI makes the gates **non-optional**: every push runs the full pipeline on a clean machine, and merging is blocked until it's green. This is the book's workflow for the capstone — the local run is courtesy, *this* run is law."""
))

cells.append(code(
'''CI_WORKFLOW = textwrap.dedent("""\\
    # .github/workflows/ci.yml
    name: ci
    on:
      pull_request:
      push:
        branches: [main]

    jobs:
      quality:
        runs-on: ubuntu-latest
        steps:
          - uses: actions/checkout@v4
          - uses: astral-sh/setup-uv@v5
          - run: uv sync --all-groups       # exact env from uv.lock
          - run: uv run ruff check .
          - run: uv run ruff format --check .
          - run: uv run mypy src
          - run: uv run pytest -q --maxfail=5
""")
print(CI_WORKFLOW)'''
))

cells.append(md(
"""> ⚠️ **Pitfall — skipping the lockfile in CI.** If you `pip install` loose ranges instead of `uv sync --all-groups` against the committed `uv.lock`, CI tests a *different* dependency tree than production runs, and dependency drift hides exactly there — a transitive bump turns green locally and red in prod. The lockfile step is what makes CI's pass *mean something*."""
))

cells.append(code(
'''# Make the lockfile point concrete: a hand-resolved "lock" pins EVERY version,
# so two machines install byte-identical trees. Loose ranges do not.
loose_requirements = ["anthropic>=0.40", "httpx>=0.27"]
locked_tree = {
    "anthropic": "0.42.0", "httpx": "0.28.1",
    "httpcore": "1.0.7", "anyio": "4.8.0", "certifi": "2025.1.31",  # transitives, pinned
}
print("loose (could resolve differently next week):")
for r in loose_requirements:
    print("   ", r)
print("\\nlocked (uv.lock — what CI and prod BOTH install):")
for pkg, ver in locked_tree.items():
    print(f"    {pkg}=={ver}")
print("\\nCI runs `uv sync` against this lock -> it tests the tree production runs.")'''
))

cells.append(md(
"""## 7 · 📋 Checklist — self-audit (§7 summary)

Run this against your own repo. It's the chapter's version-control & quality checklist as a few asserts you can adapt."""
))

cells.append(code(
'''checklist = {
    "Commits are small, logical, and explain WHY (bisectable history)": True,
    "Branches are short-lived; main is always releasable; flags hide WIP": True,
    "Never rewrite shared history; --force-with-lease only on own branches": True,
    "Most tests are unit-fast with a FakeLLM; integration covers real boundaries": True,
    "Non-determinism contained: logic unit-tested, HTTP mocked, quality -> evals": True,
    "Mocks sit at OWNED boundaries (protocols, transports), not vendor internals": True,
    "Gates are mechanical: ruff + mypy + tests in pre-commit AND CI, same lockfile": True,
    "Property-based tests guard the fiddly text machinery (chunkers, parsers)": True,
}
width = max(len(k) for k in checklist)
for item, done in checklist.items():
    mark = "[x]" if done else "[ ]"
    print(f"{mark} {item:<{width}}")
print(f"\\n{sum(checklist.values())}/{len(checklist)} green — flip any False on your own repo and fix it.")'''
))

cells.append(code(
'''# Clean up the throwaway repo — leave no temp dirs behind.
import stat

def _force_remove(func, path, _exc):
    # Git marks pack/object files read-only; clear the bit, then retry the delete.
    os.chmod(path, stat.S_IWRITE)
    func(path)

if tmpdir and os.path.isdir(tmpdir):
    # onexc (3.12+) / onerror (older) lets us clear the read-only bit Windows sets.
    try:
        shutil.rmtree(tmpdir, onexc=_force_remove)        # Python 3.12+
    except TypeError:
        shutil.rmtree(tmpdir, onerror=lambda f, p, e: _force_remove(f, p, e))
    print("temp repo removed:", not os.path.isdir(tmpdir))
else:
    print("nothing to clean up (no temp repo was created).")'''
))

cells.append(md(
"""## 🎯 Senior lens

Gates change *role* when AI writes the code. A human author internalizes a code-review comment and stops making that mistake; a code-generating model does not — it will cheerfully emit the same unused import, untyped dict, or swallowed exception forever. So ruff and mypy stop being style nags and become the **always-on reviewers of machine output**, and your test suite becomes the contract the generated code must satisfy *before* a human looks at it. Teams that invested here absorb AI-written code at the speed it arrives; teams reviewing by eyeball drown in plausible-looking regressions. Bisect is the same idea pointed backward in time: when a regression slips through anyway, a fast deterministic suite turns "we don't know what broke it" into a ten-minute mechanical search."""
))

cells.append(md(
"""## Recap

- `git bisect run <test>` binary-searches history for the breaking commit in `~log2(N)` checkouts — automatic when a test detects the bug.
- bisect's payoff is proportional to **test discipline + small commits**; you can't isolate a bug inside a 2,000-line commit.
- Trunk-based dev, rebase-own / merge-to-integrate, and `--force-with-lease` keep history clean enough to bisect.
- The gate stack is small: **ruff** (lint + format) and **mypy**, configured once in `pyproject.toml`.
- **pre-commit** runs the cheap gates locally (courtesy); **CI** runs them on a clean machine (law) and blocks merge until green.
- The **lockfile** (`uv sync` against `uv.lock`) makes CI test the *same* dependency tree production runs — skip it and drift hides.
- When AI writes the code, the gates become its mechanical, always-on reviewers."""
))

cells.append(md(
"""## Exercises

Predict the result before running each.

1. **Move the bug.** Set `BAD_COMMIT_INDEX = 11` and `N_COMMITS = 24`. Predict the new step count (`ceil(log2(24))`), then run section 3 and compare to the reported steps.
2. **A flaky test breaks bisect.** Make `test_calc.py` pass/fail randomly (e.g. `assert random.random() > 0.5`). Predict what `git bisect run` reports, then explain why a *deterministic* suite is a precondition for bisect.
3. **Tighten the gates.** Add `"S"` (flake8-bandit) and `"ANN"` (annotations) to the ruff `select` list in the config string, and `disallow_untyped_defs = true` to mypy. Describe one class of defect each newly catches.
4. **Break the lockfile invariant.** Imagine `httpx` ships `0.29` with a breaking change. Explain, in two sentences, why `uv sync` against the committed lock keeps CI green while a loose `httpx>=0.27` install would surprise you — and where you'd update the pin deliberately."""
))

cells.append(code('# Exercise 1 — your code here\n'))
cells.append(code('# Exercise 2 — your code here\n'))
cells.append(code('# Exercise 3 — your code here\n'))
cells.append(code('# Exercise 4 — your code here\n'))

cells.append(md(
"""## Next

- ⬅️ **Previous:** [`07-01-pytest-and-testing-nondeterminism.ipynb`](./07-01-pytest-and-testing-nondeterminism.ipynb) — the `FakeLLM`, the async pitfall, and property-based tests that bisect then searches for.
- 📦 **Template — copy this:** the production version of the workflow you just read lives in [`templates/github-actions-ci/`](../../../templates/github-actions-ci/) (uv + ruff + mypy + pytest, lockfile-pinned, plus the `.pre-commit-config.yaml`).
- 🏗️ **Capstone:** this is the chapter's 🔧 Build — the branch-protected CI that **every** later chapter's code, human-written or generated, enters through. It guards the capstone's `main` from day one.
- 📘 See the book **§7.1, §7.4–7.5** for git beyond the basics, the gate stack, and the CI/CD foundations; model **quality** gating (evals) is **Ch 22**, deliberately separate from this red/green CI."""
))

nb = {
    "cells": cells,
    "metadata": {
        "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
        "language_info": {"name": "python"},
    },
    "nbformat": 4,
    "nbformat_minor": 5,
}

out = os.path.join(DIR, "07-02-git-and-quality-gates.ipynb")
with open(out, "w", encoding="utf-8") as f:
    json.dump(nb, f, indent=1, ensure_ascii=False)
    f.write("\n")
print("wrote", out)
