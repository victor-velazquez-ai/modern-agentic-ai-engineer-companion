"""Runbook + past-incident retrieval — a thin wrapper over the ``rag-pipeline`` pattern (Ch 13).

The copilot's institutional memory lives in two corpora that this module ingests into one
hybrid retriever:

* **runbooks** (``data/runbooks/*.md``) — the "what to do when X" knowledge that today lives in
  a few senior heads, and
* **past incidents** (``data/past_incidents.md``) — "we've seen this before, here's what fixed
  it", which is often the single most useful signal during triage.

We do not fork the pipeline; we **compose** it: ``chunk_documents → embed_chunks →
InMemoryVectorStore → HybridRetriever → MockReranker``, all from ``rag_pipeline``. Hybrid search
matters here specifically because incidents are full of *rare exact terms* — an error string like
``HikariPool-1``, a service name, a deploy id — and dense-only retrieval smears those; the
keyword channel pulls the runbook that names the exact symptom to the top.

Runs offline and free (``COMPANION_MOCK=1`` → deterministic hash embedder + heuristic reranker).
Point :func:`load_corpus` at your own runbook repo to adapt it; the retrieval code is unchanged.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from . import _bootstrap  # noqa: F401  (wire the composed patterns onto sys.path)

from rag_pipeline import (  # noqa: E402  (after the path bootstrap)
    Document,
    HybridRetriever,
    InMemoryVectorStore,
    MockReranker,
    chunk_documents,
    embed_chunks,
)

# data/ sits next to app/ inside the blueprint.
_DATA = Path(__file__).resolve().parents[1] / "data"


@dataclass(frozen=True)
class RunbookHit:
    """A retrieved piece of guidance: where it came from and its text."""

    source: str       # e.g. "runbook:checkout-high-error-rate" or "incident:INC-204"
    kind: str         # "runbook" | "incident"
    text: str
    score: float


def load_corpus(data_dir: Path | str | None = None) -> list[Document]:
    """Load runbooks + past incidents from ``data/`` into ``rag_pipeline.Document`` objects.

    Each runbook file becomes one document tagged ``kind="runbook"``; the past-incidents file is
    split on ``---`` separators into one document per incident, tagged ``kind="incident"``. The
    metadata rides into every chunk so a hit can cite its source.
    """
    base = Path(data_dir) if data_dir is not None else _DATA
    docs: list[Document] = []

    runbook_dir = base / "runbooks"
    if runbook_dir.is_dir():
        for path in sorted(runbook_dir.glob("*.md")):
            docs.append(
                Document(
                    id=f"runbook:{path.stem}",
                    text=path.read_text(encoding="utf-8"),
                    metadata={"kind": "runbook", "source": f"runbook:{path.stem}"},
                )
            )

    incidents_file = base / "past_incidents.md"
    if incidents_file.is_file():
        blocks = [b.strip() for b in incidents_file.read_text(encoding="utf-8").split("\n---\n")]
        for i, block in enumerate(b for b in blocks if b):
            inc_id = _first_token(block) or f"INC-{i:03d}"
            docs.append(
                Document(
                    id=f"incident:{inc_id}",
                    text=block,
                    metadata={"kind": "incident", "source": f"incident:{inc_id}"},
                )
            )
    return docs


def _first_token(block: str) -> str:
    """Best-effort incident id: the first ``INC-...`` token in the block, else ''."""
    for tok in block.replace("#", " ").split():
        if tok.startswith("INC-"):
            return tok.rstrip(":")
    return ""


class Knowledge:
    """A ready-to-query retriever over the copilot's runbooks + incident history.

    Construct once (it ingests + embeds the corpus), then call :meth:`search` per alert. Holds
    only ``rag_pipeline`` objects — there is no bespoke retrieval logic here, which is the point:
    a solution blueprint *uses* the pattern, it does not reimplement it.
    """

    def __init__(self, docs: list[Document] | None = None) -> None:
        self._docs = docs if docs is not None else load_corpus()
        self._store = InMemoryVectorStore()
        chunks = chunk_documents(self._docs, chunk_size=120, overlap=20, structure_aware=True)
        self._store.add(embed_chunks(chunks))
        self._retriever = HybridRetriever(self._store)
        self._reranker = MockReranker()

    def __len__(self) -> int:
        return len(self._store)

    def search(self, query: str, *, k: int = 4) -> list[RunbookHit]:
        """Return the top-``k`` runbook / incident snippets for ``query`` (hybrid → reranked)."""
        fused = self._retriever.retrieve(query, k=max(k * 3, k))
        reranked = self._reranker.rerank(query, fused, top_n=k)
        hits: list[RunbookHit] = []
        for sc in reranked:
            meta = sc.chunk.metadata
            hits.append(
                RunbookHit(
                    source=str(meta.get("source", sc.chunk.doc_id)),
                    kind=str(meta.get("kind", "runbook")),
                    text=sc.chunk.text,
                    score=sc.score,
                )
            )
        return hits
