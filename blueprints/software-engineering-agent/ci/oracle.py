"""The oracle — CI *is* the eval (Ch 22). The pass/fail ground truth for every change.

The thesis of a software-engineering agent: the environment is **verifiable**. Unlike most
agent domains, code has an oracle — tests, linters, type-checkers — that says *objectively*
whether a change is good. So the eval harness here is not a bolt-on; it is the same harness the
``eval-harness`` blueprint ships, with the "expected answer" being **green CI**.

What the oracle checks, in order (a change must clear all of them):

1. **Tests** — discover and run every ``test_*`` callable in the target repo, in-process, no
   pytest dependency. Any failure or error fails the gate.
2. **Lint (light)** — the candidate must still *compile* (``py_compile``). A change that breaks
   syntax is rejected before it can break the build.
3. **Assertion-deletion guard** — the cheapest way for a model to make tests "pass" is to delete
   the assertions. The oracle counts ``assert`` statements in every ``test_*`` file and **fails
   the gate if the count dropped** versus the pre-change baseline. *Guard the oracle itself.*

Composition
-----------
Each check is wrapped as an ``eval-harness`` :class:`~eval_harness.Case` graded by a
:class:`~eval_harness.Grader`, and the suite is scored with ``eval_harness.run``. A perfect score
(every gate green) is the only thing ``code_agent``/``migrate`` will accept — exactly the
"baseline-or-better" contract the harness's gate enforces. The candidate under test is the
*repository state on disk* after a proposed write.
"""

from __future__ import annotations

import ast
import importlib
import importlib.util
import sys
import traceback
from dataclasses import dataclass, field
from pathlib import Path

# Compose the sibling pattern blueprints (eval-harness) without forking them.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from _blueprints import ensure_blueprints_on_path  # noqa: E402

ensure_blueprints_on_path()

from eval_harness import Case, GradeResult, run  # noqa: E402  (reused: CI is the eval)


# ------------------------------------------------------------------------------------------
# Reading the repo: tests and their assertion counts.
# ------------------------------------------------------------------------------------------

def _test_files(repo_root: Path) -> list[Path]:
    return sorted((repo_root / "tests").glob("test_*.py"))


def count_assertions(repo_root: Path) -> int:
    """Total ``assert`` statements across every test file — the assertion-deletion tripwire.

    Parsed with ``ast`` (not a regex) so commented-out or string-literal "assert" text does not
    inflate the count. A drop in this number between baseline and candidate means the change
    weakened the test contract, which the oracle treats as a failure even if tests pass.
    """
    total = 0
    for f in _test_files(repo_root):
        try:
            tree = ast.parse(f.read_text(encoding="utf-8"), filename=str(f))
        except SyntaxError:
            continue  # a syntactically broken test file is caught by the lint gate
        total += sum(1 for node in ast.walk(tree) if isinstance(node, ast.Assert))
    return total


# ------------------------------------------------------------------------------------------
# Running the suite in-process (no pytest dependency, fully offline).
# ------------------------------------------------------------------------------------------

@dataclass
class TestRun:
    """The result of running the repo's test suite once."""

    passed: int = 0
    failed: int = 0
    errors: tuple[str, ...] = ()

    @property
    def total(self) -> int:
        return self.passed + self.failed

    @property
    def green(self) -> bool:
        return self.failed == 0 and self.passed > 0


