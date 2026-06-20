"""Cache (Ch 40): exact hit; semantic near-hit threshold; cost-aware keys."""

from llm_gateway.cache import (
    ResponseCache,
    cache_key,
    cosine_similarity,
    hashing_embedder,
)
from llm_gateway.ports import ChatRequest, ChatResponse, Usage


def _response(text: str = "answer") -> ChatResponse:
    return ChatResponse(text=text, model="claude-sonnet-4-6", usage=Usage(10, 5), provider="mock")


# -- keying ------------------------------------------------------------------


def test_identical_requests_share_a_key():
    a = ChatRequest.of("claude-sonnet-4-6", "hello", system="be terse")
    b = ChatRequest.of("claude-sonnet-4-6", "hello", system="be terse")
    assert cache_key(a) == cache_key(b)


def test_metadata_does_not_affect_key():
    # Two requests differing only in a tracing tag must hit the same entry.
    a = ChatRequest("claude-sonnet-4-6", (), max_tokens=100, metadata={"trace": "1"})
    b = ChatRequest("claude-sonnet-4-6", (), max_tokens=100, metadata={"trace": "2"})
    assert cache_key(a) == cache_key(b)


def test_model_change_changes_key():
    a = ChatRequest.of("claude-sonnet-4-6", "hello")
    b = ChatRequest.of("claude-opus-4-8", "hello")
    assert cache_key(a) != cache_key(b)


# -- exact cache -------------------------------------------------------------


def test_exact_hit():
    cache = ResponseCache(semantic=False)
    req = ChatRequest.of("claude-sonnet-4-6", "what is RAG?")
    assert cache.get(req) is None  # miss
    cache.put(req, _response("RAG = retrieval augmented generation"))
    hit = cache.get(req)
    assert hit is not None
    assert hit.cached is True
    assert hit.text == "RAG = retrieval augmented generation"
    assert cache.exact_hits == 1
    assert cache.misses == 1


def test_exact_only_cache_misses_paraphrase():
    cache = ResponseCache(semantic=False)
    cache.put(ChatRequest.of("claude-sonnet-4-6", "reset my password"), _response())
    assert cache.get(ChatRequest.of("claude-sonnet-4-6", "how to reset my password")) is None


# -- semantic cache ----------------------------------------------------------


def test_semantic_near_hit_within_threshold():
    cache = ResponseCache(threshold=0.6)
    stored = ChatRequest.of("claude-sonnet-4-6", "how do I reset my password")
    cache.put(stored, _response("Click 'forgot password'."))
    near = ChatRequest.of("claude-sonnet-4-6", "how can I reset my password")
    hit = cache.get(near)
    assert hit is not None
    assert hit.cached is True
    assert cache.semantic_hits == 1


def test_semantic_miss_above_threshold():
    # A very high threshold means only near-identical prompts hit.
    cache = ResponseCache(threshold=0.999)
    cache.put(ChatRequest.of("claude-sonnet-4-6", "tell me about cats"), _response())
    miss = cache.get(ChatRequest.of("claude-sonnet-4-6", "explain quantum chromodynamics"))
    assert miss is None
    assert cache.misses == 1


def test_unrelated_prompts_do_not_collide():
    cache = ResponseCache(threshold=0.8)
    cache.put(ChatRequest.of("claude-sonnet-4-6", "weather in Paris"), _response("rainy"))
    other = cache.get(ChatRequest.of("claude-sonnet-4-6", "how to bake sourdough bread"))
    assert other is None


def test_hit_rate_and_stats():
    cache = ResponseCache(semantic=False)
    req = ChatRequest.of("claude-sonnet-4-6", "x")
    cache.get(req)          # miss
    cache.put(req, _response())
    cache.get(req)          # hit
    stats = cache.stats()
    assert stats["misses"] == 1
    assert stats["exact_hits"] == 1
    assert 0.0 < stats["hit_rate"] <= 1.0


# -- embedder ----------------------------------------------------------------


def test_embedder_is_deterministic_and_normalized():
    v1 = hashing_embedder("reset my password")
    v2 = hashing_embedder("reset my password")
    assert v1 == v2
    # Self-similarity is 1.0 for non-empty text.
    assert abs(cosine_similarity(v1, v2) - 1.0) < 1e-9


def test_overlapping_vocab_is_more_similar_than_disjoint():
    base = hashing_embedder("the quick brown fox")
    near = hashing_embedder("the quick brown dog")
    far = hashing_embedder("entirely different sentence here")
    assert cosine_similarity(base, near) > cosine_similarity(base, far)
