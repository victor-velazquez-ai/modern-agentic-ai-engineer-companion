"""The CI quality gate — compare a run to a baseline and exit non-zero on regression.

This is what turns an eval set into a *merge gate*. You commit a ``baseline.json`` (the
scores you accept today). On every PR, CI re-runs the suite and calls the gate: if the
overall mean — or any per-tag score — drops more than ``tolerance`` below the baseline, the
gate **fails the build** with a non-zero exit code and a readable diff. Quality becomes a
red check, not a code-review vibe.

Two regression signals, both on by default:

* **Overall** — ``mean_score`` fell below ``baseline.mean_score - tolerance``.
* **Per-tag** — any tag's mean fell below its baseline by more than ``tolerance``. This
  catches the sneaky regression that barely moves the global average while quietly tanking
  ``must-refuse`` or one capability.

``tolerance`` exists because LLM-judge scores have run-to-run noise; set it to a few points
above your judge's observed variance so the gate flags real drops, not jitter. The exit code
(``0`` ok, ``1`` regression, ``2`` usage error) is the contract the tests pin and CI reads.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from .dataset import load_jsonl
from .graders.deterministic import ExactMatch
from .runner import Report, run

EXIT_OK = 0
EXIT_REGRESSION = 1
EXIT_USAGE = 2

DEFAULT_TOLERANCE = 0.02


@dataclass(frozen=True, slots=True)
class Regression:
    """One way the candidate fell below baseline."""

    scope: str  # "overall" or a tag name
    baseline: float
    current: float

    @property
    def drop(self) -> float:
        return self.baseline - self.current

    def __str__(self) -> str:
        return (
            f"{self.scope}: {self.current:.3f} < baseline {self.baseline:.3f} "
            f"(drop {self.drop:.3f})"
        )


@dataclass(frozen=True, slots=True)
class GateResult:
    """The verdict of comparing a report to a baseline."""

    passed: bool
    regressions: tuple[Regression, ...]
    tolerance: float

    @property
    def exit_code(self) -> int:
        return EXIT_OK if self.passed else EXIT_REGRESSION

    def render(self) -> str:
        if self.passed:
            return f"✓ gate passed (tolerance {self.tolerance:.3f}); no regression."
        lines = [f"✗ gate FAILED (tolerance {self.tolerance:.3f}):"]
        lines.extend(f"  - {r}" for r in self.regressions)
        return "\n".join(lines)


def save_baseline(report: Report, path: str | Path) -> None:
    """Write a report's summary to ``path`` as the accepted baseline (pretty JSON)."""

    Path(path).write_text(
        json.dumps(report.to_dict(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def load_baseline(path: str | Path) -> dict[str, Any]:
    """Load a committed baseline summary (as written by :func:`save_baseline`)."""

    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"baseline not found: {p}")
    return json.loads(p.read_text(encoding="utf-8"))


def gate(
    report: Report,
    baseline: Mapping[str, Any],
    *,
    tolerance: float = DEFAULT_TOLERANCE,
    check_tags: bool = True,
) -> GateResult:
    """Compare a fresh ``report`` to a ``baseline`` summary; flag regressions.

    A *new* tag (present now, absent in the baseline) is never a regression — you can add
    cases without tripping the gate. A *missing* tag (in baseline, gone now) is likewise not
    flagged here; dataset shrinkage is a dataset-review concern, not a quality regression.
    """

    regressions: list[Regression] = []

    base_overall = float(baseline.get("mean_score", 0.0))
    if report.mean_score < base_overall - tolerance:
        regressions.append(Regression("overall", base_overall, report.mean_score))

    if check_tags:
        base_tags: Mapping[str, float] = baseline.get("tag_scores", {})
        current_tags = report.tag_scores()
        for tag, base_score in base_tags.items():
            if tag not in current_tags:
                continue
            cur = current_tags[tag]
            if cur < float(base_score) - tolerance:
                regressions.append(Regression(tag, float(base_score), cur))

    return GateResult(
        passed=not regressions,
        regressions=tuple(regressions),
        tolerance=tolerance,
    )


# --------------------------------------------------------------------------------------
# CLI entrypoint — this is what a CI step invokes.
# --------------------------------------------------------------------------------------

def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="eval-harness-gate",
        description="Score a dataset and gate the build against a baseline.",
    )
    p.add_argument("dataset", type=Path, help="path to a golden-set .jsonl")
    p.add_argument(
        "--baseline",
        type=Path,
        required=True,
        help="baseline JSON to compare against (write one first with --update).",
    )
    p.add_argument(
        "--tolerance",
        type=float,
        default=DEFAULT_TOLERANCE,
        help=f"allowed drop before failing (default {DEFAULT_TOLERANCE}).",
    )
    p.add_argument(
        "--threshold",
        type=float,
        default=0.5,
        help="per-case pass bar for the report (default 0.5).",
    )
    p.add_argument(
        "--update",
        action="store_true",
        help="run, then OVERWRITE the baseline with the new scores and exit 0.",
    )
    p.add_argument(
        "--no-tags",
        action="store_true",
        help="gate on the overall mean only (skip per-tag regression checks).",
    )
    return p


def _identity_candidate(value: Any) -> Any:
    """Default candidate for the CLI: echo the input.

    The CLI is a *thin demo wiring* — real use imports :func:`gate` and passes your own
    candidate + grader. Echoing the input means a dataset whose ``expected`` equals its
    ``input`` scores 1.0, which is enough to exercise the gate end-to-end from the shell.
    """

    return value


def main(argv: list[str] | None = None) -> int:
    """CLI: ``eval-harness-gate dataset.jsonl --baseline baseline.json``.

    Returns the process exit code (``0`` ok / ``1`` regression / ``2`` usage), so it can be
    used directly as ``sys.exit(main())`` and as a CI gate step.
    """

    # Print the report glyphs (✓/✗) on any console, including Windows cp1252 terminals.
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
        except (AttributeError, ValueError):  # pragma: no cover - non-reconfigurable
            pass

    parser = _build_parser()
    args = parser.parse_args(argv)

    if not args.dataset.exists():
        parser.error(f"dataset not found: {args.dataset}")

    cases = load_jsonl(args.dataset)
    report = run(
        _identity_candidate,
        cases,
        ExactMatch(),
        threshold=args.threshold,
    )
    print(report.render())

    if args.update:
        save_baseline(report, args.baseline)
        print(f"\nBaseline written to {args.baseline}.")
        return EXIT_OK

    if not args.baseline.exists():
        print(
            f"\nNo baseline at {args.baseline}. Create one with --update.",
            file=sys.stderr,
        )
        return EXIT_USAGE

    result = gate(
        report,
        load_baseline(args.baseline),
        tolerance=args.tolerance,
        check_tags=not args.no_tags,
    )
    print()
    print(result.render())
    return result.exit_code


if __name__ == "__main__":  # pragma: no cover
    # Honour the repo-wide MOCK default for messaging; the CLI itself never spends.
    os.environ.setdefault("COMPANION_MOCK", "1")
    raise SystemExit(main())
