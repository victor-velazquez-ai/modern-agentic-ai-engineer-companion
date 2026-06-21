"""audit — the append-only ledger of every screening decision and its basis.

An immutable audit trail is **part of the compliance product**, not an afterthought: when a
regulator or an internal reviewer asks "why was this flagged, on what basis, and who saw it?",
the answer has to be a tamper-evident record, not a reconstruction. This package provides that
ledger and composes the ``observability-stack`` blueprint for the per-run trace.
"""

from __future__ import annotations

from .ledger import AuditLedger, AuditRecord

__all__ = ["AuditLedger", "AuditRecord"]
