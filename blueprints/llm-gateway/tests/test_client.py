"""Base client (Ch 11): retry/backoff, streaming assembly, usage parsing."""

import pytest

from llm_gateway.client import LLMClient, RetryPolicy
from llm_gateway.ports import ChatRequest, MockProvider, ProviderError


def _no_sleep(_seconds: float) -> None:
    return None


def test_complete_returns_typed_usage():
    client = LLMClient(provider=MockProvider(), sleep=_no_sleep)
    resp = client.complete(ChatRequest.of("claude-sonnet-4-6", "hello"))
    assert resp.provider == "mock"
    assert resp.text.startswith("[mock:mock]")
    # Usage is populated and totals add up.
    assert resp.usage.input_tokens > 0
    assert resp.usage.output_tokens > 0
    assert resp.usage.total_tokens == (
        resp.usage.input_tokens
        + resp.usage.output_tokens
        + resp.usage.cache_read_input_tokens
        + resp.usage.cache_creation_input_tokens
    )


def test_mock_is_deterministic():
    client = LLMClient(provider=MockProvider(), sleep=_no_sleep)
    a = client.ask("claude-sonnet-4-6", "same prompt")
    b = client.ask("claude-sonnet-4-6", "same prompt")
    assert a == b


def test_retry_recovers_from_transient_failures():
    # First two calls fail (retryable); third succeeds.
    provider = MockProvider(fail_times=2)
    client = LLMClient(
        provider=provider,
        retry=RetryPolicy(max_attempts=3),
        sleep=_no_sleep,
    )
    resp = client.complete(ChatRequest.of("claude-sonnet-4-6", "retry me"))
    assert resp.text  # eventually succeeded
    assert provider.calls == 3


def test_retry_exhausted_raises():
    provider = MockProvider(fail_times=5)
    client = LLMClient(
        provider=provider,
        retry=RetryPolicy(max_attempts=3),
        sleep=_no_sleep,
    )
    with pytest.raises(ProviderError):
        client.complete(ChatRequest.of("claude-sonnet-4-6", "always fails"))
    assert provider.calls == 3  # stopped at max_attempts


def test_non_retryable_error_fails_fast():
    class HardFail(MockProvider):
        def complete(self, request):
            self.calls += 1
            raise ProviderError("bad request", retryable=False)

    provider = HardFail()
    client = LLMClient(provider=provider, retry=RetryPolicy(max_attempts=3), sleep=_no_sleep)
    with pytest.raises(ProviderError):
        client.complete(ChatRequest.of("claude-sonnet-4-6", "x"))
    assert provider.calls == 1  # did not retry


def test_backoff_delay_is_monotone_without_jitter():
    policy = RetryPolicy(base_delay_s=1.0, max_delay_s=100.0, jitter=False)
    delays = [policy.delay_for(n) for n in (1, 2, 3, 4)]
    assert delays == [1.0, 2.0, 4.0, 8.0]
    # Cap applies.
    assert RetryPolicy(base_delay_s=1.0, max_delay_s=3.0, jitter=False).delay_for(5) == 3.0


def test_streaming_assembles_to_same_text_as_complete():
    client = LLMClient(provider=MockProvider(), sleep=_no_sleep)
    request = ChatRequest.of("claude-sonnet-4-6", "stream this please")
    streamed = "".join(client.stream_text(request))
    whole = client.complete(request).text
    assert streamed == whole


def test_stream_collect_returns_response_with_usage():
    client = LLMClient(provider=MockProvider(), sleep=_no_sleep)
    resp = client.stream_collect(ChatRequest.of("claude-sonnet-4-6", "collect"))
    assert resp.text
    assert resp.usage.output_tokens > 0
