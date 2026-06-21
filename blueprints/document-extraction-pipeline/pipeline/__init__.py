"""document-extraction-pipeline — a SOLUTION blueprint (Appendix G: IDP & extraction).

This package is a *recipe*, not a new library: it **composes** four pattern blueprints into an
agentic pipeline that turns unstructured documents into validated structured records flowing
into a system of record. Nothing here is forked — each part is imported from its sibling
blueprint (see :mod:`pipeline._compose`), so a fix in a pattern is a fix here too.

The pieces (PLAN.md -> "Composes"):

* ``schema``     — the strict, **versioned** extraction contract (Ch 15).
* ``extract``    — the vision/OCR read as an **agent-loop** turn, traced with the
                   **observability-stack**, with the validate→repair policy wired in (Ch 45/15).
* ``repair``     — retry-and-repair on invalid output (Ch 15).
* ``confidence`` — confidence scoring + routing low-confidence items to a human review queue (Ch 20).
* ``manifest``   — per-item, resumable ledger with a dead-letter lane for a backfill (Ch 31/43).
* ``evals/``     — a golden-set accuracy gate (**eval-harness**) that picks the cheapest model
                   clearing an explicit accuracy bar (Ch 22).

The public surface is :func:`process_document` (one item) and :func:`run_backfill` (a queue,
resumable). Everything runs **offline and free** under ``COMPANION_MOCK=1`` (the default); no
module imports an SDK or spends tokens by default — secrets come from the environment only when
you opt into the live path.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable

from . import _compose  # noqa: F401  -- side effect: pattern blueprints onto sys.path

try:  # observability is optional at runtime; the pipeline runs without it.
    from observability_stack import Tracer  # noqa: E402

    _HAVE_OBS = True
except Exception:  # pragma: no cover
    Tracer = None  # type: ignore[assignment]
    _HAVE_OBS = False

from .confidence import (  # noqa: E402
    DEFAULT_ACCEPT_THRESHOLD,
    ConfidenceReport,
    Decision,
    ReviewQueue,
    score_confidence,
)
from .extract import ExtractResult, extract_document  # noqa: E402
from .manifest import (  # noqa: E402
    MAX_DOC_BYTES,
    MAX_DOC_PAGES,
    ItemStatus,
    Manifest,
    ManifestEntry,
)
from .repair import RepairOutcome  # noqa: E402
from .schema import (  # noqa: E402
    SCHEMA_VERSION,
    Invoice,
    ValidationError,
    validate_invoice,
)

__all__ = [
    # schema
    "Invoice",
    "ValidationError",
    "validate_invoice",
    "SCHEMA_VERSION",
    # extraction (agent-loop + repair + tracing)
    "ExtractResult",
    "extract_document",
    "RepairOutcome",
    # confidence / human-review routing
    "ConfidenceReport",
    "Decision",
    "ReviewQueue",
    "score_confidence",
    "DEFAULT_ACCEPT_THRESHOLD",
    # backfill / manifest
    "Manifest",
    "ManifestEntry",
    "ItemStatus",
    "MAX_DOC_BYTES",
    "MAX_DOC_PAGES",
    # orchestration
    "Document",
    "ItemResult",
    "process_document",
    "run_backfill",
]

__version__ = "0.1.0"


@dataclass(frozen=True, slots=True)
class Document:
    """One input document: an id, its source text, and an optional corrected source.

    ``repaired_source`` exists only for the MOCK demo: it is the cleaned-up source a repair turn
    re-reads, so the *repaired* branch is deterministic offline. A live document has no such
    field — the model conditions on the validation errors instead. ``pages`` is metadata the
    loader uses for the oversize/poison dead-letter rule before any model spend.
    """

    doc_id: str
    source: str
    repaired_source: str | None = None
    pages: int = 1


@dataclass(frozen=True, slots=True)
class ItemResult:
    """What the pipeline decided for one document, and the entry it wrote to the manifest."""

    doc_id: str
    status: ItemStatus
    invoice: Invoice | None = None
    confidence: ConfidenceReport | None = None
    error: str | None = None
    attempts: int = 0
    skipped: bool = False  # True when a resumed run short-circuited an already-terminal item

    @property
    def accepted(self) -> bool:
        return self.status is ItemStatus.ACCEPTED


def _oversize_reason(doc: Document) -> str | None:
    """Return a dead-letter reason if the document is too big to safely process, else ``None``.

    This is the **poison-document guard** the PLAN insists on: one 400-page/corrupt outlier must
    dead-letter *before* any model spend instead of wedging a worker. Cheap, deterministic, and
    applied first.
    """
    if doc.pages > MAX_DOC_PAGES:
        return f"oversize: {doc.pages} pages > {MAX_DOC_PAGES} page limit"
    nbytes = len(doc.source.encode("utf-8"))
    if nbytes > MAX_DOC_BYTES:
        return f"oversize: {nbytes} bytes > {MAX_DOC_BYTES} byte limit"
    return None


def process_document(
    doc: Document,
    *,
    manifest: Manifest,
    review_queue: ReviewQueue,
    accept_threshold: float = DEFAULT_ACCEPT_THRESHOLD,
    max_repairs: int = 2,
    tracer: "Tracer | None" = None,
) -> ItemResult:
    """Process one document end-to-end and record the outcome on the ``manifest``.

    Stages (each traced when a tracer is supplied):

    1. **guard** — oversize/poison docs dead-letter immediately (no model spend).
    2. **extract** — agent-loop read + validate→repair (:func:`pipeline.extract.extract_document`).
       An unrepairable read dead-letters.
    3. **score** — confidence scoring (:func:`pipeline.confidence.score_confidence`).
    4. **route** — ``ACCEPT`` → write to the system of record (here: mark accepted); below the
       threshold → enqueue for human review.

    Idempotent at the manifest row level: a resumed backfill skips items already terminal.
    """
    # Resumability: never redo finished work (Ch 43). A terminal item short-circuits here — no
    # extractor call, no model spend — and reports ``skipped=True`` so a caller can prove it.
    if manifest.is_done(doc.doc_id):
        entry = manifest.get(doc.doc_id)
        return ItemResult(
            doc_id=doc.doc_id,
            status=entry.status,
            error=entry.error,
            confidence=None,
            attempts=entry.attempts,
            skipped=True,
        )

    def _process() -> ItemResult:
        # 1. Poison/oversize guard — dead-letter before spend.
        reason = _oversize_reason(doc)
        if reason is not None:
            manifest.mark_dead_letter(doc.doc_id, error=reason, attempts=0)
            return ItemResult(doc_id=doc.doc_id, status=ItemStatus.DEAD_LETTER, error=reason)

        # 2. Extract (agent-loop read + repair), traced.
        extracted: ExtractResult = extract_document(
            doc.source,
            repaired_source=doc.repaired_source,
            max_repairs=max_repairs,
            tracer=tracer,
        )
        outcome = extracted.outcome
        if not outcome.ok:
            err = "; ".join(outcome.error.errors) if outcome.error else "unrepairable extraction"
            manifest.mark_dead_letter(doc.doc_id, error=err, attempts=outcome.attempts)
            return ItemResult(
                doc_id=doc.doc_id,
                status=ItemStatus.DEAD_LETTER,
                error=err,
                attempts=outcome.attempts,
            )

        invoice = outcome.invoice
        assert invoice is not None  # ok is True

        # 3. Score confidence (cheap, deterministic, no extra model call).
        report = score_confidence(
            invoice,
            repaired=outcome.repaired,
            accept_threshold=accept_threshold,
        )

        # 4. Route on the written threshold.
        record = invoice.to_record()
        if report.decision is Decision.ACCEPT:
            manifest.mark_accepted(
                doc.doc_id, record, confidence=report.score, attempts=outcome.attempts
            )
            status = ItemStatus.ACCEPTED
        else:
            review_queue.enqueue(doc.doc_id, invoice, report)
            manifest.mark_review(
                doc.doc_id, record, confidence=report.score, attempts=outcome.attempts
            )
            status = ItemStatus.REVIEW

        return ItemResult(
            doc_id=doc.doc_id,
            status=status,
            invoice=invoice,
            confidence=report,
            attempts=outcome.attempts,
        )

    if tracer is not None and _HAVE_OBS:
        with tracer.span(f"item:{doc.doc_id}"):
            return _process()
    return _process()


@dataclass(slots=True)
class BackfillResult:
    """The aggregate outcome of draining a queue of documents."""

    manifest: Manifest
    review_queue: ReviewQueue
    items: list[ItemResult] = field(default_factory=list)

    def counts(self) -> dict[str, int]:
        return self.manifest.counts()


def run_backfill(
    docs: Iterable[Document],
    *,
    manifest: Manifest | None = None,
    review_queue: ReviewQueue | None = None,
    accept_threshold: float = DEFAULT_ACCEPT_THRESHOLD,
    max_repairs: int = 2,
    tracer: "Tracer | None" = None,
) -> BackfillResult:
    """Drain a queue of documents into a manifest, resumably.

    Pass an existing ``manifest`` (e.g. ``Manifest.load(path)``) to **resume** a crashed run:
    finished items are skipped and only ``pending`` work is processed. Omit it to start fresh.
    The same ``review_queue`` accumulates every low-confidence item for the human path.
    """
    docs = list(docs)
    manifest = manifest if manifest is not None else Manifest.for_docs(d.doc_id for d in docs)
    review_queue = review_queue if review_queue is not None else ReviewQueue()

    items: list[ItemResult] = []
    for doc in docs:
        result = process_document(
            doc,
            manifest=manifest,
            review_queue=review_queue,
            accept_threshold=accept_threshold,
            max_repairs=max_repairs,
            tracer=tracer,
        )
        items.append(result)

    return BackfillResult(manifest=manifest, review_queue=review_queue, items=items)
