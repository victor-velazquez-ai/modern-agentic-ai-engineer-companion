"""Routing (Ch 39): tier selection + primary→fallback on error/timeout."""

import pytest

from llm_gateway.client import LLMClient, RetryPolicy
from llm_gateway.ports import ChatRequest, MockProvider, ProviderError
from llm_gateway.routing import (
    FallbackLadder,
    Rung,
    TierRouter,
    ladder_from_models,
)


def _client():
    return LLMClient(retry=RetryPolicy(max_attempts=1), sleep=lambda _: None)


# -- routing -----------------------------------------------------------------


def test_router_sends_classification_to_cheap_tier():
    router = TierRouter()
    decision = router.decide(ChatRequest.of("balanced", "spam?"), task="classification")
    assert decision.tier == "cheap"
    assert decision.model == "claude-haiku-4-5"


def test_router_sends_reasoning_to_smart_tier():
    router = TierRouter()
    decision = router.decide(ChatRequest.of("balanced", "prove it"), task="reasoning")
    assert decision.tier == "smart"
    assert decision.model == "claude-opus-4-8"


def test_router_uses_smart_tier_for_long_prompts():
    router = TierRouter(long_prompt_chars=100)
    long_prompt = "x" * 200
    decision = router.decide(ChatRequest.of("balanced", long_prompt), task="general")
    assert decision.tier == "smart"


def test_router_respects_explicit_model():
    router = TierRouter()
    decision = router.decide(ChatRequest.of("claude-opus-4-6", "hi"), task="classification")
    assert decision.tier == "explicit"
    assert decision.model == "claude-opus-4-6"


def test_router_default_is_balanced():
    router = TierRouter()
    decision = router.decide(ChatRequest.of("balanced", "short"), task="general")
    assert decision.tier == "balanced"


# -- fallback ladder ---------------------------------------------------------


def test_fallback_climbs_to_healthy_rung():
    failing = MockProvider("primary", fail_times=99)
    healthy = MockProvider("secondary")
    ladder = FallbackLadder(
        [Rung(failing, "claude-opus-4-8"), Rung(healthy, "claude-sonnet-4-6")],
        client=_client(),
    )
    result = ladder.complete(ChatRequest.of("claude-opus-4-8", "ping"))
    assert result.rung_index == 1
    assert result.response.provider == "secondary"
    assert result.attempts == ["primary:claude-opus-4-8", "secondary:claude-sonnet-4-6"]


def test_fallback_overrides_model_per_rung():
    healthy = MockProvider("secondary")
    ladder = FallbackLadder(
        [Rung(MockProvider("primary", fail_times=99), "claude-opus-4-8"),
         Rung(healthy, "claude-haiku-4-5")],
        client=_client(),
    )
    result = ladder.complete(ChatRequest.of("claude-opus-4-8", "ping"))
    # The served response carries the second rung's model, not the requested one.
    assert result.response.model == "claude-haiku-4-5"


def test_fallback_first_rung_wins_when_healthy():
    ladder = ladder_from_models(
        MockProvider("p"),
        ["claude-opus-4-8", "claude-sonnet-4-6"],
        client=_client(),
    )
    result = ladder.complete(ChatRequest.of("claude-opus-4-8", "ping"))
    assert result.rung_index == 0


def test_fallback_non_retryable_does_not_climb():
    class HardFail(MockProvider):
        def complete(self, request):
            raise ProviderError("400", retryable=False)

    ladder = FallbackLadder(
        [Rung(HardFail("primary"), "claude-opus-4-8"),
         Rung(MockProvider("secondary"), "claude-sonnet-4-6")],
        client=_client(),
    )
    with pytest.raises(ProviderError):
        ladder.complete(ChatRequest.of("claude-opus-4-8", "ping"))


def test_fallback_all_rungs_fail_raises_last_error():
    ladder = FallbackLadder(
        [Rung(MockProvider("a", fail_times=99), "claude-opus-4-8"),
         Rung(MockProvider("b", fail_times=99), "claude-sonnet-4-6")],
        client=_client(),
    )
    with pytest.raises(ProviderError):
        ladder.complete(ChatRequest.of("claude-opus-4-8", "ping"))


def test_empty_ladder_rejected():
    with pytest.raises(ValueError):
        FallbackLadder([])