def _fresh_import(module_path: Path, repo_src: Path) -> object:
    """Import (or re-import) a module from a file path, picking up edits on disk.

    The agent rewrites files between oracle runs, so we must drop any cached module and load the
    current bytes. We add the repo's ``src/`` to ``sys.path`` so intra-repo imports (``import
    textkit``) resolve, then load the test module fresh.
    """
    if str(repo_src) not in sys.path:
        sys.path.insert(0, str(repo_src))
    # Evict the unit-under-test and the test module so edits on disk take effect.
    for name in ("textkit", "handlers", module_path.stem):
        sys.modules.pop(name, None)
    spec = importlib.util.spec_from_file_location(module_path.stem, module_path)
    if spec is None or spec.loader is None:  # pragma: no cover - defensive
        raise ImportError(f"cannot load test module {module_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)  # type: ignore[union-attr]
    return module


def run_tests(repo_root: Path) -> TestRun:
    """Discover ``test_*`` callables across the repo's test files and run them in-process."""
    repo_src = repo_root / "src"
    result = TestRun()
    errors: list[str] = []
    for test_file in _test_files(repo_root):
        try:
            module = _fresh_import(test_file, repo_src)
        except Exception:  # an import-time failure is a failure of the whole file
            result.failed += 1
            errors.append(f"{test_file.name}: import error\n{traceback.format_exc(limit=3)}")
            continue
        for attr in sorted(dir(module)):
            if not attr.startswith("test_"):
                continue
            fn = getattr(module, attr)
            if not callable(fn):
                continue
            try:
                fn()
                result.passed += 1
            except AssertionError as exc:
                result.failed += 1
                errors.append(f"{test_file.name}::{attr} FAILED: {exc or 'assertion failed'}")
            except Exception as exc:  # an error is distinct from a failure, but still red
                result.failed += 1
                errors.append(f"{test_file.name}::{attr} ERROR: {type(exc).__name__}: {exc}")
    result.errors = tuple(errors)
    return result


# ------------------------------------------------------------------------------------------
# Lint gate (light): everything under src/ must still compile.
# ------------------------------------------------------------------------------------------

def lint_ok(repo_root: Path) -> tuple[bool, str]:
    """Cheap stand-in for a real linter/type-checker: parse every source file.

    A real adaptation wires ``ruff``/``mypy``/your test command here; the *contract* — "a change
    that breaks the build is rejected before it merges" — is identical.
    """
    for src in sorted((repo_root / "src").glob("*.py")):
        try:
            ast.parse(src.read_text(encoding="utf-8"), filename=str(src))
        except SyntaxError as exc:
            return False, f"{src.name}: syntax error: {exc}"
    return True, "all source files parse"


# ------------------------------------------------------------------------------------------
# The oracle: assemble the gates as an eval-harness run.
# ------------------------------------------------------------------------------------------

@dataclass
class OracleReport:
    """The oracle's verdict for one repository state."""

    passed: bool
    score: float
    test_run: TestRun
    assertions: int
    baseline_assertions: int | None
    details: tuple[str, ...] = field(default_factory=tuple)

    def render(self) -> str:
        lines = [
            "Oracle verdict: " + ("GREEN ✓" if self.passed else "RED ✗"),
            f"  tests      : {self.test_run.passed} passed, {self.test_run.failed} failed",
            f"  assertions : {self.assertions}"
            + (
                f" (baseline {self.baseline_assertions})"
                if self.baseline_assertions is not None
                else ""
            ),
            f"  gate score : {self.score:.2f}",
        ]
        for d in self.details:
            lines.append(f"  - {d}")
        return "\n".join(lines)


class _BoolGrader:
    """An ``eval-harness`` grader: ``expected`` is True (the gate should pass), ``actual`` is the
    observed boolean. Full marks only when the check holds. Pure and never raises — a malformed
    result is a 0, not a crash (the harness's grader contract)."""

    def __init__(self, name: str) -> None:
        self.name = name

    def grade(self, expected: object, actual: object) -> GradeResult:
        if bool(actual) == bool(expected):
            return GradeResult.ok(f"{self.name}: ok")
        return GradeResult.fail(f"{self.name}: FAILED")


def evaluate(repo_root: Path, *, baseline_assertions: int | None = None) -> OracleReport:
    """Run all gates over the current repo state and return a pass/fail :class:`OracleReport`.

    ``baseline_assertions`` is the assertion count captured *before* the change; pass it so the
    deletion guard can fire. Omit it (e.g. the very first measurement) and the guard is skipped.
    """
    repo_root = Path(repo_root).resolve()
    test_run = run_tests(repo_root)
    lint_pass, lint_msg = lint_ok(repo_root)
    assertions = count_assertions(repo_root)

    assertions_preserved = (
        baseline_assertions is None or assertions >= baseline_assertions
    )

    # Model each gate as an eval-harness Case graded by a boolean grader: CI *is* the eval.
    checks: list[tuple[str, bool]] = [
        ("tests-green", test_run.green),
        ("lint-clean", lint_pass),
        ("assertions-preserved", assertions_preserved),
    ]
    cases = [Case(id=name, input=name, expected=True, tags=["ci-gate"]) for name, _ in checks]
    observed = dict(checks)
    report = run(
        candidate=lambda name: observed[name],
        cases=cases,
        grader=_BoolGrader("gate"),
        threshold=1.0,
    )

    details: list[str] = []
    if not lint_pass:
        details.append(f"lint: {lint_msg}")
    if not assertions_preserved:
        details.append(
            f"assertion-deletion guard TRIPPED: {assertions} < baseline {baseline_assertions} "
            "(a change may not 'fix' tests by weakening them)"
        )
    details.extend(test_run.errors)

    return OracleReport(
        passed=report.pass_rate == 1.0,
        score=report.mean_score,
        test_run=test_run,
        assertions=assertions,
        baseline_assertions=baseline_assertions,
        details=tuple(details),
    )
