"""pr — the structured diff a *human* reviews and merges (Ch 15, 20).

The book's thesis, made literal: **the AI writes the code, you own the merge.** Whatever the agent
or the migration produces, it never lands on its own. It is packaged here as a :class:`PullRequest`
— a title, a body that explains the change and shows the oracle's green verdict, and a real unified
diff per file — and handed back for human review. There is **no ``merge()`` that writes to a
protected branch**; this module only *describes* a change.

Why a dedicated object and not "just print a diff"? Because a PR is the audit surface. It records:

* the **before/after** of every file as a standard unified diff (reviewable in any tool),
* the **verification evidence** (the oracle was green when this diff was produced), and
* a machine-readable summary (files touched, lines changed) for dashboards and gates.

Nothing here imports a sibling blueprint — a PR is plain data. The agent (``code_agent``) and the
migration (``migrate``) build one; the demo prints it; a real adapter would open it on GitHub/GitLab
via their API. That adapter is the *only* place credentials live, and it is out of scope here.
"""

from __future__ import annotations

import difflib
from dataclasses import dataclass, field


def unified_diff(path: str, before: str, after: str) -> str:
    """Return a standard unified diff for one file's ``before`` → ``after`` content.

    Uses :mod:`difflib` (stdlib) so the output is the same format ``git diff`` and every review
    tool understands. An empty string means the file is unchanged — callers skip those so a PR only
    carries files that actually moved.
    """
    before_lines = before.splitlines(keepends=True)
    after_lines = after.splitlines(keepends=True)
    diff = difflib.unified_diff(
        before_lines,
        after_lines,
        fromfile=f"a/{path}",
        tofile=f"b/{path}",
        lineterm="",
    )
    return "\n".join(diff)


@dataclass(frozen=True)
class FileDiff:
    """The change to one file: its repo-relative path and a unified diff."""

    path: str
    before: str = field(repr=False, default="")
    after: str = field(repr=False, default="")

    @property
    def diff(self) -> str:
        return unified_diff(self.path, self.before, self.after)

    @property
    def changed(self) -> bool:
        return self.before != self.after

    @property
    def added_lines(self) -> int:
        return sum(
            1
            for line in self.diff.splitlines()
            if line.startswith("+") and not line.startswith("+++")
        )

    @property
    def removed_lines(self) -> int:
        return sum(
            1
            for line in self.diff.splitlines()
            if line.startswith("-") and not line.startswith("---")
        )


@dataclass
class PullRequest:
    """A proposed change, packaged for human review. **Never auto-merges.**

    Build one with :meth:`from_changes` from a set of before/after file contents plus the oracle
    verdict that gated them. The object is pure data: rendering it (``render``) or serialising it
    (``to_dict``) is all this blueprint does. Opening it against a real forge — and therefore the
    only place a token is needed — is an adapter a caller supplies; it is deliberately absent so the
    blueprint spends nothing and merges nothing.
    """

    title: str
    summary: str
    files: tuple[FileDiff, ...] = ()
    oracle_passed: bool = False
    oracle_report: str = ""
    labels: tuple[str, ...] = ()
    # A PR is a *proposal*. This flag is informational and always False here: the merge decision is
    # a human's, made outside this process. It exists so a downstream tool can assert on it.
    auto_merge: bool = False

    @classmethod
    def from_changes(
        cls,
        *,
        title: str,
        summary: str,
        changes: dict[str, tuple[str, str]],
        oracle_passed: bool,
        oracle_report: str = "",
        labels: tuple[str, ...] = (),
    ) -> "PullRequest":
        """Build a PR from ``{path: (before, after)}`` changes and the oracle verdict.

        Only files that actually changed are included. ``oracle_passed`` is recorded verbatim — a
        PR is allowed to carry a *red* verdict (so a human can see a rejected attempt), but the
        agents in this blueprint only ever emit a PR once the oracle is green.
        """
        diffs = tuple(
            FileDiff(path=path, before=before, after=after)
            for path, (before, after) in sorted(changes.items())
            if before != after
        )
        return cls(
            title=title,
            summary=summary,
            files=diffs,
            oracle_passed=oracle_passed,
            oracle_report=oracle_report,
            labels=labels,
        )

    @property
    def files_changed(self) -> int:
        return len(self.files)

    @property
    def added_lines(self) -> int:
        return sum(f.added_lines for f in self.files)

    @property
    def removed_lines(self) -> int:
        return sum(f.removed_lines for f in self.files)

    @property
    def is_empty(self) -> bool:
        return self.files_changed == 0

    def to_dict(self) -> dict[str, object]:
        """A machine-readable summary (what a dashboard or a gate would consume)."""
        return {
            "title": self.title,
            "summary": self.summary,
            "files_changed": self.files_changed,
            "added_lines": self.added_lines,
            "removed_lines": self.removed_lines,
            "oracle_passed": self.oracle_passed,
            "labels": list(self.labels),
            "auto_merge": self.auto_merge,
            "files": [f.path for f in self.files],
        }

    def render(self) -> str:
        """A reviewable PR: header, verification evidence, then the per-file unified diffs."""
        verdict = "GREEN (oracle passed)" if self.oracle_passed else "RED (oracle did NOT pass)"
        lines = [
            f"PULL REQUEST: {self.title}",
            "=" * 72,
            self.summary.strip(),
            "",
            f"Verification : {verdict}",
            f"Files changed: {self.files_changed}  (+{self.added_lines} / -{self.removed_lines})",
            f"Labels       : {', '.join(self.labels) or '(none)'}",
            "Merge        : awaiting human review — this tool NEVER auto-merges.",
        ]
        if self.oracle_report:
            lines += ["", "Oracle verdict", "-" * 72, self.oracle_report.rstrip()]
        if self.files:
            lines += ["", "Diff", "-" * 72]
            for f in self.files:
                lines.append(f.diff)
                lines.append("")
        else:
            lines += ["", "(no file changes — nothing to review)"]
        return "\n".join(lines).rstrip() + "\n"
