"""Corpus-freshness monitoring — so the knowledge base doesn't silently rot (Ch 30).

A retrieval assistant fails in a quiet, dangerous way: the index keeps answering confidently
from documents that are months out of date. Nobody sees an error; people just get wrong answers
and stop trusting the tool. The fix is **freshness monitoring** — track when each document was
last updated and flag the ones past a staleness budget, so a human re-syncs them *before* the
corpus rots.

This is the observability-stack blueprint's "monitor the system, not just the request" idea
applied to data freshness. The check here is deterministic and offline (it reads ``updated``
dates from the corpus ACL sidecar against a reference "today"), so it runs in CI as a guard: a
nightly job runs :func:`check_freshness` and alerts if anything is stale.

In production you'd source ``updated`` from each connector (the wiki page's last-edited time, the
drive file's modified time) and emit the staleness count as a metric / span attribute on the
observability stack. The contract — *every indexed doc has a last-updated date, and stale ones
are surfaced* — is what matters.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date
from pathlib import Path

# How old a document may be before it's considered stale and flagged for re-sync. A policy knob:
# a runbook might tolerate a year; an on-call rotation or a price sheet might tolerate a week.
DEFAULT_MAX_AGE_DAYS = 180


@dataclass(frozen=True)
class DocFreshness:
    """One document's freshness verdict."""

    doc_id: str
    title: str
    updated: date
    age_days: int
    stale: bool


@dataclass(frozen=True)
class FreshnessReport:
    """The corpus-wide freshness picture (what a monitor alerts on)."""

    docs: tuple[DocFreshness, ...]
    max_age_days: int
    as_of: date

    @property
    def stale(self) -> tuple[DocFreshness, ...]:
        return tuple(d for d in self.docs if d.stale)

    @property
    def is_healthy(self) -> bool:
        """True iff nothing is past the staleness budget — the gate a CI job asserts."""
        return not self.stale

    def render(self) -> str:
        lines = [
            f"Corpus freshness (as of {self.as_of.isoformat()}, "
            f"budget {self.max_age_days}d)",
            "-" * 52,
        ]
        for d in sorted(self.docs, key=lambda x: x.age_days, reverse=True):
            mark = "STALE" if d.stale else "ok"
            lines.append(f"  [{mark:>5}] {d.title:<32} {d.age_days:>4}d old")
        if self.stale:
            lines.append("")
            lines.append(f"ALERT: {len(self.stale)} document(s) past the freshness budget.")
        else:
            lines.append("\nAll documents are within the freshness budget.")
        return "\n".join(lines)


def check_freshness(
    corpus_dir: str | Path,
    *,
    as_of: date | None = None,
    max_age_days: int = DEFAULT_MAX_AGE_DAYS,
) -> FreshnessReport:
    """Read each indexed doc's ``updated`` date and flag the stale ones.

    ``as_of`` defaults to the corpus's own configured "today" (``acl.json``'s ``__today__`` key)
    so the demo is deterministic regardless of the wall clock; pass an explicit date in a real
    monitor (``date.today()``). A document missing an ``updated`` date is treated as **stale**
    (unknown age = assume rotten — fail safe), because an untracked document is exactly the kind
    that silently rots.
    """
    corpus_dir = Path(corpus_dir)
    acl_map = json.loads((corpus_dir / "acl.json").read_text(encoding="utf-8"))
    reference = as_of or _configured_today(acl_map)

    docs: list[DocFreshness] = []
    for filename, entry in sorted(acl_map.items()):
        if filename.startswith("__"):  # config keys like __today__
            continue
        doc_id = Path(filename).stem
        title = entry.get("title", doc_id)
        updated_raw = entry.get("updated")
        if not updated_raw:
            # No date => assume stale (an untracked doc is the one that rots unnoticed).
            docs.append(DocFreshness(doc_id, title, reference, 10**6, stale=True))
            continue
        updated = date.fromisoformat(updated_raw)
        age = (reference - updated).days
        docs.append(
            DocFreshness(doc_id, title, updated, age, stale=age > max_age_days)
        )

    return FreshnessReport(docs=tuple(docs), max_age_days=max_age_days, as_of=reference)


def _configured_today(acl_map: dict) -> date:
    """The corpus's reference 'today' for a deterministic demo; falls back to a fixed date."""
    today = acl_map.get("__today__")
    return date.fromisoformat(today) if today else date(2026, 6, 20)
