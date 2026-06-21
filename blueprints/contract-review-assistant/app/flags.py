"""Flags — every deviation carries a citation (rag-pipeline · Ch 13).

This is where the "no uncited flags" rule of the PLAN is *enforced in the type system*. A
:class:`Flag` cannot be constructed without a ``rule_id`` and the verbatim ``rule_excerpt`` it
was grounded in. The way a flag *gets* that citation is by **composing the ``rag-pipeline``
blueprint**: the firm's risk playbook (``playbook/risk_rules.md``) is ingested → chunked →
embedded → indexed, and each extracted clause is used as a query to retrieve the most relevant
playbook rule. The retrieved rule supplies the ``RULE-ID``, the severity, and the standard
position — so the flag points back at a specific, reviewable source.

We do **not** re-implement retrieval here; we import ``rag_pipeline`` (via ``_compose``) and use
its ``HybridRetriever`` + ``MockReranker`` exactly as the rag demo does. Hybrid search matters
for this job: a rare token like a ``RULE-ID`` or "indemnification" is precisely the keyword-y
signal the dense channel smears and the keyword channel rescues.

Nothing here calls an API. The retriever uses the deterministic mock embedder/reranker by default
(``COMPANION_MOCK=1``), so flagging is free and reproducible.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from . import _compose  # noqa: F401  -- side effect: pattern blueprints onto sys.path

# Imported only after _compose has wired sys.path. The rag-pipeline is composed, never forked.
from rag_pipeline import (  # noqa: E402
    Document,
    HybridRetriever,
    InMemoryVectorStore,
    MockReranker,
    chunk_documents,
    embed_chunks,
)

from .clause_schema import Clause, ClauseType  # noqa: E402

_PLAYBOOK_PATH = Path(__file__).resolve().parent.parent / "playbook" / "risk_rules.md"

# A playbook rule heading looks like:
#   ## RULE-LIAB-001 — Limitation of Liability (liability) — severity: high
_RULE_RE = re.compile(
    r"^##\s+(?P<rule_id>RULE-[A-Z]+-\d+)\s+[—-]\s+(?P<title>.+?)\s+\((?P<ctype>[a-z_]+)\)\s+"
    r"[—-]\s+severity:\s+(?P<severity>\w+)\s*$",
    re.MULTILINE,
)


@dataclass(frozen=True, slots=True)
class PlaybookRule:
    """One parsed rule from the playbook: its id, clause type, severity, and full text."""

    rule_id: str
    title: str
    clause_type: str
    severity: str
    body: str  # the verbatim rule paragraph (heading + standard position + "watch for")


@dataclass(frozen=True, slots=True)
class Flag:
    """A single, **cited** deviation a reviewer should look at.

    A flag is uncreatable without provenance: ``rule_id`` + ``rule_excerpt`` are required fields,
    so "an uncited flag" is not representable. ``severity`` and ``standard_position`` come from the
    retrieved rule; ``confidence`` is the reranker's relevance score for the match (how strongly
    the playbook rule applies to this clause).
    """

    clause_id: str
    clause_type: str
    clause_location: str
    message: str
    rule_id: str
    rule_excerpt: str
    severity: str
    confidence: float

    def cite(self) -> str:
        """One-line citation a reviewer can act on."""
        return f"[{self.rule_id} · severity={self.severity}] {self.clause_location}"


def load_playbook_rules(path: Path | str = _PLAYBOOK_PATH) -> list[PlaybookRule]:
    """Parse ``risk_rules.md`` into structured :class:`PlaybookRule` objects.

    The body of each rule is the text from its ``##`` heading up to the next ``##``/``---``, so the
    excerpt a flag cites is the actual rule prose (standard position + what to watch for), not a
    summary.
    """
    text = Path(path).read_text(encoding="utf-8")
    matches = list(_RULE_RE.finditer(text))
    rules: list[PlaybookRule] = []
    for i, m in enumerate(matches):
        start = m.start()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        body = text[start:end].split("\n---", 1)[0].strip()
        rules.append(
            PlaybookRule(
                rule_id=m.group("rule_id"),
                title=m.group("title").strip(),
                clause_type=m.group("ctype"),
                severity=m.group("severity"),
                body=body,
            )
        )
    if not rules:
        raise ValueError(f"no rules parsed from playbook at {path}")
    return rules


class PlaybookIndex:
    """The retrieval layer over the playbook — a thin wrapper around ``rag_pipeline``.

    Construction ingests every rule as a :class:`~rag_pipeline.Document` (metadata carries the
    ``rule_id``/``severity``/``clause_type``), chunks + embeds them into an
    :class:`~rag_pipeline.InMemoryVectorStore`, and builds a :class:`~rag_pipeline.HybridRetriever`.
    :meth:`match` retrieves + reranks the best rule for a clause. This is the whole "grounding"
    mechanism, and it is *borrowed*, not rebuilt.
    """

    def __init__(self, rules: Iterable[PlaybookRule] | None = None) -> None:
        self.rules = list(rules) if rules is not None else load_playbook_rules()
        self._by_id = {r.rule_id: r for r in self.rules}

        documents = [
            Document(
                id=r.rule_id,
                text=r.body,
                metadata={
                    "rule_id": r.rule_id,
                    "severity": r.severity,
                    "clause_type": r.clause_type,
                    "title": r.title,
                },
            )
            for r in self.rules
        ]
        # Rules are short; one chunk per rule keeps a retrieved chunk == a whole rule, so a
        # citation excerpt is the complete rule, never a fragment.
        chunks = chunk_documents(documents, chunk_size=400, overlap=0)
        self.store = InMemoryVectorStore()
        self.store.add(embed_chunks(chunks))
        self.retriever = HybridRetriever(self.store)
        self.reranker = MockReranker()

    def match(self, clause: Clause, *, k: int = 4) -> tuple[PlaybookRule, float] | None:
        """Return the best ``(rule, confidence)`` for a clause, or ``None`` if nothing retrieves.

        The query blends the clause's type and its text so both the keyword channel (the type
        name, a rare term) and the dense channel (the surrounding language) contribute. The
        reranker then picks the single most on-point rule.
        """
        query = f"{clause.clause_type} {clause.text}"
        hits = self.retriever.retrieve(query, k=k)
        if not hits:
            return None
        reranked = self.reranker.rerank(query, hits, top_n=1)
        if not reranked:
            return None
        best = reranked[0]
        rule_id = str(best.chunk.metadata.get("rule_id", best.chunk.doc_id))
        rule = self._by_id.get(rule_id)
        if rule is None:
            return None
        return rule, best.score


# Phrases in a clause that signal a deviation from the standard position, per clause type. This is
# the deterministic, offline "policy" the demo uses to decide *whether* to flag; the citation for a
# raised flag always comes from the retrieved playbook rule (above), never from this table. A real
# build replaces this with the agent-loop critique pass (see app/review.py) and/or counsel-authored
# rules — but the citation discipline is identical.
_DEVIATION_CUES: dict[ClauseType, tuple[str, ...]] = {
    ClauseType.LIABILITY: ("uncapped", "unlimited liability", "no limit", "without limitation"),
    ClauseType.INDEMNIFICATION: ("sole", "one-way", "without limitation", "defend", "uncapped"),
    ClauseType.TERMINATION: ("immediately", "without notice", "sole discretion", "auto-renew", "automatically renew"),
    ClauseType.CONFIDENTIALITY: ("perpetual", "in perpetuity", "indefinitely"),
    ClauseType.PAYMENT_TERMS: ("net 60", "net 90", "in advance", "prepay"),
    ClauseType.GOVERNING_LAW: ("courts of", "laws of england", "foreign", "arbitration in"),
    ClauseType.WARRANTY: ("as is", "as-is", "no warranty", "disclaims all warranties"),
    ClauseType.IP_OWNERSHIP: ("all intellectual property", "including pre-existing", "background ip", "assigns all"),
    ClauseType.DATA_PROTECTION: ("no dpa", "without a dpa", "any sub-processor", "outside the approved regions", "30 days of becoming aware"),
}


def _deviation_message(clause: Clause) -> str | None:
    """Return a short reason if the clause text trips a deviation cue, else ``None``."""
    cues = _DEVIATION_CUES.get(clause.clause_type, ())
    lowered = clause.text.lower()
    hit = next((c for c in cues if c in lowered), None)
    if hit is None:
        return None
    return f"non-standard {clause.clause_type} language (matched cue: {hit!r})"


def flag_clause(clause: Clause, index: PlaybookIndex) -> Flag | None:
    """Flag one clause iff it deviates from the playbook — with a mandatory citation.

    Returns ``None`` when the clause looks standard. When it deviates, the matched playbook rule
    supplies the citation; if *no* rule retrieves (should not happen with the shipped playbook) we
    refuse to emit an uncited flag and return ``None`` instead — failing closed on the project's
    cardinal rule.
    """
    message = _deviation_message(clause)
    if message is None:
        return None
    matched = index.match(clause)
    if matched is None:
        # No grounding -> no flag. An uncited legal conclusion is worse than a missed one here.
        return None
    rule, confidence = matched
    return Flag(
        clause_id=clause.id,
        clause_type=str(clause.clause_type),
        clause_location=clause.location,
        message=message,
        rule_id=rule.rule_id,
        rule_excerpt=rule.body,
        severity=rule.severity,
        confidence=round(confidence, 4),
    )


def flag_clauses(clauses: Iterable[Clause], index: PlaybookIndex) -> list[Flag]:
    """Flag a list of clauses, dropping the standard ones; ordered high-severity first."""
    flags = [f for c in clauses if (f := flag_clause(c, index)) is not None]
    _order = {"high": 0, "medium": 1, "low": 2}
    flags.sort(key=lambda f: (_order.get(f.severity, 9), f.clause_id))
    return flags
