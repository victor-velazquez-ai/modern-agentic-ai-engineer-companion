"""migrate — a resumable, idempotent, oracle-gated framework migration (Ch 17, 31, 43).

The toil this attacks: a deprecated API used across many files, the kind of mechanical change that
is too tedious for a human to do consistently and too sprawling to review in one diff. Here it is a
single deprecated function — ``legacy_clean`` → ``normalize`` — but the *shape* is what scales to a
framework migration across hundreds of repositories.

Three properties make it production-grade, and each maps to a pattern blueprint:

* **Fanned across files (multi-agent-supervisor, Ch 17).** Each file is an independent unit of
  work — a :class:`FileTask`. The migration plans the set, then processes them one by one (a real
  deployment fans them across workers; the topology is the supervisor's). One file failing the
  oracle does not abort the others.
* **Resumable + idempotent (Ch 31, 43).** Progress is written to a JSON :class:`MigrationManifest`
  after every file. Re-running skips files already ``done`` (idempotent) and picks up exactly where
  a crash left off (resumable). Re-applying the rewrite to an already-migrated file is a no-op.
* **Oracle-gated (eval-harness / CI-is-the-eval, Ch 22).** Every file's rewrite is verified by the
  oracle (``ci/oracle.py``) **before it is marked done**. A rewrite that reddens the suite is
  reverted and the file is recorded ``failed`` — the migration never trades correctness for
  coverage.

The migration **never auto-merges**: like :mod:`app.code_agent` it produces a
:class:`~app.pr.PullRequest` for human review. MOCK by default — the rewrite is a deterministic
text transform, so the whole job runs offline with no API spend.
"""

from __future__ import annotations

import json
import re
import shutil
import sys
import tempfile
from dataclasses import asdict, dataclass, field
from pathlib import Path

# --- composition seam ---------------------------------------------------------------------------
_SOLUTION_ROOT = Path(__file__).resolve().parent.parent
if str(_SOLUTION_ROOT) not in sys.path:
    sys.path.insert(0, str(_SOLUTION_ROOT))

from _blueprints import ensure_blueprints_on_path, repo_root as _bundled_repo_root  # noqa: E402

ensure_blueprints_on_path()
for _sub in ("ci",):
    _d = str(_SOLUTION_ROOT / _sub)
    if _d not in sys.path:
        sys.path.insert(0, _d)

import oracle as _oracle  # noqa: E402  (ci/oracle.py — gate every file)


# ------------------------------------------------------------------------------------------------
# The rewrite — a single, idempotent text transform. Pure and unit-testable.
# ------------------------------------------------------------------------------------------------

_OLD = "legacy_clean"
_NEW = "normalize"

# Match a *call site* or an *import* of the deprecated name, but never its ``def`` (we keep the
# deprecated alias defined so already-migrated code and third parties don't break). ``\b`` anchors
# avoid rewriting a substring of a longer identifier.
_CALL = re.compile(rf"(?<![\w.])({re.escape(_OLD)})\s*\(")
_IMPORT = re.compile(rf"(\bfrom\s+[\w.]+\s+import\s+(?:[^\n]*,\s*)?){re.escape(_OLD)}\b")
_DEF = re.compile(rf"^\s*def\s+{re.escape(_OLD)}\b")


def rename_call_sites(source: str) -> str:
    """Rewrite call sites and imports of ``legacy_clean`` to ``normalize``; leave its ``def`` alone.

    Idempotent: running it on already-migrated text returns the text unchanged (there are no call
    sites left to rewrite). Line-oriented so the deprecated *definition* line is preserved while
    every *use* is migrated — exactly the safe rename a reviewer would do by hand.
    """
    out_lines: list[str] = []
    for line in source.splitlines(keepends=True):
        if _DEF.match(line):
            out_lines.append(line)  # never rewrite the deprecated definition itself
            continue
        new_line = _CALL.sub(f"{_NEW}(", line)
        new_line = _IMPORT.sub(rf"\g<1>{_NEW}", new_line)
        out_lines.append(new_line)
    return "".join(out_lines)


def needs_migration(source: str) -> bool:
    """True if the file still *uses* (calls/imports) the deprecated name. Drives task discovery."""
    for line in source.splitlines():
        if _DEF.match(line):
            continue
        if _CALL.search(line) or _IMPORT.search(line):
            return True
    return False


# ------------------------------------------------------------------------------------------------
# The per-file manifest — the resumability + idempotency substrate.
# ------------------------------------------------------------------------------------------------

@dataclass
class FileTask:
    """One file's migration record. The unit the supervisor topology fans out."""

    path: str  # repo-relative
    status: str = "pending"  # pending | done | failed | skipped
    detail: str = ""

    @property
    def finished(self) -> bool:
        # ``done`` and ``skipped`` are terminal-success; ``failed`` is retried on resume.
        return self.status in {"done", "skipped"}


