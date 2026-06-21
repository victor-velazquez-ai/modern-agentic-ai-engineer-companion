"""Per-item manifest for a resumable backfill, with a dead-letter lane (Ch 31, 43).

A backlog of a million scanned invoices is a **batch pipeline**, not a request. Batch pipelines
have one non-negotiable property: they must survive a crash, a redeploy, and a poison document
without redoing finished work or wedging on the bad item. The mechanism for that is a
**manifest** — a durable, per-item ledger of status — plus a **dead-letter** lane for items
that can't be processed so one outlier can't stop the other 999,999.

This module is the ledger and its rules, kept storage-agnostic and pure:

* :class:`ItemStatus` — the lifecycle of one document.
* :class:`ManifestEntry` — the per-item row (status, schema version, attempt count, result/error).
* :class:`Manifest` — the collection, with the resumability operations: ``pending()`` (what's
  left), ``is_done()`` (skip finished work), ``mark_*`` transitions, and JSONL load/save so a
  crash resumes from disk.

It maps to Ch 43's batch reference architecture (idempotent worker fleet draining a queue) and
Ch 31's data-pipeline discipline (manifests, dead-letter queues, exactly-once *effects*).
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Iterable, Iterator

from .schema import SCHEMA_VERSION


class ItemStatus(str, Enum):
    """Lifecycle of one document in the backfill."""

    PENDING = "pending"  # not yet attempted
    ACCEPTED = "accepted"  # extracted, validated, confident → written to the system of record
    REVIEW = "review"  # extracted + valid but low-confidence → human review queue
    DEAD_LETTER = "dead_letter"  # could not be processed (poison/oversize/unrepairable)

    def __str__(self) -> str:
        return self.value


# A document the loader rejects *before* any model spend — too large or unreadable. Keeping this
# bound here means one 400-page corrupt scan dead-letters instantly instead of melting a worker.
MAX_DOC_BYTES = 256 * 1024  # 256 KB of extracted text is already a very large invoice
MAX_DOC_PAGES = 50


@dataclass(slots=True)
class ManifestEntry:
    """The durable row for one document — the unit of resumability and attribution."""

    doc_id: str
    status: ItemStatus = ItemStatus.PENDING
    schema_version: str = SCHEMA_VERSION
    attempts: int = 0
    result: dict[str, Any] | None = None  # the validated record, when ACCEPTED/REVIEW
    error: str | None = None  # the failure reason, when DEAD_LETTER
    confidence: float | None = None

    @property
    def done(self) -> bool:
        """A terminal status — a resumed run skips these so finished work is never redone."""
        return self.status is not ItemStatus.PENDING

    def to_json(self) -> dict[str, Any]:
        return {
            "doc_id": self.doc_id,
            "status": str(self.status),
            "schema_version": self.schema_version,
            "attempts": self.attempts,
            "result": self.result,
            "error": self.error,
            "confidence": self.confidence,
        }

    @classmethod
    def from_json(cls, obj: dict[str, Any]) -> "ManifestEntry":
        return cls(
            doc_id=str(obj["doc_id"]),
            status=ItemStatus(obj.get("status", "pending")),
            schema_version=str(obj.get("schema_version", SCHEMA_VERSION)),
            attempts=int(obj.get("attempts", 0)),
            result=obj.get("result"),
            error=obj.get("error"),
            confidence=obj.get("confidence"),
        )


@dataclass(slots=True)
class Manifest:
    """The per-item ledger for a backfill — load it, drain ``pending()``, save it, repeat.

    The manifest is the **only** durable state a worker needs: kill the process mid-run, reload
    from JSONL, and ``pending()`` yields exactly the unfinished items. Because each transition is
    recorded by ``doc_id``, re-processing an already-done item is a no-op — the idempotency a
    batch fleet relies on (Ch 43).
    """

    entries: dict[str, ManifestEntry] = field(default_factory=dict)

    # --- construction ---------------------------------------------------------------------
    @classmethod
    def for_docs(cls, doc_ids: Iterable[str]) -> "Manifest":
        """Open a fresh manifest with every document PENDING."""
        m = cls()
        for doc_id in doc_ids:
            if doc_id not in m.entries:
                m.entries[doc_id] = ManifestEntry(doc_id=doc_id)
        return m

    # --- resumability queries -------------------------------------------------------------
    def pending(self) -> list[ManifestEntry]:
        """The unfinished items, in insertion order — the worker's work list."""
        return [e for e in self.entries.values() if not e.done]

    def is_done(self, doc_id: str) -> bool:
        e = self.entries.get(doc_id)
        return bool(e and e.done)

    def get(self, doc_id: str) -> ManifestEntry:
        return self.entries[doc_id]

    # --- transitions (each is idempotent at the row level) --------------------------------
    def mark_accepted(self, doc_id: str, record: dict[str, Any], *, confidence: float, attempts: int) -> ManifestEntry:
        return self._set(doc_id, ItemStatus.ACCEPTED, result=record, confidence=confidence, attempts=attempts)

    def mark_review(self, doc_id: str, record: dict[str, Any], *, confidence: float, attempts: int) -> ManifestEntry:
        return self._set(doc_id, ItemStatus.REVIEW, result=record, confidence=confidence, attempts=attempts)

    def mark_dead_letter(self, doc_id: str, *, error: str, attempts: int = 0) -> ManifestEntry:
        return self._set(doc_id, ItemStatus.DEAD_LETTER, error=error, attempts=attempts)

    def _set(
        self,
        doc_id: str,
        status: ItemStatus,
        *,
        result: dict[str, Any] | None = None,
        error: str | None = None,
        confidence: float | None = None,
        attempts: int | None = None,
    ) -> ManifestEntry:
        entry = self.entries.setdefault(doc_id, ManifestEntry(doc_id=doc_id))
        entry.status = status
        entry.result = result
        entry.error = error
        entry.confidence = confidence
        if attempts is not None:
            entry.attempts = attempts
        # The record stamps the schema version it was produced under (drift survival, Ch 43).
        if result is not None:
            entry.schema_version = str(result.get("schema_version", SCHEMA_VERSION))
        return entry

    # --- aggregates -----------------------------------------------------------------------
    def counts(self) -> dict[str, int]:
        out = {s.value: 0 for s in ItemStatus}
        for e in self.entries.values():
            out[str(e.status)] += 1
        return out

    def dead_letters(self) -> list[ManifestEntry]:
        return [e for e in self.entries.values() if e.status is ItemStatus.DEAD_LETTER]

    def __len__(self) -> int:
        return len(self.entries)

    def __iter__(self) -> Iterator[ManifestEntry]:
        return iter(self.entries.values())

    # --- durability (JSONL: one entry per line, appendable + diff-able) -------------------
    def save(self, path: str | Path) -> Path:
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        lines = [json.dumps(e.to_json(), sort_keys=True) for e in self.entries.values()]
        p.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")
        return p

    @classmethod
    def load(cls, path: str | Path) -> "Manifest":
        """Reload a manifest from JSONL so a crashed backfill resumes from disk."""
        p = Path(path)
        m = cls()
        if not p.exists():
            return m
        for raw in p.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if not line:
                continue
            entry = ManifestEntry.from_json(json.loads(line))
            m.entries[entry.doc_id] = entry
        return m
