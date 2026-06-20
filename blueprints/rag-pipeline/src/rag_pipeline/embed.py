"""Embedding step (Ch 13, "Embeddings").

The pipeline turns text into vectors here. In the book's stack the *real* embedding call goes
through the **llm-gateway** blueprint (one door to every model call), so this module asks the
gateway for an embedder when ``COMPANION_MOCK=0`` and a key is present — and falls back to a
deterministic, dependency-free :class:`MockEmbedder` otherwise. That fallback is what makes the
whole pipeline runnable offline with **no API spend by default**.

The mock is not random noise: it is a stable feature-hashing embedder. The same text always
maps to the same unit vector, and texts that share words land near each other in cosine space,
so retrieval behaves *sensibly* (not just deterministically) without a model.

Composition note
----------------
The gateway is imported lazily and optionally (see :func:`_try_gateway_embedder`). The
blueprint depends on ``llm-gateway`` *conceptually* but never *requires* it to run; if the
gateway package is not on the path, the mock is used. Code here imports only stdlib + the
optional gateway.
"""

from __future__ import annotations

import hashlib
import math
import os
from dataclasses import dataclass
from typing import Protocol, Sequence, runtime_checkable

from .ingest import Chunk
from .tokenize import tokens as _tokenize

DEFAULT_EMBEDDING_DIM = 256


@dataclass(frozen=True)
class EmbeddedChunk:
    """A chunk paired with its (unit-norm) embedding vector."""

    chunk: Chunk
    vector: tuple[float, ...]


@runtime_checkable
class Embedder(Protocol):
    """Anything that can turn text into fixed-dimension vectors.

    Kept deliberately tiny so a gateway-backed embedder, a sentence-transformers embedder, or
    the mock all satisfy it interchangeably.
    """

    dim: int

    def embed(self, texts: Sequence[str]) -> list[tuple[float, ...]]:
        """Return one unit-norm vector per input text, in order."""
        ...


def _l2_normalize(vec: list[float]) -> tuple[float, ...]:
    norm = math.sqrt(sum(x * x for x in vec))
    if norm == 0.0:
        return tuple(vec)
    return tuple(x / norm for x in vec)


class MockEmbedder:
    """Deterministic, offline embedder via feature hashing.

    For each whitespace token we hash ``token`` into a bucket in ``[0, dim)`` and accumulate a
    signed weight (the sign comes from a second hash). The summed vector is L2-normalized so
    cosine similarity is just a dot product. Properties that make it *useful*, not just
    reproducible:

      * **Stable:** identical text -> identical vector, every run, every machine.
      * **Semantically monotone on overlap:** more shared words -> higher cosine, so a query's
        nearest neighbors are the chunks that actually share its terms.

    It is *not* a substitute for a learned embedder (no synonymy, no semantics beyond surface
    tokens) — and the README says so. It exists to make the pipeline honest to run for free.
    """

    def __init__(self, dim: int = DEFAULT_EMBEDDING_DIM) -> None:
        if dim <= 0:
            raise ValueError("embedding dim must be > 0")
        self.dim = dim

    @staticmethod
    def _tokens(text: str) -> list[str]:
        return _tokenize(text)

    def _embed_one(self, text: str) -> tuple[float, ...]:
        vec = [0.0] * self.dim
        for token in self._tokens(text):
            digest = hashlib.sha256(token.encode("utf-8")).digest()
            bucket = int.from_bytes(digest[:4], "big") % self.dim
            sign = 1.0 if digest[4] & 1 else -1.0
            vec[bucket] += sign
        return _l2_normalize(vec)

    def embed(self, texts: Sequence[str]) -> list[tuple[float, ...]]:
        return [self._embed_one(t) for t in texts]


def _try_gateway_embedder(dim: int) -> Embedder | None:
    """Best-effort: borrow a real embedder from the ``llm-gateway`` blueprint if available.

    The gateway is a sibling blueprint (``../llm-gateway/src``). We add it to ``sys.path`` and
    try to import a factory. Any failure (package not built yet, no key, import error) returns
    ``None`` so the caller transparently falls back to the mock. This is the seam the solution
    blueprints rely on: same import surface, real embeddings when the gateway is wired in.
    """
    import sys
    from pathlib import Path

    gateway_src = Path(__file__).resolve().parents[3] / "llm-gateway" / "src"
    if gateway_src.is_dir() and str(gateway_src) not in sys.path:
        sys.path.insert(0, str(gateway_src))
    try:  # pragma: no cover - exercised only when the gateway is present + keyed.
        from llm_gateway import get_embedder as gateway_get_embedder  # type: ignore

        embedder = gateway_get_embedder(dim=dim)
        if isinstance(embedder, Embedder):
            return embedder
    except Exception:
        return None
    return None


def get_embedder(*, dim: int = DEFAULT_EMBEDDING_DIM) -> Embedder:
    """Return the embedder to use, honoring the MOCK switch and the gateway seam.

    - ``COMPANION_MOCK=1`` (default) -> always the deterministic :class:`MockEmbedder`.
    - ``COMPANION_MOCK=0`` -> try the ``llm-gateway`` real embedder; if it is unavailable
      (blueprint not built, no key), fall back to the mock so nothing breaks at import time.
    """
    mock = os.getenv("COMPANION_MOCK", "1") != "0"
    if not mock:
        gateway = _try_gateway_embedder(dim)
        if gateway is not None:
            return gateway
    return MockEmbedder(dim=dim)


def embed_chunks(
    chunks: Sequence[Chunk], *, embedder: Embedder | None = None
) -> list[EmbeddedChunk]:
    """Embed a batch of chunks (defaults to the env-selected embedder)."""
    embedder = embedder or get_embedder()
    vectors = embedder.embed([c.text for c in chunks])
    return [EmbeddedChunk(chunk=c, vector=v) for c, v in zip(chunks, vectors)]


def embed_query(query: str, *, embedder: Embedder | None = None) -> tuple[float, ...]:
    """Embed a single query string with the same embedder used for the corpus."""
    embedder = embedder or get_embedder()
    return embedder.embed([query])[0]
