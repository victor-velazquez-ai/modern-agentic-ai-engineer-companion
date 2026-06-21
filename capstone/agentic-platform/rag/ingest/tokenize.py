"""One tokenizer, shared by every channel (Ch 13).

Dense (mock embedder), keyword search, and the reranker must all see the *same* tokens, or they
disagree about what a document contains — e.g. ``"password,"`` (with a comma) would match in one
channel and not another. Splitting on bare whitespace leaks punctuation into tokens; this module
splits on word characters instead, lowercases, and keeps alphanumerics together.

Deliberately simple (no stemming, no language model) so it stays deterministic and dependency-
free. A production swap (spaCy, a real BPE tokenizer) would replace just this function.
"""

from __future__ import annotations

import re

# Word = a run of unicode letters/digits/underscore. Hyphenated terms split into parts, which is
# fine for lexical overlap (querying "keyword-term" still matches "keyword" and "term").
_WORD = re.compile(r"\w+", re.UNICODE)


def tokens(text: str) -> list[str]:
    """Lowercased word tokens, punctuation stripped, in document order."""
    return _WORD.findall(text.lower())
