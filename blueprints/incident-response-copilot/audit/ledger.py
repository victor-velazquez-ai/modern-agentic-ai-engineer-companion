"""An append-only, tamper-evident audit log of every action (Ch 28).

In an incident the audit trail is not paperwork — it is *evidence*. "Who (the copilot or a
human) did what, when, and was it approved?" must survive the incident, the postmortem, and the
compliance review. So the ledger here is **append-only by construction**:

* there is no ``update`` and no ``delete`` — only :meth:`AuditLedger.append`;
* each entry is hash-chained to the one before it (``prev_hash`` → ``entry_hash``), so removing
  or editing any past entry breaks every hash after it and :meth:`AuditLedger.verify` catches it;
* the entries are plain dicts you can stream to a real system of record (an append-only S3
  bucket, a WORM store, a SIEM) by swapping :meth:`AuditLedger.export_jsonl`'s sink.

The ledger records *intent and outcome*, not just success: a **proposed** action, an
**approved** one, a **rejected** one, and a **read** all get an entry, because "the copilot
wanted to restart the pod and the on-call said no" is exactly the line you want in the
postmortem. Keep it in memory for the demo; point :meth:`export_jsonl` at durable storage in
production. Never let the copilot be able to rewrite its own history.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Iterator

# The genesis link: the chain starts from a fixed, well-known hash so the first real entry is
# verifiable too (there is no "trust me" entry zero).
GENESIS_HASH = "0" * 64


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


@dataclass(frozen=True, slots=True)
class LedgerEntry:
    """One immutable line in the audit log, hash-chained to its predecessor.

    ``actor`` is who did it (``"copilot"`` or a human id); ``action`` is the verb
    (``"retrieve"``, ``"propose"``, ``"approve"``, ``"reject"``, ``"execute"``, ``"read_tool"``);
    ``detail`` is a free-form payload (the proposed command, the tool + args, the approver).
    ``entry_hash`` is ``sha256(prev_hash || canonical(payload))`` — change any field and it no
    longer matches, which is what makes the chain tamper-evident.
    """

    seq: int
    ts: str
    actor: str
    action: str
    detail: dict[str, Any]
    prev_hash: str
    entry_hash: str

    def payload(self) -> dict[str, Any]:
        """The signed portion of the entry (everything except the hash itself)."""
        return {
            "seq": self.seq,
            "ts": self.ts,
            "actor": self.actor,
            "action": self.action,
            "detail": self.detail,
            "prev_hash": self.prev_hash,
        }

    def compute_hash(self) -> str:
        """Recompute this entry's hash from its payload (used by :meth:`AuditLedger.verify`)."""
        return _hash_payload(self.payload())

    def to_dict(self) -> dict[str, Any]:
        d = self.payload()
        d["entry_hash"] = self.entry_hash
        return d


def _hash_payload(payload: dict[str, Any]) -> str:
    """Deterministic SHA-256 over a canonical JSON encoding of the payload."""
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


@dataclass(slots=True)
class AuditLedger:
    """An in-memory, append-only, hash-chained audit log.

    The only mutation is :meth:`append`. ``entries`` is exposed read-only via iteration and
    :meth:`__getitem__`; there is deliberately no setter, no pop, no clear. Wire
    :meth:`export_jsonl` to durable, write-once storage in production.
    """

    _entries: list[LedgerEntry] = field(default_factory=list)

    def append(self, actor: str, action: str, detail: dict[str, Any] | None = None) -> LedgerEntry:
        """Record one action and return the new (immutable) entry.

        The entry is chained onto the current head: its ``prev_hash`` is the last entry's
        ``entry_hash`` (or :data:`GENESIS_HASH` for the first), so the whole log is verifiable
        end to end.
        """
        prev_hash = self._entries[-1].entry_hash if self._entries else GENESIS_HASH
        seq = len(self._entries)
        payload = {
            "seq": seq,
            "ts": _now_iso(),
            "actor": str(actor),
            "action": str(action),
            "detail": dict(detail or {}),
            "prev_hash": prev_hash,
        }
        entry = LedgerEntry(
            seq=payload["seq"],
            ts=payload["ts"],
            actor=payload["actor"],
            action=payload["action"],
            detail=payload["detail"],
            prev_hash=payload["prev_hash"],
            entry_hash=_hash_payload(payload),
        )
        self._entries.append(entry)
        return entry

    def verify(self) -> bool:
        """Return ``True`` iff the chain is intact (no entry edited, removed, or reordered).

        Re-derives every hash and checks the links. A single altered byte anywhere in the log
        makes this return ``False`` — that is the whole point of an append-only ledger.
        """
        prev = GENESIS_HASH
        for i, entry in enumerate(self._entries):
            if entry.seq != i or entry.prev_hash != prev:
                return False
            if entry.compute_hash() != entry.entry_hash:
                return False
            prev = entry.entry_hash
        return True

    def export_jsonl(self) -> str:
        """Serialize the whole ledger as JSON Lines (one entry per line).

        This is the seam to your system of record: in production, stream these lines to an
        append-only/WORM sink instead of returning a string. Kept pure here so the demo and the
        tests can assert on the output without touching the filesystem.
        """
        return "\n".join(json.dumps(e.to_dict(), sort_keys=True) for e in self._entries)

    def __iter__(self) -> Iterator[LedgerEntry]:
        return iter(self._entries)

    def __len__(self) -> int:
        return len(self._entries)

    def __getitem__(self, index: int) -> LedgerEntry:
        return self._entries[index]
