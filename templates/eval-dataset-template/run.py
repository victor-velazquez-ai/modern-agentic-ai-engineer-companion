"""Run the eval set: load cases -> call target() -> score -> print table.

Usage:
    python run.py                          # scores datasets/golden.jsonl
    python run.py datasets/adversarial.jsonl
    python run.py datasets/golden.jsonl datasets/adversarial.jsonl

Exit code:
    0  every case passed (and threshold met)
    1  one or more cases failed (this is what CI gates on)

This is a **drop-in CI quality gate** — `github-actions-ci`'s eval-gate job runs
exactly this entrypoint. By default it runs with ``COMPANION_MOCK=1`` (free,
offline, deterministic) so PR CI costs nothing.

NO business logic lives here. The one thing you MUST fill in is ``target()`` —
the function that calls *your* LLM feature. Everything else (loading, scoring,
reporting, the exit code) is wired up for you.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any, Iterable

# Load .env if python-dotenv is available (optional; only matters in live mode).
try:
    from dotenv import load_dotenv

    load_dotenv()
except Exception:  # pragma: no cover - dotenv is optional
    pass

from scorer import Score, mock_enabled, score_case

HERE = Path(__file__).resolve().parent
DEFAULT_DATASET = HERE / "datasets" / "golden.jsonl"

# Fraction of cases that must pass for the run to succeed (CI gate threshold).
# TODO: tune to your bar. 1.0 = every case must pass; 0.9 = allow 10% to fail.
PASS_THRESHOLD = float(os.environ.get("EVAL_PASS_THRESHOLD", "1.0"))


# ---------------------------------------------------------------------------
# THE ONE THING YOU FILL IN
# ---------------------------------------------------------------------------


def target(case_input: Any) -> Any:
    """Run the system under test on one case's ``input`` and return its output.

    >>> TODO: replace this stub with a call to YOUR agent / prompt / pipeline. <<<

    The stub below is an *echo* so the template runs end-to-end out of the box
    (and so the suite has something deterministic to score in MOCK mode). It has
    no real behavior — swap it for something like:

        from my_app import answer
        return answer(case_input)          # str in, str out

    Keep this function pure and side-effect-free where you can; the runner calls
    it once per case. Respect ``mock_enabled()`` if your target hits a model:
    return a canned response when mock mode is on so CI stays free.
    """
    # --- echo stub (delete me) ------------------------------------------------
    if isinstance(case_input, dict):
        return case_input.get("question") or json.dumps(case_input)
    return str(case_input)
    # --- end echo stub --------------------------------------------------------


# ---------------------------------------------------------------------------
# Dataset loading
# ---------------------------------------------------------------------------


def load_cases(path: Path) -> list[dict]:
    """Read a JSONL dataset into a list of case dicts."""
    cases: list[dict] = []
    with path.open(encoding="utf-8") as fh:
        for lineno, raw in enumerate(fh, start=1):
            raw = raw.strip()
            if not raw:
                continue  # tolerate blank lines
            try:
                cases.append(json.loads(raw))
            except json.JSONDecodeError as exc:
                raise SystemExit(f"{path}:{lineno}: invalid JSON — {exc}") from exc
    return cases


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------


def _print_table(rows: list[tuple[str, Score]]) -> None:
    id_w = max((len(r[0]) for r in rows), default=2)
    id_w = max(id_w, len("ID"))
    print(f"{'PASS':<5} {'ID':<{id_w}}  RATIONALE")
    print(f"{'-' * 5} {'-' * id_w}  {'-' * 40}")
    for case_id, sc in rows:
        mark = "PASS " if sc.passed else "FAIL "
        print(f"{mark:<5} {case_id:<{id_w}}  {sc.rationale}")


def _print_tag_breakdown(per_tag: dict[str, list[bool]]) -> None:
    if not per_tag:
        return
    print("\nPer-tag breakdown:")
    for tag in sorted(per_tag):
        results = per_tag[tag]
        passed = sum(results)
        total = len(results)
        print(f"  {tag:<20} {passed}/{total}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def run(paths: Iterable[Path]) -> int:
    rows: list[tuple[str, Score]] = []
    per_tag: dict[str, list[bool]] = {}

    for path in paths:
        for case in load_cases(path):
            actual = target(case.get("input"))
            sc = score_case(case, actual)
            rows.append((case.get("id", "<no-id>"), sc))
            for tag in case.get("tags", []):
                per_tag.setdefault(tag, []).append(sc.passed)

    if not rows:
        print("No cases found.")
        return 1

    _print_table(rows)
    _print_tag_breakdown(per_tag)

    passed = sum(1 for _, sc in rows if sc.passed)
    total = len(rows)
    rate = passed / total
    mode = "MOCK" if mock_enabled() else "LIVE"
    print(
        f"\n[{mode}] {passed}/{total} passed "
        f"({rate:.0%}); threshold {PASS_THRESHOLD:.0%}"
    )

    return 0 if rate >= PASS_THRESHOLD else 1


def main(argv: list[str]) -> int:
    args = argv[1:]
    paths = [Path(a) for a in args] if args else [DEFAULT_DATASET]
    for p in paths:
        if not p.exists():
            print(f"Dataset not found: {p}", file=sys.stderr)
            return 1
    return run(paths)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
