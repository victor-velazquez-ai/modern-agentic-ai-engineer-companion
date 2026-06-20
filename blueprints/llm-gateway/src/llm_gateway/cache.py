"""Response cache (Ch 40) — exact + semantic, with cost-aware keys.

Two layers, cheapest first:

1. **Exact cache** — a dict keyed by a hash of the *cache-relevant* request fields
   (model, system, messages, max_tokens, effort). A repeated identical prompt
   never reaches the provider. O(1), zero false positives.
2. **Semantic cache** — embeds the prompt and returns a stored response when the
   nearest neighbour is within a cosine-similarity ``threshold``. Catches
   paraphrases the exact cache misses ("reset my password" vs "how do I reset my
   password"), at the cost of *recall risk*: too low a threshold and you serve a
   stale-but-similar answer. That trade-off is the whole point of the README's
   "exact-vs-semantic cost/recall" discussion.

The embedder is pluggable. The default :func:`hashing_embedder` is a deterministic
bag-of-words hash — good enough to demo near-hits offline with **no extra deps**.
In production you'd pass a real embedding function (e.g. ``sentence-transformers``
or an embeddings API); the seam is identical.
"""

from __future__ import annotations

import hashlib
import math
import re
from dataclasses import dataclass, field
from typing import Callable, Sequence

from .ports import ChatRequest, ChatResponse

Embedder = Callable[[str], Sequence[float]]

_WORD_RE = re.compile(r"[a-z0-9']+")


# ---------------------------------------------------------------------------
# Keying
# ---------------------------------------------------------------------------


def cache_key(request: ChatRequest) -> str:
    """Stable hash over the fields that change the answer.

    ``metadata`` is intentionally excluded — two requests that differ only in a
    tracing tag should share a cache entry. This is the "cost-aware key": include
    exactly what affects output, nothing that doesn't.
    """

    parts = [
        request.model,
        request.system or "",
        str(request.max_tokens),
        request.effort or "",
    ]
    parts.extend(f"{m.role}:{m.content}" for m in request.messages)
    blob = "\x1f".join(parts)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def prompt_text(request: ChatRequest) -> str:
    """The text the semantic layer embeds (system + all turns)."""

    head = (request.system or "").strip()
    body = " ".join(m.content for m in request.messages)
    return f"{head} {body}".strip()


# ---------------------------------------------------------------------------
# Default offline embedder
# ---------------------------------------------------------------------------


def hashing_embedder(text: str, dim: int = 256) -> list[float]:
    """Deterministic bag-of-words hashing embedding (L2-normalized).

    No model, no network, no extra dependency. Identical text → identical vector;
    overlapping vocabulary → high cosine similarity. Good enough to *demonstrate*
    semantic near-hits in CI; swap in a real embedder for production recall.
    """

    vec = [0.0] * dim
    for token in _WORD_RE.findall(text.lower()):
        h = int(hashlib.md5(token.encode("utf-8")).hexdigest(), 16)
        vec[h % dim] += 1.0
    norm = math.sqrt(sum(v * v for v in vec))
    if norm == 0.0:
        return vec
    return [v / norm for v in vec]


def cosine_similarity(a: Sequence[float], b: Sequence[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0.0 or nb == 0.0:
        return 0.0
    return dot / (na * nb)


# ---------------------------------------------------------------------------
# Cache
# ---------------------------------------------------------------------------


@dataclass
class _SemanticEntry:
    embedding: Sequence[float]
    response: ChatResponse


@dataclass
class ResponseCache:
    """Exact + semantic response cache.

    Set ``semantic=False`` for an exact-only cache (no false positives, lower
    recall). ``threshold`` is the cosine-similarity bar for a semantic hit;
    higher is safer (fewer wrong answers), lower is cheaper (more hits).
    """

    embedder: Embedder = hashing_embedder
    threshold: float = 0.95
    semantic: bool = True

    _exact: dict[str, ChatResponse] = field(default_factory=dict)
    _semantic: list[_SemanticEntry] = field(default_factory=list)
    exact_hits: int = 0
    semantic_hits: int = 0
    misses: int = 0

    def get(self, request: ChatRequest) -> ChatResponse | None:
        """Return a cached response (marked ``cached=True``) or ``None``."""

        key = cache_key(request)
        hit = self._exact.get(key)
        if hit is not None:
            self.exact_hits += 1
            return self._mark(hit)

        if self.semantic:
            query = self.embedder(prompt_text(request))
            best: ChatResponse | None = None
            best_score = self.threshold
            for entry in self._semantic:
                score = cosine_similarity(query, entry.embedding)
                if score >= best_score:
                    best_score = score
                    best = entry.response
            if best is not None:
                self.semantic_hits += 1
                return self._mark(best)

        self.misses += 1
        return None

    def put(self, request: ChatRequest, response: ChatResponse) -> None:
        """Store a freshly-computed response in both layers."""

        self._exact[cache_key(request)] = response
        if self.semantic:
            self._semantic.append(
                _SemanticEntry(
                    embedding=self.embedder(prompt_text(request)),
                    response=response,
                )
            )

    @staticmethod
    def _mark(response: ChatResponse) -> ChatResponse:
        if response.cached:
            return response
        # Re-stamp so callers/metering can tell a hit from a fresh call.
        return ChatResponse(
            text=response.text,
            model=response.model,
            usage=response.usage,
            provider=response.provider,
            stop_reason=response.stop_reason,
            cached=True,
        )

    @property
    def hit_rate(self) -> float:
        total = self.exact_hits + self.semantic_hits + self.misses
        if total == 0:
            return 0.0
        return (self.exact_hits + self.semantic_hits) / total

    def stats(self) -> dict[str, float | int]:
        return {
            "exact_hits": self.exact_hits,
            "semantic_hits": self.semantic_hits,
            "misses": self.misses,
            "hit_rate": round(self.hit_rate, 4),
            "size": len(self._exact),
        }


__all__ = [
    "ResponseCache",
    "Embedder",
    "hashing_embedder",
    "cosine_similarity",
    "cache_key",
    "prompt_text",
]
