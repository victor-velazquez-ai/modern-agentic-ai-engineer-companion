"""demo.py — the software-engineering agent, end to end, free and offline.

Run it::

    python demo.py            # MOCK mode (the default): no API key, no spend, deterministic
    COMPANION_MOCK=0 python demo.py   # live path — requires a wired ModelPort + key (not bundled)

What it shows, in order, **composing five pattern blueprints and never auto-merging**:

1. **Fix a failing test (agent-loop + mcp-server + eval-harness + observability).** The
   ``CodeAgent`` drives the agent loop with sandboxed, least-privilege tools, proposes a one-token
   fix for the ``slugify`` bug, and the **oracle** (CI-is-the-eval) verifies the suite goes green —
   *and* that no assertion was deleted to fake it. On green, it emits a PR for human review.

2. **The oracle catches a cheating "fix".** We feed the agent a model that "fixes" the test by
   deleting its assertion; the assertion-deletion guard turns the oracle red and the change is
   rejected. *Guard the oracle itself.*

3. **Migrate a deprecated API across the repo (multi-agent-supervisor + eval-harness).** The
   ``Migration`` rewrites ``legacy_clean`` → ``normalize`` at every call site, file by file, behind
   a **resumable manifest**, gating each file with the oracle. It emits a second PR.

Nothing here merges anything: every result is a :class:`~app.pr.PullRequest` awaiting human review.
The bundled ``sample_repo/`` is never mutated — each step runs on a throwaway working copy.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

# Default to offline MOCK before importing anything that reads the switch.
os.environ.setdefault("COMPANION_MOCK", "1")

# --- composition seam: make the sibling pattern blueprints + this solution importable ------------
_SOLUTION_ROOT = Path(__file__).resolve().parent
if str(_SOLUTION_ROOT) not in sys.path:
    sys.path.insert(0, str(_SOLUTION_ROOT))

from _blueprints import ensure_blueprints_on_path  # noqa: E402

ensure_blueprints_on_path()

from agent_loop import MockModel, ToolCall, assistant  # noqa: E402
from app import PullRequest, build_agent, build_migration  # noqa: E402
from app.code_agent import _last_tool_text  # noqa: E402  (reuse the transcript reader)


# ------------------------------------------------------------------------------------------------
# A second, adversarial mock model: it "fixes" the test by deleting an assertion. The oracle's
# assertion-deletion guard must reject it. This is the "guard the oracle" demonstration.
# ------------------------------------------------------------------------------------------------

def _cheating_script() -> list[object]:
    """A model that tries to make tests pass by weakening them (deleting an assertion)."""

    def _delete_assertion(transcript: list[object]) -> object:
        test_src = _last_tool_text(transcript, "read_file") or ""
        # Remove the multi-word assertion that is red — the lazy way to "go green".
        weakened = test_src.replace(
            '    assert slugify("Hello World") == "hello-world"',
            "    pass  # assertion deleted to fake a pass",
        )
        return assistant(
            text="I'll just remove the failing assertion.",
            tool_calls=(
                ToolCall(
                    id="w1",
                    name="write_file",
                    arguments={"path": "tests/test_slugify.py", "content": weakened},
                ),
            ),
        )

    return [
        assistant(
            text="Reading the failing test.",
            tool_calls=(
                ToolCall(
                    id="t1",
                    name="read_file",
                    arguments={"path": "tests/test_slugify.py"},
                ),
            ),
        ),
        _delete_assertion,
        assistant(text="Done (cheating)."),
    ]


def _hr(title: str) -> None:
    print("\n" + "#" * 78)
    print(f"# {title}")
    print("#" * 78)


def main() -> int:
    # The oracle/PR renderers use ✓/✗ glyphs; make them printable on cp1252 consoles too.
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
        except (AttributeError, ValueError):  # pragma: no cover - non-reconfigurable stream
            pass

    mock = os.getenv("COMPANION_MOCK", "1").strip().lower() not in {"0", "false", "no"}
    print(f"software-engineering-agent demo  (MOCK={'on' if mock else 'off'}, no auto-merge)")

    # --- 1) Fix the slugify bug, gated by the oracle, packaged as a PR ---------------------------
    _hr("1) Code agent: fix a failing test (agent-loop + mcp-server + eval-harness)")
    agent = build_agent()  # default = deterministic slugify-fix script on the bundled sample_repo
    attempt = agent.fix(target_rel="src/textkit.py")
    print(attempt.oracle_report)
    if attempt.accepted:
        pr = PullRequest.from_changes(
            title="Fix slugify: insert separator between words",
            summary=(
                "slugify() joined words with an empty string, dropping the separator. This change "
                "uses sep.join(words). Verified by the oracle (tests green, no assertions removed)."
            ),
            changes=attempt.changes,
            oracle_passed=True,
            oracle_report=attempt.oracle_report,
            labels=("bug", "agent-generated", "needs-human-review"),
        )
        print()
        print(pr.render())
        assert pr.auto_merge is False, "a PR must never auto-merge"
    else:
        print("Agent did not produce an accepted fix (oracle stayed red).")
        return 1

    # --- 2) The oracle catches a cheating 'fix' -------------------------------------------------
    _hr("2) Guard the oracle: a 'fix' that deletes an assertion is REJECTED")
    cheat = build_agent(model=lambda: MockModel(_cheating_script()))
    cheat_attempt = cheat.fix(target_rel="tests/test_slugify.py")
    print(cheat_attempt.oracle_report)
    if cheat_attempt.accepted:
        print("UNEXPECTED: the cheating change was accepted — the guard failed!")
        return 1
    print("\nRejected as expected: the assertion-deletion guard kept the test contract honest.")

    # --- 3) Resumable, oracle-gated migration across the repo -----------------------------------
    _hr("3) Migration: rename legacy_clean -> normalize across the repo (resumable manifest)")
    migration = build_migration()
    result = migration.run()
    print(
        f"migrated {result.files_migrated} file(s), "
        f"{result.files_failed} failed, "
        f"manifest tasks: {len(result.manifest.tasks)}"
    )
    for task in result.manifest.tasks:
        print(f"  - {task.path:<24} {task.status:<8} {task.detail}")
    print()
    print(result.oracle_report)

    if result.changes:
        mpr = PullRequest.from_changes(
            title="Migrate deprecated legacy_clean() to normalize()",
            summary=(
                "Mechanical rename of the deprecated legacy_clean call sites to normalize, applied "
                "file by file behind a resumable manifest. Each file was gated by the oracle; "
                "behaviour is unchanged (the migration tests stay green)."
            ),
            changes=result.changes,
            oracle_passed=result.oracle_passed,
            oracle_report=result.oracle_report,
            labels=("migration", "agent-generated", "needs-human-review"),
        )
        print()
        print(mpr.render())
        assert mpr.auto_merge is False, "a migration PR must never auto-merge"

    _hr("Done — two PRs proposed, zero merges. A human owns the merge.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
