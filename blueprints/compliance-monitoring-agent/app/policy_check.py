"""policy_check — grounds every flag in a real rule, via the ``rag-pipeline`` blueprint (Ch 13).

A compliance flag that cannot point at the rule it broke is worthless: the human adjudicator
cannot act on it and an auditor cannot defend it. So the centerpiece of this solution is
*retrieval over the policy corpus* — we index the policies once, and for each monitored item we
retrieve the most relevant rule and attach it as the flag's **basis**.

This module is pure composition. It imports ``rag-pipeline``'s public surface
(``Document``/``chunk_documents``/``embed_chunks``/``InMemoryVectorStore``/``HybridRetriever``/
``MockReranker``) and wires the standard pipeline:

    parse policies.md -> Document per rule -> chunk -> embed -> store -> hybrid retrieve -> rerank

Hybrid (dense + keyword) retrieval matters here specifically: policy violations hinge on **rare,
exact terms** — a rule id, "sanctions", "10,000", "guaranteed", "MNPI" — that a dense-only signal
smears among look-alikes. The keyword channel, IDF-weighting those rare terms, pulls the right
rule to the top. That is the rag-pipeline's whole reason for being, used as designed.

Nothing here spends tokens under ``COMPANION_MOCK=1`` (the default): the pipeline uses its
deterministic hash embedder and heuristic reranker.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from . import add_blueprint_paths

add_blueprint_paths()

from rag_pipeline import (  # noqa: E402  (path wired above)
    Document,
    HybridRetriever,
    InMemoryVectorStore,
    MockReranker,
    chunk_documents,
    embed_chunks,
)

# policies.md lives next to this app/ package, under ../policy/.
DEFAULT_POLICY_PATH = Path(__file__).resolve().parent.parent / "policy" / "policies.md"

# A rule heading looks like "## COMM-01 — No sharing of customer PII ..." — capture id + title.
_RULE_HEADING = re.compile(r"^##\s+([A-Z]+-\d+)\s+[—-]\s+(.*)$")


@dataclass(frozen=True)
class PolicyRule:
    """One rule parsed from the corpus: a stable id, a title, and the full text that grounds it."""

    rule_id: str
    title: str
    text: str


@dataclass(frozen=True)
class PolicyMatch:
    """The most relevant rule for an item, with the retrieval score that surfaced it.

    ``rule_id`` is what a flag cites; ``snippet`` is the human-readable basis shown to the
    adjudicator and written to the audit log. ``benign`` is True when the best match is the
    explicit "routine business communication" rule (GEN-01), i.e. retrieval found no real
    violation to ground — the screener uses this to avoid false positives.
    """

    rule_id: str
    title: str
    snippet: str
    score: float

    @property
    def benign(self) -> bool:
        return self.rule_id == "GEN-01"


def parse_policies(path: str | Path = DEFAULT_POLICY_PATH) -> list[PolicyRule]:
    """Parse ``policies.md`` into one :class:`PolicyRule` per ``##`` rule heading.

    The body of a rule is everything up to the next heading. We skip the document's intro
    blockquote/preamble, so only real rules become retrievable documents.
    """
    text = Path(path).read_text(encoding="utf-8")
    rules: list[PolicyRule] = []
    current: dict[str, object] | None = None
    body: list[str] = []

    def _flush() -> None:
        if current is not None:
            rules.append(
                PolicyRule(
                    rule_id=str(current["rule_id"]),
                    title=str(current["title"]),
                    text="\n".join(body).strip(),
                )
            )

    for line in text.splitlines():
        m = _RULE_HEADING.match(line.strip())
        if m:
            _flush()
            current = {"rule_id": m.group(1), "title": m.group(2).strip()}
            body = [f"{m.group(1)} {m.group(2).strip()}"]
        elif current is not None:
            body.append(line)
    _flush()
    if not rules:
        raise ValueError(f"no '## RULE-ID — title' rules found in {path}")
    return rules


class PolicyIndex:
    """A retrieval index over the policy corpus — the ``rag-pipeline`` composed for compliance.

    Build it once (``PolicyIndex.from_corpus()``); then call :meth:`most_relevant_rule` per item.
    The index *is* the rag-pipeline: a vector store of embedded policy chunks behind a hybrid
    retriever and a reranker. Construction and querying are deterministic and offline by default.
    """

    def __init__(self, rules: list[PolicyRule]) -> None:
        self.rules = {r.rule_id: r for r in rules}
        documents = [
            Document(
                id=r.rule_id,
                text=r.text,
                metadata={"rule_id": r.rule_id, "title": r.title},
            )
            for r in rules
        ]
        # Small rules -> keep each rule a single self-contained chunk where possible.
        chunks = chunk_documents(documents, chunk_size=120, overlap=20)
        self.store = InMemoryVectorStore()
        self.store.add(embed_chunks(chunks))
        self.retriever = HybridRetriever(self.store)
        self.reranker = MockReranker()

    @classmethod
    def from_corpus(cls, path: str | Path = DEFAULT_POLICY_PATH) -> "PolicyIndex":
        """Parse the corpus file and build the index in one call."""
        return cls(parse_policies(path))

    def most_relevant_rule(self, query: str, *, k: int = 4) -> PolicyMatch:
        """Retrieve + rerank the policy corpus and return the single best-matching rule.

        ``query`` is the text of the monitored item (a message or a transaction description). We
        pull a hybrid shortlist, rerank it for precision, and return the top rule as the flag's
        basis. The returned ``snippet`` is the rule's own text — so the flag literally quotes the
        rule it cites.
        """
        hits = self.retriever.retrieve(query, k=k)
        if not hits:
            # Empty query / no overlap: treat as benign rather than inventing a violation.
            gen = self.rules.get("GEN-01")
            return PolicyMatch(
                rule_id="GEN-01",
                title=gen.title if gen else "Routine business communication",
                snippet=gen.text if gen else "",
                score=0.0,
            )
        reranked = self.reranker.rerank(query, hits, top_n=1)
        top = reranked[0]
        rule_id = str(top.chunk.metadata.get("rule_id", top.chunk.doc_id))
        rule = self.rules.get(rule_id)
        title = str(top.chunk.metadata.get("title", rule.title if rule else rule_id))
        snippet = rule.text if rule else top.chunk.text
        return PolicyMatch(rule_id=rule_id, title=title, snippet=snippet, score=top.score)
