"""Loaders — raw sources into :class:`Document` objects (Ch 13, "Loaders").

A loader's only job is to turn *some source* into a :class:`Document`: an id, the extracted
text, and the **provenance metadata** that will ride along into every chunk so retrieval results
can be cited and permission-filtered. The platform's API ``/documents`` route and the ingestion
worker both call these.

What ships here is deliberately format-light — plain text and UTF-8 files — because that is what
stays dependency-free and deterministic for the default MOCK path. Richer extractors (PDF via
``pypdf``, HTML via a parser, Markdown front-matter) are *new loaders behind the same
``Document`` contract*: add a function that produces a :class:`Document`, and chunking, embedding,
and retrieval downstream do not change a line. That is the seam.
"""

from __future__ import annotations

import uuid
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from pathlib import Path

# Suffixes we treat as plain UTF-8 text. A production build adds binary extractors (PDF/DOCX)
# behind the same Document contract; everything below is unchanged.
TEXT_SUFFIXES = frozenset({".txt", ".md", ".markdown", ".rst", ".text"})


@dataclass(frozen=True)
class Document:
    """A source document before chunking.

    ``metadata`` rides along into every chunk so retrieval results can cite source, section,
    permissions, etc. — the thing the platform's permissioned routes and the solution blueprints
    (e.g. a tenant-scoped knowledge assistant) filter on.
    """

    id: str
    text: str
    metadata: dict[str, object] = field(default_factory=dict)


def new_document_id() -> str:
    """A random document id, for loaders that ingest content without a natural key."""
    return uuid.uuid4().hex


def load_text(
    text: str,
    *,
    doc_id: str | None = None,
    metadata: Mapping[str, object] | None = None,
) -> Document:
    """Wrap an in-memory string as a :class:`Document`.

    The smallest loader — used by tests, the demo, and any caller that already has the text
    (e.g. a webhook payload). A missing ``doc_id`` gets a random one.
    """
    return Document(
        id=doc_id or new_document_id(),
        text=text,
        metadata=dict(metadata or {}),
    )


def load_file(
    path: str | Path,
    *,
    doc_id: str | None = None,
    metadata: Mapping[str, object] | None = None,
    encoding: str = "utf-8",
) -> Document:
    """Read a UTF-8 text file into a :class:`Document`, recording its path in metadata.

    Args:
        path: file to read; its suffix must be a known text type (see :data:`TEXT_SUFFIXES`)
            or this raises — we refuse to silently treat a binary blob as text.
        doc_id: stable id; defaults to the file's POSIX path so re-ingesting the same file is
            idempotent (the chunk ids stay stable).
        metadata: extra provenance merged on top of the auto-recorded ``source``/``filename``.
        encoding: text encoding (default UTF-8).

    Raises:
        ValueError: if the suffix is not a recognized text type.
        FileNotFoundError: if ``path`` does not exist.
    """
    p = Path(path)
    if p.suffix.lower() not in TEXT_SUFFIXES:
        raise ValueError(
            f"{p.name!r} is not a recognized text type ({sorted(TEXT_SUFFIXES)}). "
            "Add a binary extractor that returns a Document for this format."
        )
    text = p.read_text(encoding=encoding)
    meta: dict[str, object] = {"source": p.as_posix(), "filename": p.name}
    meta.update(metadata or {})
    return Document(id=doc_id or p.as_posix(), text=text, metadata=meta)


def load_documents(
    sources: Iterable[tuple[str, str] | Document],
    *,
    metadata: Mapping[str, object] | None = None,
) -> list[Document]:
    """Normalize a batch of ``(id, text)`` pairs (or ready :class:`Document` s) into Documents.

    Convenience for callers (and tests) that hold a small corpus in memory. ``metadata`` is
    applied as a base layer under each document's own metadata.
    """
    base = dict(metadata or {})
    out: list[Document] = []
    for src in sources:
        if isinstance(src, Document):
            merged = {**base, **src.metadata}
            out.append(Document(id=src.id, text=src.text, metadata=merged))
        else:
            doc_id, text = src
            out.append(Document(id=doc_id, text=text, metadata=dict(base)))
    return out


def load_directory(
    root: str | Path,
    *,
    suffixes: Iterable[str] | None = None,
    recursive: bool = True,
    metadata: Mapping[str, object] | None = None,
    encoding: str = "utf-8",
) -> list[Document]:
    """Load every text file under ``root`` into Documents, sorted for determinism.

    Args:
        root: directory to scan.
        suffixes: which suffixes to include (default :data:`TEXT_SUFFIXES`). Matching is
            case-insensitive.
        recursive: descend into subdirectories (default ``True``).
        metadata: base provenance merged under each file's auto-recorded metadata.
        encoding: text encoding.

    Returns:
        Documents in sorted path order (stable across machines), so ingestion is reproducible.

    Raises:
        NotADirectoryError: if ``root`` is not a directory.
    """
    root_path = Path(root)
    if not root_path.is_dir():
        raise NotADirectoryError(f"{root_path} is not a directory")
    wanted = {s.lower() for s in (suffixes or TEXT_SUFFIXES)}
    glob = root_path.rglob("*") if recursive else root_path.glob("*")
    files = sorted(p for p in glob if p.is_file() and p.suffix.lower() in wanted)
    return [load_file(p, metadata=metadata, encoding=encoding) for p in files]
