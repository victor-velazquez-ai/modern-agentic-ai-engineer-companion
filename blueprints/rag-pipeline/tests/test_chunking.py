"""Chunking tests — boundaries, overlap, and no-loss (PLAN: test_chunking.py)."""

from __future__ import annotations

import pytest

from rag_pipeline import Document, chunk_documents, chunk_text


def _words(s: str) -> list[str]:
    return s.split()


def test_short_text_is_one_chunk() -> None:
    text = "one two three four five"
    assert chunk_text(text, chunk_size=10, overlap=2) == [text]


def test_windows_have_expected_overlap() -> None:
    # 10 words, size 4, overlap 2 -> step 2 -> windows starting at 0,2,4,6 (8 reaches end via 6).
    words = [f"w{i}" for i in range(10)]
    chunks = chunk_text(" ".join(words), chunk_size=4, overlap=2)

    # Every chunk except possibly the last is exactly chunk_size words.
    for c in chunks[:-1]:
        assert len(_words(c)) == 4

    # Consecutive chunks share exactly `overlap` trailing/leading words.
    for prev, nxt in zip(chunks, chunks[1:]):
        prev_w, next_w = _words(prev), _words(nxt)
        assert prev_w[-2:] == next_w[:2]


def test_no_word_is_lost() -> None:
    words = [f"tok{i}" for i in range(37)]
    text = " ".join(words)
    chunks = chunk_text(text, chunk_size=8, overlap=3)
    covered = {w for c in chunks for w in _words(c)}
    assert covered == set(words)  # every original word survives in some chunk
    # And order is preserved: first chunk starts the doc, last chunk ends it.
    assert _words(chunks[0])[0] == "tok0"
    assert _words(chunks[-1])[-1] == "tok36"


def test_last_chunk_not_duplicated_when_window_aligns() -> None:
    # 8 words, size 4, overlap 2, step 2 -> starts 0,2,4 ; start 4 window [4:8] reaches end.
    words = [f"w{i}" for i in range(8)]
    chunks = chunk_text(" ".join(words), chunk_size=4, overlap=2)
    assert chunks[-1] == "w4 w5 w6 w7"
    # No empty trailing chunk and no run past the end.
    assert all(c.strip() for c in chunks)


def test_structure_aware_respects_paragraphs() -> None:
    text = "alpha beta gamma\n\ndelta epsilon zeta eta theta"
    chunks = chunk_text(text, chunk_size=50, overlap=5, structure_aware=True)
    assert chunks == ["alpha beta gamma", "delta epsilon zeta eta theta"]


def test_structure_aware_windows_long_paragraphs() -> None:
    long_para = " ".join(f"x{i}" for i in range(30))
    text = f"short para\n\n{long_para}"
    chunks = chunk_text(text, chunk_size=8, overlap=2, structure_aware=True)
    assert chunks[0] == "short para"
    # The long paragraph got windowed into multiple chunks.
    assert len(chunks) > 2


def test_empty_text_yields_no_chunks() -> None:
    assert chunk_text("   \n  ") == []


@pytest.mark.parametrize(
    "size,overlap",
    [(0, 0), (-1, 0), (5, 5), (5, 6), (5, -1)],
)
def test_invalid_params_raise(size: int, overlap: int) -> None:
    with pytest.raises(ValueError):
        chunk_text("a b c d e f", chunk_size=size, overlap=overlap)


def test_chunk_documents_ids_and_metadata() -> None:
    docs = [
        Document(id="doc-a", text=" ".join(f"a{i}" for i in range(20)),
                 metadata={"source": "kb", "section": "intro"}),
        Document(id="doc-b", text="b0 b1 b2"),
    ]
    chunks = chunk_documents(docs, chunk_size=8, overlap=2)

    # Stable, namespaced ids.
    assert chunks[0].id == "doc-a::0"
    assert all(c.id == f"{c.doc_id}::{c.index}" for c in chunks)

    # Metadata propagates from document onto each chunk.
    a_chunks = [c for c in chunks if c.doc_id == "doc-a"]
    assert all(c.metadata["source"] == "kb" for c in a_chunks)

    # Idempotent: re-chunking the same corpus yields identical ids (stable identity).
    again = chunk_documents(docs, chunk_size=8, overlap=2)
    assert [c.id for c in chunks] == [c.id for c in again]
