"""The audit trail (Ch 41) — a tamper-evident log of every security-relevant decision.

A security posture you can't review after the fact isn't one. The audit log is the record that
makes the platform *accountable*: every guarded decision — a tool authorized or denied, an
input blocked by a guardrail, a credential minted, sandboxed code rejected, a human approval —
is appended here with who/what/why and the outcome. When something goes wrong (or an auditor
asks), this is the answer to "what did the agent do, and what stopped it?".

Two properties make it trustworthy:

* **Append-only.** The log only grows. There is no update or delete in the API.
* **Tamper-evident (hash chain).** Each event stores the SHA-256 of ``(previous_hash + this
  event's content)``. Altering or removing any past event breaks the chain from that point on,
  which :meth:`AuditLog.verify` detects. You can't quietly rewrite history — a classic
  blockchain-style integrity check, applied to a humble decision log.

It is dependency-free and JSONL-serializable (one event per line), so the trail ships to the
same log pipeline as everything else and is diffable/greppable. In production you'd also stream
it to append-only storage (e.g. an object-lock bucket) so the record survives the host.
"""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import asdict, dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Iterable, Iterator

# The genesis link — the hash a chain starts from before any event exists.
GENESIS_HASH = "0" * 64


class Decision(str, Enum):
    """The outcome recorded for an audited action."""

    ALLOW = "allow"
    DENY = "deny"
    REDACT = "redact"
    BLOCK = "block"
    APPROVAL_REQUIRED = "approval_required"
    APPROVED = "approved"
    REJECTED = "rejected"

    def __str__(self) -> str:
        return self.value


@dataclass(frozen=True)
class AuditEvent:
    """One immutable entry in the audit chain.

    ``prev_hash`` links to the event before it and ``hash`` is this event's content hash;
    together they form the tamper-evident chain. ``hash`` is computed by :meth:`finalize`, so
    construct events through :meth:`AuditLog.record` rather than by hand.
    """

    seq: int
    timestamp: float
    actor: str  # who acted (principal id, "system", an operator)
    action: str  # what was attempted (e.g. "tool.invoke", "guard.input", "credential.mint")
    target: str  # the object acted on (a tool name, a resource id)
    decision: Decision  # the outcome
    reason: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)
    prev_hash: str = GENESIS_HASH
    hash: str = ""

    def _content(self) -> dict[str, Any]:
        """The fields covered by the hash (everything except ``hash`` itself)."""

        return {
            "seq": self.seq,
            "timestamp": self.timestamp,
            "actor": self.actor,
            "action": self.action,
            "target": self.target,
            "decision": str(self.decision),
            "reason": self.reason,
            "metadata": self.metadata,
            "prev_hash": self.prev_hash,
        }

    def compute_hash(self) -> str:
        """SHA-256 over this event's content (deterministic; sorts keys)."""

        blob = json.dumps(self._content(), sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(blob.encode("utf-8")).hexdigest()

    def finalize(self) -> "AuditEvent":
        """Return a copy with ``hash`` filled in from the content + ``prev_hash``."""

        from dataclasses import replace

        return replace(self, hash=self.compute_hash())

    def to_json(self) -> str:
        return json.dumps({**self._content(), "hash": self.hash}, sort_keys=True)


class AuditLog:
    """An append-only, hash-chained audit log (in-memory, JSONL-serializable).

    Use :meth:`record` to append; the log links each event to the previous one and seals it
    with a content hash. :meth:`verify` walks the chain and proves it hasn't been tampered with.
    """

    def __init__(self) -> None:
        self._events: list[AuditEvent] = []

    def __len__(self) -> int:
        return len(self._events)

    def __iter__(self) -> Iterator[AuditEvent]:
        return iter(self._events)

    @property
    def head_hash(self) -> str:
        """The hash of the most recent event (or :data:`GENESIS_HASH` if empty)."""

        return self._events[-1].hash if self._events else GENESIS_HASH

    def record(
        self,
        *,
        actor: str,
        action: str,
        target: str,
        decision: Decision | str,
        reason: str = "",
        metadata: dict[str, Any] | None = None,
        now: float | None = None,
    ) -> AuditEvent:
        """Append one decision to the chain and return the sealed event."""

        event = AuditEvent(
            seq=len(self._events),
            timestamp=now if now is not None else time.time(),
            actor=actor,
            action=action,
            target=target,
            decision=decision if isinstance(decision, Decision) else Decision(str(decision)),
            reason=reason,
            metadata=dict(metadata or {}),
            prev_hash=self.head_hash,
        ).finalize()
        self._events.append(event)
        return event

    def verify(self) -> bool:
        """True iff the chain is intact: every link and every content hash checks out.

        Recomputes each event's hash and confirms it both matches the stored hash and chains to
        the prior event's hash. Any insertion, deletion, or edit anywhere breaks this.
        """

        prev = GENESIS_HASH
        for i, event in enumerate(self._events):
            if event.seq != i:
                return False
            if event.prev_hash != prev:
                return False
            if event.hash != event.compute_hash():
                return False
            prev = event.hash
        return True

    def tail(self, n: int = 20) -> list[AuditEvent]:
        """The last ``n`` events (most recent last)."""

        return self._events[-n:]

    # --- JSONL persistence ---------------------------------------------------------------

    def to_jsonl(self) -> str:
        """Serialize the whole chain to JSONL (one event per line)."""

        return "\n".join(e.to_json() for e in self._events)

    def write_jsonl(self, path: str | Path) -> None:
        """Append-only write of the chain to ``path`` (overwrites with the full chain)."""

        Path(path).write_text(self.to_jsonl() + ("\n" if self._events else ""), encoding="utf-8")

    @classmethod
    def from_events(cls, events: Iterable[AuditEvent]) -> "AuditLog":
        """Rebuild a log from already-sealed events (e.g. loaded from JSONL), then verify."""

        log = cls()
        log._events = list(events)
        return log

    @classmethod
    def load_jsonl(cls, path: str | Path) -> "AuditLog":
        """Load a chain from JSONL. Does *not* re-seal — call :meth:`verify` to check integrity."""

        events: list[AuditEvent] = []
        for line in Path(path).read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            obj = json.loads(line)
            events.append(
                AuditEvent(
                    seq=int(obj["seq"]),
                    timestamp=float(obj["timestamp"]),
                    actor=str(obj["actor"]),
                    action=str(obj["action"]),
                    target=str(obj["target"]),
                    decision=Decision(str(obj["decision"])),
                    reason=str(obj.get("reason", "")),
                    metadata=dict(obj.get("metadata", {})),
                    prev_hash=str(obj.get("prev_hash", GENESIS_HASH)),
                    hash=str(obj.get("hash", "")),
                )
            )
        return cls.from_events(events)


def event_as_dict(event: AuditEvent) -> dict[str, Any]:
    """A plain dict view of an event (for structured logging / dashboards)."""

    return asdict(event)


__all__ = [
    "AuditLog",
    "AuditEvent",
    "Decision",
    "GENESIS_HASH",
    "event_as_dict",
]
