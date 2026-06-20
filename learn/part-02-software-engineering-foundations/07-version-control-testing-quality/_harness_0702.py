# ===== CELL 1 =====
# --- Setup: imports, env, and the MOCK switch ---------------------------------
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
    print("      with a pure-Python binary search so the notebook still runs.")

# ===== CELL 2 =====
# The senior workflow as runnable reference (printed, not executed against a remote).
WORKFLOW = textwrap.dedent("""\
    git switch -c feat/tool-retries     # short-lived branch
    git fetch origin
    git rebase origin/main              # replay MY commits onto fresh main
    git push --force-with-lease         # safe force: fails if the remote moved
""")
print(WORKFLOW)
print("Rule of thumb:")
print("  rebase OWN unpushed work   -> linear, reviewable history")
print("  merge via PR to integrate  -> shared history is never rewritten")
print("  --force-with-lease only    -> refuses to clobber someone else's push")

# ===== CELL 3 =====
N_COMMITS = 16        # we'll build 16 commits; exactly one introduces the bug
worst_case = math.ceil(math.log2(N_COMMITS))
print(f"commits to search : {N_COMMITS}")
print(f"predicted steps   : ~ceil(log2({N_COMMITS})) = {worst_case} checkouts")
print(f"(linear search would be up to {N_COMMITS} — bisect turns O(n) into O(log n).)")

# ===== CELL 4 =====
def run(cmd, cwd, env=None, check=True):
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
    return "def add(a, b):\n    return a + b\n"

def bad_module():
    # the regression: subtracts instead of adds
    return "def add(a, b):\n    return a - b\n"

TEST_SRC = textwrap.dedent("""\
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
    print("git unavailable -> will simulate bisect in pure Python below.")

# ===== CELL 5 =====
# Now the star: git bisect run drives pytest across history automatically.
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
    print("MATCH:", lo == BAD_COMMIT_INDEX)

# ===== CELL 6 =====
PYPROJECT_TOOL_CONFIG = textwrap.dedent("""\
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
print("One config; three consumers (editor, pre-commit, CI) -> no 'works on my machine'.")

# ===== CELL 7 =====
PRE_COMMIT_CONFIG = textwrap.dedent("""\
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
print("shift-left: catch formatting/lint at the cheapest point — before review, before CI.")

# ===== CELL 8 =====
CI_WORKFLOW = textwrap.dedent("""\
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
print(CI_WORKFLOW)

# ===== CELL 9 =====
# Make the lockfile point concrete: a hand-resolved "lock" pins EVERY version,
# so two machines install byte-identical trees. Loose ranges do not.
loose_requirements = ["anthropic>=0.40", "httpx>=0.27"]
locked_tree = {
    "anthropic": "0.42.0", "httpx": "0.28.1",
    "httpcore": "1.0.7", "anyio": "4.8.0", "certifi": "2025.1.31",  # transitives, pinned
}
print("loose (could resolve differently next week):")
for r in loose_requirements:
    print("   ", r)
print("\nlocked (uv.lock — what CI and prod BOTH install):")
for pkg, ver in locked_tree.items():
    print(f"    {pkg}=={ver}")
print("\nCI runs `uv sync` against this lock -> it tests the tree production runs.")

# ===== CELL 10 =====
checklist = {
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
print(f"\n{sum(checklist.values())}/{len(checklist)} green — flip any False on your own repo and fix it.")

# ===== CELL 11 =====
# Clean up the throwaway repo — leave no temp dirs behind.
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
    print("nothing to clean up (no temp repo was created).")

# ===== CELL 12 =====
# Exercise 1 — your code here


# ===== CELL 13 =====
# Exercise 2 — your code here


# ===== CELL 14 =====
# Exercise 3 — your code here


# ===== CELL 15 =====
# Exercise 4 — your code here

