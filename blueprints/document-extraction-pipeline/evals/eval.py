"""Golden-set accuracy gate — pick the cheapest model that clears the bar (eval-harness · Ch 22).

An extraction pipeline lives or dies on **accuracy**, and accuracy is a number you measure
against labeled data, not a vibe. This module composes the **eval-harness** blueprint to:

1. load the labeled golden set (``invoices_golden.jsonl``);
2. run the *real* extractor (:func:`pipeline.extract.extract_document`) as the candidate over
   each document;
3. grade each produced record **field-by-field** against the human label with a custom
   :class:`FieldAccuracy` grader (partial credit per correct field);
4. gate the mean accuracy against an **explicit bar** and, given a menu of models with prices,
   pick the **cheapest model that still clears the bar** — the Ch 22 cost/quality decision made
   honestly instead of by reputation.

Everything runs offline and free (``COMPANION_MOCK=1``). The "model menu" here is illustrative:
each entry is a (name, price, accuracy) the harness would *measure* on the live path; offline we
score the one mock extractor and show the selection logic. Swap in real model runs and the same
``run`` → ``Report`` → selection code is unchanged.

Run it::

    python evals/eval.py            # score + gate against the default 0.90 accuracy bar
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from pathlib import Path

# Make the sibling pipeline package importable whether run as a script or a module, and wire the
# pattern blueprints (eval-harness) onto sys.path via the pipeline's compose seam.
_HERE = Path(__file__).resolve().parent
_PKG_ROOT = _HERE.parent  # document-extraction-pipeline/
if str(_PKG_ROOT) not in sys.path:
    sys.path.insert(0, str(_PKG_ROOT))

from pipeline import _compose  # noqa: E402,F401  -- side effect: eval-harness onto sys.path
from pipeline.extract import extract_document  # noqa: E402

from eval_harness import (  # noqa: E402
    Case,
    GradeResult,
    Report,
    gate,
    load_jsonl,
    run,
)

GOLDEN_PATH = _HERE / "invoices_golden.jsonl"

# The accuracy bar finance signs off on, in writing (PLAN: "set the accepted error rate up
# front"). A record must reproduce >= this fraction of its labeled fields, on average, to ship.
DEFAULT_ACCURACY_BAR = 0.90

# The scalar fields we score for accuracy (line items are graded separately by reconciliation in
# the live confidence layer; here we hold the eval focused on the labeled header fields).
_SCORED_FIELDS = ("invoice_number", "vendor", "invoice_date", "currency", "total")


@dataclass(frozen=True, slots=True)
class FieldAccuracy:
    """Grade an extracted record against a labeled one, field by field (partial credit).

    * ``expected is None`` is the **must-dead-letter** contract: the correct output is *no
      record*. The candidate passes iff it produced ``None`` (the pipeline dead-lettered) and
      fails (score 0) if it produced a record anyway — auto-posting a doc we should have refused
      is the expensive error, so it scores zero, not partial credit.
    * Otherwise the score is the fraction of ``_SCORED_FIELDS`` that match the label. Numbers
      compare within a small tolerance; strings compare case-folded/stripped.
    """

    fields: tuple[str, ...] = _SCORED_FIELDS
    number_tol: float = 0.005

    def grade(self, expected, actual) -> GradeResult:  # type: ignore[no-untyped-def]
        if expected is None:
            if actual is None:
                return GradeResult.ok("correctly produced no record (dead-lettered)")
            return GradeResult.fail("produced a record for a must-dead-letter document")
        if not isinstance(actual, dict):
            return GradeResult.fail(f"expected a record, got {type(actual).__name__}")

        hits = 0
        misses: list[str] = []
        for key in self.fields:
            if self._match(expected.get(key), actual.get(key)):
                hits += 1
            else:
                misses.append(key)
        score = hits / len(self.fields)
        if score == 1.0:
            return GradeResult.ok(f"all {len(self.fields)} fields match")
        return GradeResult(score, f"mismatched fields: {misses}")

    def _match(self, want, got) -> bool:  # type: ignore[no-untyped-def]
        if isinstance(want, (int, float)) and isinstance(got, (int, float)):
            return abs(float(want) - float(got)) <= self.number_tol
        return str(want).strip().casefold() == str(got).strip().casefold()


def _candidate(source) -> dict | None:  # type: ignore[no-untyped-def]
    """The system under test: run the real extractor, return its record or ``None``.

    ``None`` means the pipeline (correctly or not) produced no validated record — the signal the
    :class:`FieldAccuracy` grader checks the must-dead-letter cases against. We special-case the
    one repairable golden doc by supplying its corrected source, mirroring what a live model
    would emit from the repair prompt.
    """
    repaired = _REPAIRED_SOURCES.get(source)
    result = extract_document(source, repaired_source=repaired, max_repairs=2)
    if not result.ok or result.outcome.invoice is None:
        return None
    return result.outcome.invoice.to_record()


# Offline determinism for the one repairable golden case: the corrected source a repair turn
# re-reads. On the live path the model produces this itself; here we map source -> corrected.
_REPAIRED_SOURCES: dict[str, str] = {
    (
        "invoice_number: INV-1002\nvendor: Globex Logistics\ninvoice_date: 03/05/2026\n"
        "currency: USD\ntotal: $1,450.00\nLINE: Freight forwarding | 1 | 1200.00 | 1200.00\n"
        "LINE: Customs handling | 1 | 250.00 | 250.00"
    ): (
        "invoice_number: INV-1002\nvendor: Globex Logistics\ninvoice_date: 2026-03-05\n"
        "currency: USD\ntotal: 1450.00\nLINE: Freight forwarding | 1 | 1200.00 | 1200.00\n"
        "LINE: Customs handling | 1 | 250.00 | 250.00"
    )
}


@dataclass(frozen=True, slots=True)
class ModelOption:
    """One candidate model on the menu: a name, its price ($/1M output tokens), measured accuracy."""

    name: str
    price_per_mtok: float
    accuracy: float


def pick_cheapest_passing(options, bar: float) -> "ModelOption | None":  # type: ignore[no-untyped-def]
    """Pick the **cheapest** model whose measured accuracy clears ``bar`` (Ch 22).

    The whole point of an eval-harness in a high-volume pipeline: do not pay for the smartest
    model when a cheaper one already clears the accuracy bar. Returns ``None`` if nothing passes
    — the signal to either relax nothing and keep humans in the loop, or improve the prompt/schema.
    """
    passing = [o for o in options if o.accuracy >= bar]
    if not passing:
        return None
    return min(passing, key=lambda o: o.price_per_mtok)


def evaluate(bar: float = DEFAULT_ACCURACY_BAR) -> Report:
    """Score the extractor over the golden set and return the eval-harness :class:`Report`."""
    cases: list[Case] = load_jsonl(GOLDEN_PATH)
    # A field is "passed" at >= the bar; partial-credit scores still aggregate into the mean.
    return run(_candidate, cases, FieldAccuracy(), threshold=bar)


def main(argv: list[str] | None = None) -> int:
    """CLI: score the golden set, gate on the accuracy bar, and print the model selection."""
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
        except (AttributeError, ValueError):  # pragma: no cover
            pass

    bar = DEFAULT_ACCURACY_BAR
    report = evaluate(bar)
    print(report.render())

    # Gate: treat the measured mean as the baseline-free bar. (A committed baseline.json + the
    # eval-harness `gate()` is the CI version; here we gate directly against the explicit bar.)
    baseline = {"mean_score": bar, "tag_scores": {}}
    verdict = gate(report, baseline, tolerance=0.0, check_tags=False)
    print()
    print(verdict.render())

    # The Ch 22 decision: cheapest model that clears the bar. Offline the menu is illustrative;
    # the measured mean stands in for the one mock extractor's accuracy.
    measured = report.mean_score
    menu = [
        ModelOption("claude-haiku-4", price_per_mtok=4.0, accuracy=measured),
        ModelOption("claude-sonnet-4", price_per_mtok=15.0, accuracy=min(1.0, measured + 0.03)),
        ModelOption("claude-opus-4", price_per_mtok=75.0, accuracy=min(1.0, measured + 0.05)),
    ]
    chosen = pick_cheapest_passing(menu, bar)
    print()
    if chosen is not None:
        print(
            f"Model selection: '{chosen.name}' clears the {bar:.0%} bar at "
            f"${chosen.price_per_mtok:.2f}/1M output tokens (cheapest passing)."
        )
    else:
        print(
            f"Model selection: no model on the menu clears the {bar:.0%} bar "
            "-- keep humans in the loop / improve the prompt+schema before lowering it."
        )

    return verdict.exit_code


if __name__ == "__main__":  # pragma: no cover
    os.environ.setdefault("COMPANION_MOCK", "1")
    raise SystemExit(main())
