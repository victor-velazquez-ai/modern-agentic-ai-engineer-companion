"""Loaders that turn the on-disk sample data into the blueprint's input types.

The pipeline itself is data-agnostic: it takes a :class:`~pipeline.stages.Brief` and a
:class:`~pipeline.stages.BrandContext`. This module is the thin adapter from *this solution's
sample files* (``brand/guidelines.md`` and ``data/briefs/*.json``) into those types, so both
``demo.py`` and the eval runner load the corpus the same way — and so the "swap in your own
brand + briefs" adapt step is a one-file change.

Why split the brand markdown into paragraph-sized documents? The ``rag-pipeline`` retriever
chunks and embeds whatever documents it is given; feeding it one giant blob would bury the
single relevant fact among everything else. Splitting on blank lines keeps each fact retrievable
on its own — which is what lets a draft cite *the* supporting fact and lets the guardrails check
"was this grounded?". Nothing here is model-specific; it is plain file I/O over the unforked
``rag-pipeline`` ``Document`` type.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable

from .compose import Document
from .stages import BrandContext, Brief, build_brand_context

# This solution's directories (…/content-production-pipeline/).
_ROOT = Path(__file__).resolve().parents[1]
BRAND_FILE = _ROOT / "brand" / "guidelines.md"
BRIEFS_DIR = _ROOT / "data" / "briefs"


def split_corpus(markdown: str, *, doc_id: str = "brand") -> list[Document]:
    """Split a brand/facts markdown doc into paragraph-sized ``rag-pipeline`` Documents.

    Blank-line-separated blocks become individual documents (heading-only blocks are dropped, so
    a ``## Product facts`` line doesn't become a retrievable "fact"). Each gets a stable id so a
    retrieved snippet can be traced back to its source block.
    """
    docs: list[Document] = []
    blocks = [b.strip() for b in markdown.split("\n\n")]
    n = 0
    for block in blocks:
        # Drop empties and pure-heading blocks ("# ...", "## ..."): they carry no claim.
        if not block or all(line.lstrip().startswith("#") for line in block.splitlines()):
            continue
        docs.append(Document(id=f"{doc_id}::{n}", text=block))
        n += 1
    return docs


def load_brand_documents(path: str | Path = BRAND_FILE) -> list[Document]:
    """Read ``brand/guidelines.md`` and return it as retrievable Documents."""
    text = Path(path).read_text(encoding="utf-8")
    return split_corpus(text)


def load_brand_context(path: str | Path = BRAND_FILE) -> BrandContext:
    """Build the :class:`BrandContext` (the ``rag-pipeline`` retriever) from the brand file."""
    return build_brand_context(load_brand_documents(path))


def load_brief(path: str | Path) -> Brief:
    """Load one brief JSON file into a :class:`Brief`."""
    obj = json.loads(Path(path).read_text(encoding="utf-8"))
    return Brief.from_dict(obj)


def load_briefs(directory: str | Path = BRIEFS_DIR) -> list[Brief]:
    """Load every ``*.json`` brief in ``directory``, sorted by filename for determinism."""
    d = Path(directory)
    return [load_brief(p) for p in sorted(d.glob("*.json"))]


def briefs_by_id(briefs: Iterable[Brief] | None = None) -> dict[str, Brief]:
    """A ``{brief_id: Brief}`` map — what the eval candidate indexes inputs against."""
    return {b.id: b for b in (briefs if briefs is not None else load_briefs())}
