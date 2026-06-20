"""Long-term memory: durable facts/episodes, retrieved by **relevance** (Ch 14).

Working memory forgets on purpose (it is a window). Long-term memory is the opposite: a durable
store you *write a fact into once* and *read back by relevance later*, possibly sessions or
restarts away. The two key reads in the chapter are:

* **relevance** — "what do I know that bears on this query?" (the default read here), and
* **recency** — "what did I learn most recently?" (a tiebreaker / alternative).

The relevance scorer here is a dependency-free lexical overlap (Jaccard over tokens) so the module
runs offline with no embedding model. The retrieval *interface* is what matters: swap
:meth:`LongTermMemory.search`'s scorer for cosine similarity over embeddings (``sentence-
transformers`` / a vector DB) in production and nothing above changes.
"""

from __future__ import annotations

import re
import time
from dataclasses import asdict, dataclass, field
from typing import Any, Iterable

_TOKEN_RE = re.compile(r"[a-z0-9]+")

# A tiny stopword list so high-frequency function words don't manufacture false relevance
# (e.g. an unrelated query sharing only "the"/"in" should score ~0). A production embedding
# retriever handles this implicitly; for the lexical scorer we strip the worst offenders.
_STOPWORDS = frozenset(
    """a an the and or but of to in on at for with is are was were be been being
    this that these those it its as by from into out up down what which who whom
    do does did i you he she we they my your our their me us them""".split()
)


def _tokenize(text: str) -> set[str]:
    return {t for t in _TOKEN_RE.findall(text.lower()) if t not in _STOPWORDS}


def _relevance(query_tokens: set[str], text: str) -> float:
    """Lexical relevance in [0, 1] — Jaccard overlap of token sets.

    Cheap, deterministic, no model. The production swap is cosine similarity over embeddings;
    this keeps the retrieval contract identical while staying offline.
    """
    doc_tokens = _tokenize(text)
    if not query_tokens or not doc_tokens:
        return 0.0
    inter = len(query_tokens & doc_tokens)
    union = len(query_tokens | doc_tokens)
    return inter / union if union else 0.0


@dataclass(slots=True)
class MemoryRecord:
    """A durable fact or episode.

    ``kind`` distinguishes a standing **fact** ("the user's name is Ada") from an **episode** (a
    summary of a past session). ``tags`` allow cheap filtering before the relevance read.
    """

    text: str
    kind: str = "fact"
    tags: tuple[str, ...] = ()
    created_at: float = field(default_factory=time.time)
    record_id: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "MemoryRecord":
        return cls(
            text=data["text"],
            kind=data.get("kind", "fact"),
            tags=tuple(data.get("tags", ())),
            created_at=data.get("created_at", time.time()),
            record_id=data.get("record_id", ""),
        )


@dataclass
class LongTermMemory:
    """An in-memory durable store with a relevance read (and a recency tiebreak).

    This is the *working set* of long-term memory; durability across restarts is provided by the
    persistence backend (see :mod:`memory_module.backends`), which snapshots/restores these
    records. The store itself is backend-agnostic.
    """

    records: list[MemoryRecord] = field(default_factory=list)
    _counter: int = 0

    # -- writes -----------------------------------------------------------------------------

    def add(self, text: str, *, kind: str = "fact", tags: Iterable[str] = ()) -> MemoryRecord:
        """Store a fact/episode and return the persisted record (with a stable id)."""
        self._counter += 1
        record = MemoryRecord(
            text=text,
            kind=kind,
            tags=tuple(tags),
            record_id=f"ltm-{self._counter:06d}",
        )
        self.records.append(record)
        return record

    def add_record(self, record: MemoryRecord) -> None:
        """Insert a fully-formed record (used by restore)."""
        self.records.append(record)
        # keep the id counter ahead of any restored ids so new ids don't collide
        if record.record_id.startswith("ltm-"):
            try:
                self._counter = max(self._counter, int(record.record_id.split("-")[1]))
            except (IndexError, ValueError):
                pass

    # -- reads ------------------------------------------------------------------------------

    def search(
        self,
        query: str,
        *,
        top_k: int = 3,
        kind: str | None = None,
        min_score: float = 0.0,
    ) -> list[MemoryRecord]:
        """Return the ``top_k`` most **relevant** records, recency as the tiebreaker.

        Filtering by ``kind`` (optional) happens before scoring. Records at or below ``min_score``
        are dropped, so an unrelated query returns nothing rather than noise.
        """
        query_tokens = _tokenize(query)
        candidates = self.records if kind is None else [r for r in self.records if r.kind == kind]
        scored = [
            (record, _relevance(query_tokens, record.text))
            for record in candidates
        ]
        scored = [(r, s) for r, s in scored if s > min_score]
        # primary: relevance desc; tiebreak: recency desc
        scored.sort(key=lambda rs: (rs[1], rs[0].created_at), reverse=True)
        return [record for record, _ in scored[:top_k]]

    def recent(self, top_k: int = 3, *, kind: str | None = None) -> list[MemoryRecord]:
        """Return the most **recently** written records (the recency read)."""
        candidates = self.records if kind is None else [r for r in self.records if r.kind == kind]
        return sorted(candidates, key=lambda r: r.created_at, reverse=True)[:top_k]

    def __len__(self) -> int:
        return len(self.records)

    # -- persistence shape ------------------------------------------------------------------

    def snapshot(self) -> list[dict[str, Any]]:
        return [r.to_dict() for r in self.records]

    def restore(self, rows: list[dict[str, Any]]) -> None:
        self.records = []
        self._counter = 0
        for row in rows:
            self.add_record(MemoryRecord.from_dict(row))
