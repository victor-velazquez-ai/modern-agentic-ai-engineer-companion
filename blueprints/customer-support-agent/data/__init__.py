"""Sample data for the customer-support solution: the help-center corpus + a loader.

Swap ``help_center/`` for your real help center + macro corpus — see :func:`load_help_center`.
This package is data + a thin loader only; it imports no pattern blueprint.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:  # avoid importing the sibling at module import; the loader imports it lazily.
    from rag_pipeline import Document

HELP_CENTER_DIR = Path(__file__).resolve().parent / "help_center"


def load_help_center(directory: "Path | None" = None) -> "list[Document]":
    """Load every ``*.md`` help-center doc into a ``rag_pipeline.Document``.

    The file stem becomes the ``doc_id`` (so citations read ``refund-policy``), the first
    ``# heading`` becomes the display ``title``, and the path rides along in metadata. Requires
    the ``rag-pipeline`` sibling on the path (``import app._paths`` does this).
    """
    from rag_pipeline import Document  # lazy: keeps this module import-light

    src = directory or HELP_CENTER_DIR
    docs: list[Document] = []
    for path in sorted(src.glob("*.md")):
        text = path.read_text(encoding="utf-8")
        title = _first_heading(text) or path.stem
        docs.append(
            Document(
                id=path.stem,
                text=text,
                metadata={"title": title, "source": str(path.name)},
            )
        )
    return docs


def _first_heading(markdown: str) -> str | None:
    for line in markdown.splitlines():
        line = line.strip()
        if line.startswith("#"):
            return line.lstrip("#").strip()
    return None