@dataclass
class MigrationManifest:
    """The resumable plan: every file and its status, persisted as JSON.

    Written after *every* file so a crash loses at most one file's progress. Loading an existing
    manifest and re-running is the resume path; files already ``done``/``skipped`` are not touched
    again (idempotent).
    """

    name: str
    tasks: list[FileTask] = field(default_factory=list)

    # --- persistence ---------------------------------------------------------
    def save(self, path: Path) -> None:
        path.write_text(
            json.dumps(
                {"name": self.name, "tasks": [asdict(t) for t in self.tasks]},
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )

    @classmethod
    def load(cls, path: Path) -> "MigrationManifest":
        obj = json.loads(Path(path).read_text(encoding="utf-8"))
        return cls(
            name=obj["name"],
            tasks=[FileTask(**t) for t in obj.get("tasks", [])],
        )

    # --- queries -------------------------------------------------------------
    def pending(self) -> list[FileTask]:
        """Tasks still to do — anything not already finished (so ``failed`` is retried)."""
        return [t for t in self.tasks if not t.finished]

    def by_status(self, status: str) -> list[FileTask]:
        return [t for t in self.tasks if t.status == status]

    @property
    def complete(self) -> bool:
        return all(t.finished for t in self.tasks)


@dataclass
class MigrationResult:
    """The outcome of a migration run over a working copy of the repo."""

    manifest: MigrationManifest
    changes: dict[str, tuple[str, str]] = field(default_factory=dict)
    oracle_report: str = ""
    oracle_passed: bool = False

    @property
    def files_migrated(self) -> int:
        return len(self.manifest.by_status("done"))

    @property
    def files_failed(self) -> int:
        return len(self.manifest.by_status("failed"))


@dataclass
class Migration:
    """Run the deprecated-API rename across a repo, file by file, gated and resumable.

    Like :class:`~app.code_agent.CodeAgent`, it operates on a **copy** of the repo so a run is
    idempotent and never mutates the bundled sample. Call :meth:`run` for a fresh job or to resume
    one (pass the ``manifest_path`` of a partial run).
    """

    source_repo: Path

    def plan(self, work_repo: Path) -> MigrationManifest:
        """Discover the files that still use the deprecated API → a fresh manifest."""
        tasks: list[FileTask] = []
        for py in sorted((work_repo / "src").rglob("*.py")):
            rel = str(py.relative_to(work_repo)).replace("\\", "/")
            tasks.append(FileTask(path=rel, status="pending"))
        return MigrationManifest(name=f"{_OLD}->{_NEW}", tasks=tasks)

    def run(self, *, manifest_path: Path | None = None) -> MigrationResult:
        """Execute (or resume) the migration on a working copy; gate every file with the oracle."""
        workdir = Path(tempfile.mkdtemp(prefix="seagent-migrate-"))
        work_repo = workdir / "repo"
        shutil.copytree(self.source_repo, work_repo)
        mpath = manifest_path or (workdir / "manifest.json")
        try:
            return self._run_in(work_repo, mpath)
        finally:
            shutil.rmtree(workdir, ignore_errors=True)

    def _run_in(self, work_repo: Path, manifest_path: Path) -> MigrationResult:
        manifest = (
            MigrationManifest.load(manifest_path)
            if manifest_path.exists()
            else self.plan(work_repo)
        )
        manifest.save(manifest_path)  # checkpoint the plan before touching code

        baseline_assertions = _oracle.count_assertions(work_repo)
        changes: dict[str, tuple[str, str]] = {}

        # Process each pending file independently (the supervisor's fan-out unit). One file's
        # failure is isolated — it is recorded and the rest proceed.
        for task in manifest.pending():
            target = work_repo / task.path
            before = target.read_text(encoding="utf-8") if target.is_file() else ""
            if not needs_migration(before):
                task.status = "skipped"
                task.detail = "no deprecated call sites"
                manifest.save(manifest_path)
                continue

            after = rename_call_sites(before)
            target.write_text(after, encoding="utf-8")

            # Gate THIS file with the oracle before marking it done (CI is the eval).
            report = _oracle.evaluate(work_repo, baseline_assertions=baseline_assertions)
            if report.passed:
                task.status = "done"
                task.detail = "rewrote call sites; oracle green"
                changes[task.path] = (before, after)
            else:
                # Revert the file so a red change never persists; record the failure and move on.
                target.write_text(before, encoding="utf-8")
                task.status = "failed"
                task.detail = "oracle red after rewrite; reverted"
            manifest.save(manifest_path)  # checkpoint after every file → resumable

        final = _oracle.evaluate(work_repo, baseline_assertions=baseline_assertions)
        return MigrationResult(
            manifest=manifest,
            changes=changes,
            oracle_report=final.render(),
            oracle_passed=final.passed,
        )


def build_migration(*, source_repo: Path | str | None = None) -> Migration:
    """Construct a :class:`Migration` over the bundled ``sample_repo/`` (or your own repo)."""
    repo = Path(source_repo) if source_repo is not None else _bundled_repo_root()
    return Migration(source_repo=Path(repo).resolve())
