"""Permissioned ingestion — carry each doc's ACL groups into the index (Ch 13, 43).

A permissioned assistant is only as safe as its *ingestion*. The filter-before-retrieval rule
downstream can only work if every chunk already knows which groups may read it — so the access
decision must be **stamped onto the data at ingest time**, not bolted on at query time. This
module is that stamp: it loads the corpus, attaches each document's ACL groups to its metadata,
chunks it (the ACL rides along onto every chunk, because ``rag_pipeline.chunk_documents`` copies
document metadata onto each chunk), embeds, and adds to the store.

It composes the **rag-pipeline** pattern blueprint by relative import — it does **not** fork it.
The only thing this solution adds on top of the generic pipeline is the ACL metadata key and a
loader that reads it from the corpus.

Adapting this to your sources
-----------------------------
Point :func:`load_corpus` at your real systems and map their *native* ACLs onto the ``acl``
group set:

* a wiki space's read-permission group(s),
* a drive folder's sharing groups,
* a Slack channel's membership,
* a ticket queue's team.

The contract is just: **every document arrives with a non-empty set of group names**, and those
names are the same ones :mod:`app.identity` resolves callers to. Keep that and the rest holds.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Iterable

# Compose the rag-pipeline pattern blueprint (sibling under blueprints/), without forking it.
# parents[2] of this file is the blueprints/ root: .../blueprints/internal-knowledge-assistant/ingest/sync_acl.py
_BLUEPRINTS = Path(__file__).resolve().parents[2]
_RAG_SRC = _BLUEPRINTS / "rag-pipeline" / "src"
if _RAG_SRC.is_dir() and str(_RAG_SRC) not in sys.path:
    sys.path.insert(0, str(_RAG_SRC))

from rag_pipeline import (  # noqa: E402  (after sys.path wiring)
    Document,
    InMemoryVectorStore,
    chunk_documents,
    embed_chunks,
)

# The metadata key that holds a document's ACL groups (a list of group names). The query-path
# filter (app.kb_assistant) reads exactly this key, so it is the contract between ingest and
# retrieval. One name, one place.
ACL_METADATA_KEY = "acl"


def load_corpus(corpus_dir: str | Path) -> list[Document]:
    """Load the demo corpus: ``*.md`` bodies + a sidecar ``acl.json`` of per-doc groups.

    The layout is deliberately boring so the *mechanism* is the lesson:

    * ``corpus_dir/<doc>.md`` — the document body. Its first ``# `` heading becomes the title.
    * ``corpus_dir/acl.json`` — ``{"<doc>.md": {"acl": ["group", ...], "source": "..."}}``.

    A document missing from ``acl.json`` (or with an empty group list) is **dropped with no
    silent default** — failing closed is the whole point. In a real connector the ACL would come
    from the source system's own permission API, not a sidecar file; the shape is what matters.
    """
    corpus_dir = Path(corpus_dir)
    acl_path = corpus_dir / "acl.json"
    acl_map: dict[str, dict] = {}
    if acl_path.exists():
        acl_map = json.loads(acl_path.read_text(encoding="utf-8"))

    documents: list[Document] = []
    for md_path in sorted(corpus_dir.glob("*.md")):
        entry = acl_map.get(md_path.name)
        if not entry:
            # Fail closed: no ACL record => not indexed. Never default to "everyone".
            continue
        groups = [g for g in entry.get(ACL_METADATA_KEY, []) if isinstance(g, str) and g]
        if not groups:
            continue
        text = md_path.read_text(encoding="utf-8").strip()
        documents.append(
            Document(
                id=md_path.stem,
                text=text,
                metadata={
                    "title": _first_heading(text) or md_path.stem,
                    "source": entry.get("source", md_path.name),
                    ACL_METADATA_KEY: tuple(groups),
                },
            )
        )
    return documents


def build_index(
    documents: Iterable[Document],
    *,
    chunk_size: int = 80,
    overlap: int = 16,
) -> InMemoryVectorStore:
    """Chunk + embed + index a corpus, ACL metadata intact on every chunk.

    Returns an :class:`~rag_pipeline.stores.memory.InMemoryVectorStore` ready for the assistant.
    ``chunk_documents`` copies each document's metadata (including the ``acl`` key) onto every
    chunk, so the permission tag survives chunking — which is exactly what the query-path filter
    relies on.
    """
    chunks = chunk_documents(list(documents), chunk_size=chunk_size, overlap=overlap)
    store = InMemoryVectorStore()
    store.add(embed_chunks(chunks))
    return store


def doc_acl(metadata: dict) -> frozenset[str]:
    """Read a chunk/doc's ACL groups out of its metadata as a ``frozenset``.

    Centralized so the filter and any audit code read the ACL the same way. Missing/empty ->
    empty set, which :meth:`app.identity.Principal.can_read` treats as *nobody* (fail closed).
    """
    raw = metadata.get(ACL_METADATA_KEY, ())
    if isinstance(raw, str):  # tolerate a single group stored as a bare string
        raw = (raw,)
    return frozenset(g for g in raw if isinstance(g, str) and g)


def _first_heading(text: str) -> str:
    """The first Markdown ``# `` heading, used as a human-readable document title."""
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("# "):
            return line[2:].strip()
    return ""
