"""Load the source corpus and turn it into a retrievable index (composes ``rag-pipeline``).

For due diligence the corpus is a *mix*: internal data-room documents and "web" findings.
This module reads ``data/sources/*.md``, tags each with a ``doc_type`` (``internal`` / ``web``)
and a human-readable citation label, then runs the **rag-pipeline** ingest → embed → store
path so the retrieval workers can do hybrid search over it.

Nothing here is forked from ``rag-pipeline``: we import :class:`Document`, :func:`chunk_documents`,
:func:`embed_chunks`, and :class:`InMemoryVectorStore` and use them as-is. The only domain
knowledge added is *what a source is* and *how to cite it*.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from . import _compose  # noqa: F401 — side effect: puts sibling src/ on sys.path

# Imported from the sibling rag-pipeline blueprint (NOT forked) — see app/_compose.py.
from rag_pipeline import (  # type: ignore  # noqa: E402
    Document,
    InMemoryVectorStore,
    chunk_documents,
    embed_chunks,
)

# Where the committed sample corpus lives, relative to this file.
_DATA_DIR = Path(__file__).resolve().parents[1] / "data"
_SOURCES_DIR = _DATA_DIR / "sources"


@dataclass(frozen=True)
class Source:
    """One source document plus the metadata a citation needs.

    ``doc_type`` is ``"internal"`` (data-room) or ``"web"`` (open-web finding). ``citation`` is
    the short human-readable label that appears next to a claim in the final brief, e.g.
    ``[internal-002-acme-financials]``. ``title`` is a friendlier description for the source list.
    """

    doc_id: str
    text: str
    doc_type: str
    title: str

    @property
    def citation(self) -> str:
        """The marker that grounds a claim — the bracketed source id."""
        return f"[{self.doc_id}]"


def _infer_type(doc_id: str) -> str:
    """Internal data-room docs are prefixed ``internal-``; everything else is treated as web."""
    return "internal" if doc_id.startswith("internal") else "web"


def _title_from(text: str, doc_id: str) -> str:
    """Use the first Markdown ``# `` heading as the title, falling back to the id."""
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("# "):
            return line[2:].strip()
    return doc_id


def load_sources(sources_dir: Path | str = _SOURCES_DIR) -> list[Source]:
    """Read every ``*.md`` under ``sources_dir`` into a :class:`Source`, sorted by id.

    Sorting keeps ingestion deterministic (so MOCK retrieval and the evals are reproducible).
    """
    directory = Path(sources_dir)
    if not directory.is_dir():
        raise FileNotFoundError(f"source corpus not found: {directory}")
    out: list[Source] = []
    for path in sorted(directory.glob("*.md")):
        doc_id = path.stem
        text = path.read_text(encoding="utf-8")
        out.append(
            Source(
                doc_id=doc_id,
                text=text,
                doc_type=_infer_type(doc_id),
                title=_title_from(text, doc_id),
            )
        )
    if not out:
        raise FileNotFoundError(f"no .md source documents in {directory}")
    return out


def build_store(sources: Iterable[Source]) -> InMemoryVectorStore:
    """Ingest + embed the sources into a rag-pipeline :class:`InMemoryVectorStore`.

    Each :class:`Source` becomes a rag-pipeline :class:`Document` whose ``metadata`` carries the
    ``doc_type`` and ``title`` so retrieval results can be cited and filtered downstream. We use
    the blueprint's own chunker and (mock-by-default) embedder unchanged.
    """
    documents = [
        Document(
            id=s.doc_id,
            text=s.text,
            metadata={"doc_id": s.doc_id, "doc_type": s.doc_type, "title": s.title},
        )
        for s in sources
    ]
    chunks = chunk_documents(documents)
    store = InMemoryVectorStore()
    store.add(embed_chunks(chunks))
    return store


@dataclass
class Corpus:
    """The loaded corpus: the sources, an index from id → source, and the vector store."""

    sources: tuple[Source, ...]
    store: InMemoryVectorStore

    def by_id(self) -> dict[str, Source]:
        return {s.doc_id: s for s in self.sources}


def load_corpus(sources_dir: Path | str = _SOURCES_DIR) -> Corpus:
    """One call: read the sample corpus and build its retrievable store."""
    sources = load_sources(sources_dir)
    store = build_store(sources)
    return Corpus(sources=tuple(sources), store=store)
