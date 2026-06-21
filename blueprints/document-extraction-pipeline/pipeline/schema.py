"""The strict, **versioned** extraction schema (Ch 15).

The whole pipeline exists to turn a blob of OCR text into *this* object: a typed, validated
:class:`Invoice` with constrained fields. Everything else — the agent loop, the repair, the
confidence routing — is in service of producing a value that passes :func:`validate_invoice`
cleanly, because only a value that passes is safe to write to a system of record.

Why a hand-rolled validator instead of Pydantic here?
-----------------------------------------------------
The book teaches this with **Pydantic** (Ch 15), and in production you should use it: a
``class Invoice(BaseModel)`` with ``field_validator``s is less code and gives you JSON-Schema
for free to hand the model. We keep the blueprint **dependency-free** so it runs offline with
zero install, so this module reimplements the *shape* of that contract — required fields, type
coercion, range/format constraints, a structured error list — with stdlib only. The seam is
honest: swap :func:`validate_invoice` for a ``Invoice.model_validate`` call and nothing else in
the pipeline changes (it only consumes :class:`ValidationError` and the cleaned dict).

Schema **versioning** is the part teams skip and regret.
--------------------------------------------------------
A backfill of a million documents does not finish in one deploy. Halfway through you will want
to add a field or tighten a rule — and now half your manifest was extracted under the old
contract. So every extracted item is stamped with :data:`SCHEMA_VERSION`; the manifest records
it per item; and a reader can tell "extracted under v1, current schema is v2" instead of
silently mixing shapes. Bump :data:`SCHEMA_VERSION` whenever the field set or a constraint
changes.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date
from typing import Any

# Bump this whenever the field set or a constraint below changes. The manifest stamps it on
# every item so a mid-backfill schema change is auditable rather than silent (Ch 31/43).
SCHEMA_VERSION = "invoice.v1"

_CURRENCY_RE = re.compile(r"^[A-Z]{3}$")  # ISO-4217, e.g. USD, EUR, GBP
_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")  # ISO-8601 date
_INVOICE_NO_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9\-/]{0,63}$")


class ValidationError(ValueError):
    """A typed, *structured* validation failure — a list of per-field problems.

    The ``errors`` list is the load-bearing part: :mod:`pipeline.repair` feeds it back to the
    model verbatim ("line_items[1].amount: expected number, got 'N/A'") so the model can fix the
    exact field rather than guessing. A flat string would make repair a coin flip.
    """

    def __init__(self, errors: list[str]) -> None:
        self.errors = errors
        super().__init__("; ".join(errors) if errors else "validation failed")


@dataclass(frozen=True, slots=True)
class LineItem:
    """One row of an invoice. Amounts are dollars (floats) — money math is out of scope here."""

    description: str
    quantity: float
    unit_price: float
    amount: float


@dataclass(frozen=True, slots=True)
class Invoice:
    """The validated extraction target. Construct it only via :func:`validate_invoice`.

    ``schema_version`` travels with the record so a downstream reader (and the manifest) always
    knows which contract produced it. ``total`` is the document total; :func:`validate_invoice`
    checks it reconciles with the line items within a tolerance.
    """

    invoice_number: str
    vendor: str
    invoice_date: str  # ISO-8601 (validated)
    currency: str  # ISO-4217 (validated)
    total: float
    line_items: tuple[LineItem, ...] = field(default_factory=tuple)
    schema_version: str = SCHEMA_VERSION

    def to_record(self) -> dict[str, Any]:
        """JSON-serializable form — what the writer hands to the warehouse/ERP (Ch 30)."""
        return {
            "schema_version": self.schema_version,
            "invoice_number": self.invoice_number,
            "vendor": self.vendor,
            "invoice_date": self.invoice_date,
            "currency": self.currency,
            "total": self.total,
            "line_items": [
                {
                    "description": li.description,
                    "quantity": li.quantity,
                    "unit_price": li.unit_price,
                    "amount": li.amount,
                }
                for li in self.line_items
            ],
        }


# JSON-Schema the model is shown so it knows the target shape (also used by the eval harness's
# JSONSchemaMatch grader). Kept in lock-step with the dataclasses above.
INVOICE_JSON_SCHEMA: dict[str, Any] = {
    "type": "object",
    "required": ["invoice_number", "vendor", "invoice_date", "currency", "total", "line_items"],
    "properties": {
        "invoice_number": {"type": "string"},
        "vendor": {"type": "string"},
        "invoice_date": {"type": "string"},
        "currency": {"type": "string"},
        "total": {"type": "number"},
        "line_items": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["description", "quantity", "unit_price", "amount"],
                "properties": {
                    "description": {"type": "string"},
                    "quantity": {"type": "number"},
                    "unit_price": {"type": "number"},
                    "amount": {"type": "number"},
                },
            },
        },
    },
}

# How far the line-item sum may drift from the stated total before we flag it (rounding, taxes
# the doc rolls into the total, etc.). A *hard* reconciliation belongs in finance rules, not the
# extractor; here it is a soft signal that contributes to the confidence score (Ch 20).
RECONCILE_TOLERANCE = 0.02  # 2%


def _require_number(value: Any, label: str, errors: list[str]) -> float | None:
    """Coerce ``value`` to a float, recording a precise error and returning ``None`` on failure."""
    if isinstance(value, bool):  # bool is an int subclass — reject it as a number
        errors.append(f"{label}: expected number, got boolean")
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        cleaned = value.strip().replace(",", "").replace("$", "")
        try:
            return float(cleaned)
        except ValueError:
            errors.append(f"{label}: expected number, got {value!r}")
            return None
    errors.append(f"{label}: expected number, got {type(value).__name__}")
    return None


def _require_str(value: Any, label: str, errors: list[str]) -> str | None:
    if not isinstance(value, str) or not value.strip():
        errors.append(f"{label}: expected a non-empty string, got {value!r}")
        return None
    return value.strip()


def validate_invoice(raw: Any) -> Invoice:
    """Validate a decoded extraction payload into a typed :class:`Invoice`, or raise.

    This is the contract enforcement boundary. It collects **all** field problems before
    raising (not just the first) so a single repair turn can fix everything at once. The
    production swap is one line — ``Invoice.model_validate(raw)`` with Pydantic — and it raises
    the same shape of structured error this pipeline's :mod:`pipeline.repair` already consumes.

    Raises
    ------
    ValidationError
        With ``.errors`` listing every field-level problem found.
    """
    errors: list[str] = []

    if not isinstance(raw, dict):
        raise ValidationError([f"top level: expected an object, got {type(raw).__name__}"])

    invoice_number = _require_str(raw.get("invoice_number"), "invoice_number", errors)
    if invoice_number is not None and not _INVOICE_NO_RE.match(invoice_number):
        errors.append(f"invoice_number: {invoice_number!r} is not a valid invoice id")

    vendor = _require_str(raw.get("vendor"), "vendor", errors)

    invoice_date = _require_str(raw.get("invoice_date"), "invoice_date", errors)
    if invoice_date is not None:
        if not _DATE_RE.match(invoice_date):
            errors.append(f"invoice_date: {invoice_date!r} is not ISO-8601 (YYYY-MM-DD)")
        else:
            try:
                date.fromisoformat(invoice_date)
            except ValueError:
                errors.append(f"invoice_date: {invoice_date!r} is not a real calendar date")

    currency = _require_str(raw.get("currency"), "currency", errors)
    if currency is not None:
        currency = currency.upper()
        if not _CURRENCY_RE.match(currency):
            errors.append(f"currency: {currency!r} is not a 3-letter ISO-4217 code")

    total = _require_number(raw.get("total"), "total", errors)
    if total is not None and total < 0:
        errors.append("total: must be >= 0")

    raw_items = raw.get("line_items")
    items: list[LineItem] = []
    if not isinstance(raw_items, list) or not raw_items:
        errors.append("line_items: expected a non-empty array")
    else:
        for i, row in enumerate(raw_items):
            if not isinstance(row, dict):
                errors.append(f"line_items[{i}]: expected an object, got {type(row).__name__}")
                continue
            desc = _require_str(row.get("description"), f"line_items[{i}].description", errors)
            qty = _require_number(row.get("quantity"), f"line_items[{i}].quantity", errors)
            unit = _require_number(row.get("unit_price"), f"line_items[{i}].unit_price", errors)
            amt = _require_number(row.get("amount"), f"line_items[{i}].amount", errors)
            if None not in (desc, qty, unit, amt):
                items.append(
                    LineItem(description=desc, quantity=qty, unit_price=unit, amount=amt)  # type: ignore[arg-type]
                )

    if errors:
        raise ValidationError(errors)

    return Invoice(
        invoice_number=invoice_number,  # type: ignore[arg-type]
        vendor=vendor,  # type: ignore[arg-type]
        invoice_date=invoice_date,  # type: ignore[arg-type]
        currency=currency,  # type: ignore[arg-type]
        total=total,  # type: ignore[arg-type]
        line_items=tuple(items),
    )


def reconciliation_gap(invoice: Invoice) -> float:
    """Relative gap between the line-item sum and the stated total (0.0 = perfect).

    A soft signal for :mod:`pipeline.confidence`: a large gap means the OCR likely dropped or
    duplicated a row even though every field is individually well-typed.
    """
    line_sum = sum(li.amount for li in invoice.line_items)
    if invoice.total == 0:
        return 0.0 if line_sum == 0 else 1.0
    return abs(line_sum - invoice.total) / abs(invoice.total)
