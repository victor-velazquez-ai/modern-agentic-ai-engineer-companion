"""Retry-and-repair on invalid extraction output (Ch 15).

A first-pass extraction is wrong often enough that "validate and give up" throws away money.
The cheap, robust fix is the same one the ``agent-loop`` blueprint uses for malformed tool
calls: hand the model **its own output plus the precise validation errors** and ask it to
return a corrected object. Most failures (a date in the wrong format, a number with a stray
``$``, a missing field the OCR text actually contains) clear in one repair turn.

This module is the *policy*, kept pure and free of any model SDK so it is unit-testable:

* :func:`build_repair_prompt` turns a :class:`~pipeline.schema.ValidationError` into the exact
  instruction the next turn should carry.
* :func:`attempt_repairs` runs the **validate → (on failure) repair → re-validate** loop a
  bounded number of times against a ``reextract`` callable, returning the first value that
  validates or the final error if the budget runs out.

The ``reextract`` callable is the seam to the model: in :mod:`pipeline.extract` it is backed by
the ``agent-loop`` (mock by default, an ``llm-gateway`` port live). Here it is just
``(prompt) -> raw_payload``, so a test can drive the whole repair policy with a scripted stub
and no spend.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from .schema import Invoice, ValidationError, validate_invoice

# The seam to "ask the model again": given a repair instruction, return a fresh decoded payload.
ReExtractFn = Callable[[str], Any]

# How many repair turns we allow before dead-lettering. Matches the agent-loop RetryPolicy
# philosophy: bound the flailing so one stubborn document can't burn the budget (Ch 12).
DEFAULT_MAX_REPAIRS = 2


def build_repair_prompt(raw: Any, error: ValidationError) -> str:
    """Compose the instruction for a repair turn from the bad output and its errors.

    The errors are listed verbatim because they are *field-addressed*
    ("line_items[1].amount: expected number, got 'N/A'"), which is what lets the model fix the
    exact field instead of re-guessing the whole object.
    """
    bullet_errors = "\n".join(f"  - {e}" for e in error.errors)
    return (
        "Your previous extraction did not pass schema validation.\n"
        f"Previous output:\n{raw!r}\n\n"
        "Validation errors (fix every one):\n"
        f"{bullet_errors}\n\n"
        "Return a corrected JSON object that satisfies the invoice schema. "
        "Use only values supported by the document text; do not invent fields."
    )


@dataclass(frozen=True, slots=True)
class RepairOutcome:
    """The result of the repair loop: the validated invoice (or the final failure) + how it got there."""

    invoice: Invoice | None
    attempts: int  # total extraction passes, including the first (1 = passed first try)
    repaired: bool  # True if it took at least one repair turn to succeed
    error: ValidationError | None  # set iff invoice is None (exhausted the budget)

    @property
    def ok(self) -> bool:
        return self.invoice is not None


def attempt_repairs(
    raw: Any,
    reextract: ReExtractFn,
    *,
    max_repairs: int = DEFAULT_MAX_REPAIRS,
    on_event: Callable[[str, dict], None] | None = None,
) -> RepairOutcome:
    """Validate ``raw``; on failure, re-extract-and-repair up to ``max_repairs`` times.

    Parameters
    ----------
    raw:
        The first-pass decoded extraction payload to validate.
    reextract:
        ``(repair_prompt) -> raw_payload`` — the model seam. Called once per repair turn.
    max_repairs:
        Maximum repair turns *after* the first validation. ``0`` disables repair (validate once).
    on_event:
        Optional observer ``(name, payload)`` for tracing each ``"validate"`` / ``"repair"`` step
        — the hook :mod:`pipeline.extract` forwards into the ``observability-stack`` tracer.

    Returns
    -------
    RepairOutcome
        ``ok`` with the validated :class:`Invoice`, or a failed outcome carrying the final
        :class:`ValidationError` (the signal the caller turns into a dead-letter).
    """
    attempt = 1
    current = raw
    last_error: ValidationError | None = None

    while True:
        try:
            invoice = validate_invoice(current)
            _emit(on_event, "validate", {"attempt": attempt, "ok": True})
            return RepairOutcome(
                invoice=invoice,
                attempts=attempt,
                repaired=attempt > 1,
                error=None,
            )
        except ValidationError as err:
            last_error = err
            _emit(on_event, "validate", {"attempt": attempt, "ok": False, "errors": err.errors})

        if attempt - 1 >= max_repairs:  # repairs are the turns *after* the first validate
            return RepairOutcome(invoice=None, attempts=attempt, repaired=attempt > 1, error=last_error)

        # --- repair turn: feed the errors back to the model and re-extract -----------------
        prompt = build_repair_prompt(current, last_error)
        _emit(on_event, "repair", {"attempt": attempt + 1})
        current = reextract(prompt)
        attempt += 1


def _emit(on_event: Callable[[str, dict], None] | None, name: str, payload: dict) -> None:
    if on_event is not None:
        on_event(name, payload)
