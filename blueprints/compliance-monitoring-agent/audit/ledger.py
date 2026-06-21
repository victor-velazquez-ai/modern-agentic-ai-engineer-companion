"""ledger — the append-only, tamper-evident record of every screening decision (Ch 28).

For a compliance product the audit trail *is* part of the deliverable. When a regulator or an
internal reviewer asks "why was this item flagged, against which rule, with what confidence, and
who was it routed to?", the answer must be a record that (a) was written at decision time and (b)
demonstrably has not been edited since. This module provides both:

* **append-only** — :class:`AuditLedger` only ever appends; there is no update or delete method.
* **tamper-evident** — each record carries the SHA-256 hash of the previous record (a hash chain,
  Ch 28). Change any earlier record and every later ``prev_hash`` stops matching, so silent edits
  are detectable by :meth:`AuditLedger.verify`. This is the same idea as a Merkle/blockchain log,
  kept to the few lines a teaching blueprint needs.

How it composes ``observability-stack``: a screening pass is wrapped in a tracer ``run`` span, and
each item's classification/routing is a child span carrying the cited rule and confidence as
attributes. The trace answers *operational* questions (latency, cost, what ran); the ledger
answers *compliance* questions (what was decided and on what basis). They are complementary, so we
keep both — the trace is ephemeral telemetry, the ledger is the durable record of account.

Stdlib only; deterministic. The ledger persists as JSONL so it diffs, greps, and ships anywhere.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Iterator

# Genesis hash for the first record's ``prev_hash`` — a fixed sentinel so the chain has a root.
GENESIS_HASH = "0" * 64


@dataclass(frozen=True)
class AuditRecord:
    """One immutable entry: a decision and everything needed to defend it later.

    The record is deliberately self-contained — an auditor reading a single line can see the
    item, the verdict, the rule it cites, the agent's confidence, where it was routed, and any
    anomaly signal — without joining against another system. ``record_hash`` chains this entry to
    the previous one; it is computed over every other field, so it covers the full payload.
    """

    seq: int                  # 0-based position in the ledger
    item_id: str
    decision: str             # "clear" | "flag"
    rule_id: str              # the cited rule ("" when clear)
    rule_title: str
    confidence: float
    basis: str                # the rule text / human-readable reason the flag rests on
    routed_to: str            # "none" (clear) | "human-review-queue"
    anomaly: str              # an anomaly note, or "" when none
    prev_hash: str            # SHA-256 of the previous record (GENESIS for the first)
    record_hash: str = ""     # SHA-256 of this record's content; set by the ledger on append

    def content_for_hash(self) -> dict[str, Any]:
        """The fields the hash covers — everything except ``record_hash`` itself."""
        d = asdict(self)
        d.pop("record_hash", None)
        return d

    def compute_hash(self) -> str:
        """SHA-256 over a canonical JSON encoding of this record's content."""
        payload = json.dumps(self.content_for_hash(), sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()


@dataclass
class AuditLedger:
    """An append-only, hash-chained ledger of audit records.

    Construct empty (``AuditLedger()``) for an in-memory log, or pass ``path=`` to also mirror
    every append to a JSONL file. The only mutation is :meth:`append`; there is intentionally no
    way to edit or remove a record, because "you could quietly change the audit log" is exactly
    the property a compliance record must *not* have.
    """

    path: Path | None = None
    records: list[AuditRecord] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.path is not None:
            self.path = Path(self.path)

    @property
    def head_hash(self) -> str:
        """Hash of the most recent record — the link the next append chains onto."""
        return self.records[-1].record_hash if self.records else GENESIS_HASH

    def append(
        self,
        *,
        item_id: str,
        decision: str,
        rule_id: str = "",
        rule_title: str = "",
        confidence: float = 0.0,
        basis: str = "",
        routed_to: str = "none",
        anomaly: str = "",
    ) -> AuditRecord:
        """Append a decision to the ledger. Returns the sealed (hashed) record.

        The record's ``prev_hash`` is the current head; its ``record_hash`` is then computed and
        the record is frozen into the log. If a ``path`` was given, the record is also flushed to
        the JSONL file immediately, so a crash mid-run still leaves a durable partial trail.
        """
        record = AuditRecord(
            seq=len(self.records),
            item_id=item_id,
            decision=decision,
            rule_id=rule_id,
            rule_title=rule_title,
            confidence=round(float(confidence), 4),
            basis=basis,
            routed_to=routed_to,
            anomaly=anomaly,
            prev_hash=self.head_hash,
        )
        sealed = AuditRecord(**{**asdict(record), "record_hash": record.compute_hash()})
        self.records.append(sealed)
        if self.path is not None:
            with self.path.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(asdict(sealed), sort_keys=True) + "\n")
        return sealed

    def verify(self) -> bool:
        """True iff the chain is intact: every hash recomputes and every link matches.

        This is what makes the trail *tamper-evident*: edit any earlier record's content and its
        recomputed hash changes, breaking the next record's ``prev_hash`` link — so a single edit
        anywhere is detectable here. An auditor (or a CI check) runs this to trust the log.
        """
        expected_prev = GENESIS_HASH
        for rec in self.records:
            if rec.prev_hash != expected_prev:
                return False
            if rec.record_hash != rec.compute_hash():
                return False
            expected_prev = rec.record_hash
        return True

    def __len__(self) -> int:
        return len(self.records)

    def __iter__(self) -> Iterator[AuditRecord]:
        return iter(self.records)


def load_ledger(path: str | Path) -> AuditLedger:
    """Load a persisted JSONL ledger back into an :class:`AuditLedger` (for re-verification).

    Reads the records as written; it does **not** rewrite the file, so loading is read-only with
    respect to the durable trail. Run :meth:`AuditLedger.verify` on the result to confirm the
    on-disk log has not been tampered with.
    """
    p = Path(path)
    records: list[AuditRecord] = []
    if p.exists():
        for line in p.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            records.append(AuditRecord(**json.loads(line)))
    ledger = AuditLedger(path=None)
    ledger.records = records
    return ledger
