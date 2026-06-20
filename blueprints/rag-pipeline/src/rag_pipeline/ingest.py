"""Loaders + chunking — the first stage of the pipeline (Ch 13, "Chunking").

A retriever can only return what ingestion preserved. The senior judgment lives in the
chunking strategy, not the loader: chunks must be **small enough to be specific** yet **large
enough to be self-contained**, and **overlap** so a fact split across a boundary survives in at
least one chunk. This module keeps that decision in one tested place.

Two strategies ship here:

- :func:`chunk_text` — sliding window over **words** with a configurable size and overlap.
  Word-based (not character-based) keeps tokens roughly proportional and avoids cutting words
  in half; the book's rule of thumb (~200-400 tokens, ~10-20% overlap) maps cleanly onto it.
- *structure-aware* splitting on blank-line paragraph boundaries (``structure_aware=True``),
  which respects the document's own seams before falling back to the window. Markdown/HTML
  loaders would plug in here in a fuller build.

Nothing here needs a model or a network call.
"""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass, field
from typing import Iterable

# Sensible defaults (book Ch 13 rule of thumb). Word counts, not tokens, but close enough
# for a window: ~280 words is roughly ~370 tokens of English prose.
DEFAULT_CHUNK_SIZE = 120
DEFAULT_CHUNK_OVERLAP = 20
_PARAGRAPH_SPLIT = re.compile(r"\n\s*\n")
_WORD_SPLIT = re.compile(r"\S+")


@dataclass(frozen=True)
class Document:
    """A source document before chunking.

    ``metadata`` rides along into every chunk so retrieval results can cite source, section,
    permissions, etc. — the thing solution blueprints (e.g. permissioned knowledge assistant)
    filter on.
    """

    id: str
    text: str
    metadata: dict[str, object] = field(default_factory=dict)


@dataclass(frozen=True)
class Chunk:
    """A retrievable unit of a document, with a stable id and provenance."""

    id: str
    doc_id: str
    text: str
    index: int  # position of this chunk within its document (0-based)
    metadata: dict[str, object] = field(default_factory=dict)


def _words(text: str) -> list[str]:
    return _WORD_SPLIT.findall(text)


def chunk_text(
    text: str,
    *,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    overlap: int = DEFAULT_CHUNK_OVERLAP,
    structure_aware: bool = False,
) -> list[str]:
    """Split ``text`` into overlapping windows of words.

    Args:
        text: The raw document text.
        chunk_size: Target window length in **words**. Must be > 0.
        overlap: Number of words shared between consecutive windows. Must be in
            ``[0, chunk_size)`` so the window always advances (no infinite loop).
        structure_aware: If ``True``, split on blank-line paragraph boundaries first and only
            window paragraphs that exceed ``chunk_size`` — preserving the document's own seams.

    Returns:
        The chunk strings in document order. Guarantees:
          * every word of the input appears in at least one chunk (no silent loss), and
          * consecutive windows share exactly ``min(overlap, len(prev))`` trailing words.

    Raises:
        ValueError: if ``chunk_size <= 0`` or ``overlap`` is out of range.
    """
    if chunk_size <= 0:
        raise ValueError(f"chunk_size must be > 0, got {chunk_size}")
    if not 0 <= overlap < chunk_size:
        raise ValueError(
            f"overlap must satisfy 0 <= overlap < chunk_size; got overlap={overlap}, "
            f"chunk_size={chunk_size}"
        )

    if structure_aware:
        chunks: list[str] = []
        for para in _PARAGRAPH_SPLIT.split(text):
            para = para.strip()
            if not para:
                continue
            if len(_words(para)) <= chunk_size:
                chunks.append(para)
            else:
                chunks.extend(
                    chunk_text(para, chunk_size=chunk_size, overlap=overlap)
                )
        return chunks

    words = _words(text)
    if not words:
        return []
    if len(words) <= chunk_size:
        return [" ".join(words)]

    step = chunk_size - overlap
    chunks = []
    for start in range(0, len(words), step):
        window = words[start : start + chunk_size]
        chunks.append(" ".join(window))
        if start + chunk_size >= len(words):
            break
    return chunks


def chunk_documents(
    documents: Iterable[Document],
    *,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    overlap: int = DEFAULT_CHUNK_OVERLAP,
    structure_aware: bool = False,
) -> list[Chunk]:
    """Chunk a corpus into :class:`Chunk` objects with stable, deterministic ids.

    Each chunk's id is ``{doc_id}::{index}`` so re-ingesting the same corpus is idempotent
    (a chunk keeps its identity), and document metadata is copied onto every chunk for citation
    and filtering downstream.
    """
    out: list[Chunk] = []
    for doc in documents:
        pieces = chunk_text(
            doc.text,
            chunk_size=chunk_size,
            overlap=overlap,
            structure_aware=structure_aware,
        )
        for index, piece in enumerate(pieces):
            out.append(
                Chunk(
                    id=f"{doc.id}::{index}",
                    doc_id=doc.id,
                    text=piece,
                    index=index,
                    metadata=dict(doc.metadata),
                )
            )
    return out


def new_document_id() -> str:
    """A random document id, for loaders that ingest content without a natural key."""
    return uuid.uuid4().hex
