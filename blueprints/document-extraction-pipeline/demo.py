"""MOCK demo — drive the whole document-extraction pipeline offline, with zero API spend.

Run it::

    python demo.py

It loads the six sample documents in ``data/samples/`` and drains them through the pipeline,
showing every outcome the PLAN's definition-of-done calls for:

* a **clean** invoice that extracts and validates first try -> ACCEPTED;
* a **repairable** invoice (US-format date, ``$`` on the total) that fails validation, gets the
  errors fed back, and clears on one repair turn -> ACCEPTED (repaired);
* a **low-confidence** invoice that is well-typed but whose line items don't reconcile -> routed
  to the **human review queue**;
* an **unrepairable** read -> DEAD-LETTERED with a precise error;
* a **poison** 400-page doc -> DEAD-LETTERED by the oversize guard *before any model spend*.

It then proves **resumability** (re-run over the same manifest -> every item is skipped) and, when
the ``observability-stack`` sibling is present, prints the per-item trace tree with a $0.00 cost
roll-up. Nothing here imports an SDK or spends tokens: ``COMPANION_MOCK`` defaults to ``1``.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

# Run free and deterministic unless the operator explicitly opts into a live model.
os.environ.setdefault("COMPANION_MOCK", "1")

# Make this folder importable as the ``pipeline`` package whether run from here or elsewhere.
_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

from pipeline import (  # noqa: E402
    Document,
    ItemStatus,
    Manifest,
    ReviewQueue,
    run_backfill,
)

try:  # the trace is a nice-to-have; the pipeline runs without observability installed.
    from observability_stack import ConsoleExporter, Tracer  # noqa: E402

    _HAVE_OBS = True
except Exception:  # pragma: no cover
    Tracer = None  # type: ignore[assignment]
    ConsoleExporter = None  # type: ignore[assignment]
    _HAVE_OBS = False

_SAMPLES = _HERE / "data" / "samples"

# The queue of documents to backfill. Each names its sample file; the poison doc declares 400
# pages so the oversize guard trips on page count before any read. The one repairable doc carries
# its corrected source (what a live model would emit from the repair prompt) for offline determinism.
_DOCS = [
    ("inv-1001", "inv-1001-clean.txt", None, 2),
    ("inv-1002", "inv-1002-needs-repair.txt", "inv-1002-repaired.txt", 1),
    ("inv-1003", "inv-1003-low-confidence.txt", None, 1),
    ("inv-1004", "inv-1004-unrepairable.txt", None, 1),
    ("inv-9999", "inv-9999-poison.txt", None, 400),
]


def _read(name: str) -> str:
    return (_SAMPLES / name).read_text(encoding="utf-8")


def _load_documents() -> list[Document]:
    docs: list[Document] = []
    for doc_id, fname, repaired_fname, pages in _DOCS:
        docs.append(
            Document(
                doc_id=doc_id,
                source=_read(fname),
                repaired_source=_read(repaired_fname) if repaired_fname else None,
                pages=pages,
            )
        )
    return docs


_STATUS_GLYPH = {
    ItemStatus.ACCEPTED: "ACCEPT ",
    ItemStatus.REVIEW: "REVIEW ",
    ItemStatus.DEAD_LETTER: "DEAD   ",
    ItemStatus.PENDING: "PENDING",
}


def main() -> int:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
        except (AttributeError, ValueError):  # pragma: no cover
            pass

    print("=" * 72)
    print("Document-extraction pipeline — MOCK backfill (no API spend)")
    print("=" * 72)
    print()

    docs = _load_documents()
    review_queue = ReviewQueue()
    tracer = Tracer() if _HAVE_OBS else None

    result = run_backfill(docs, review_queue=review_queue, tracer=tracer)

    # --- per-item outcomes -------------------------------------------------------------
    print("Per-document outcome")
    print("-" * 72)
    for item in result.items:
        glyph = _STATUS_GLYPH.get(item.status, str(item.status))
        detail = ""
        if item.invoice is not None and item.confidence is not None:
            detail = (
                f"{item.invoice.vendor} · {item.invoice.currency} {item.invoice.total:.2f} "
                f"· conf {item.confidence.score:.2f}"
            )
            if item.attempts > 1:
                detail += f" · repaired in {item.attempts} passes"
            if item.status is ItemStatus.REVIEW and item.confidence.reasons:
                detail += f" · why: {item.confidence.reasons[0]}"
        elif item.error:
            detail = f"error: {item.error}"
        print(f"  [{glyph}] {item.doc_id:<10} {detail}")
    print()

    # --- aggregate ---------------------------------------------------------------------
    counts = result.counts()
    print("Backfill summary")
    print("-" * 72)
    print(
        f"  accepted={counts['accepted']}  review={counts['review']}  "
        f"dead_letter={counts['dead_letter']}  pending={counts['pending']}"
    )
    print()

    # --- human review queue ------------------------------------------------------------
    print(f"Human review queue ({len(review_queue)} item(s) awaiting a person)")
    print("-" * 72)
    for ri in review_queue.items:
        print(f"  • {ri.doc_id:<10} conf {ri.score:.2f} — {', '.join(ri.reasons)}")
    if not review_queue.items:
        print("  (empty)")
    print()

    # --- dead-letter lane --------------------------------------------------------------
    print("Dead-letter lane (one outlier can't wedge the pipeline)")
    print("-" * 72)
    for dl in result.manifest.dead_letters():
        print(f"  • {dl.doc_id:<10} {dl.error}")
    print()

    # --- resumability proof ------------------------------------------------------------
    # Re-run over the SAME manifest: every item is already terminal, so nothing is re-processed.
    print("Resumability — re-running over the same manifest")
    print("-" * 72)
    before = result.manifest.counts()
    rerun = run_backfill(docs, manifest=result.manifest, review_queue=ReviewQueue())
    skipped = sum(1 for i in rerun.items if i.skipped)
    pending_again = rerun.manifest.counts()["pending"]
    print(
        f"  manifest unchanged: {before == rerun.manifest.counts()}  ·  "
        f"still pending: {pending_again}  ·  "
        f"items skipped (already done, zero re-extraction): {skipped}/{len(rerun.items)}"
    )
    print()

    # --- manifest round-trip (durability) ----------------------------------------------
    manifest_path = _HERE / "data" / "_manifest.jsonl"
    result.manifest.save(manifest_path)
    reloaded = Manifest.load(manifest_path)
    print("Durability — manifest JSONL round-trip")
    print("-" * 72)
    print(
        f"  saved {len(result.manifest)} entries to {manifest_path.name}; "
        f"reloaded {len(reloaded)}; equal counts: {result.manifest.counts() == reloaded.counts()}"
    )
    try:
        manifest_path.unlink()  # keep the repo clean; it's a generated artifact
    except OSError:  # pragma: no cover
        pass
    print()

    # --- observability trace -----------------------------------------------------------
    if tracer is not None and _HAVE_OBS:
        print("Per-item trace (observability-stack) — cost rolls up to $0.00 in MOCK")
        print("-" * 72)
        try:
            ConsoleExporter(show_tokens=False).export(tracer.trace)
        except Exception as exc:  # pragma: no cover - never let tracing break the demo
            print(f"  (trace unavailable: {exc})")
        print()
    else:
        print("(observability-stack not importable — skipping the trace tree)")
        print()

    print("Done. No API spend. Set COMPANION_MOCK=0 + inject a gateway vision port for the live path.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
