"""Base model client — the single door over a provider (Ch 11).

This is the platform's **only** place a model SDK is touched. Everything above it
(structured output, the gateway, agents, RAG, evals) calls models *through* this
client, so retries, streaming, and usage accounting are uniform and no raw
``client.messages.create(...)`` is scattered through the codebase.

Three concerns live here, and nothing else:

* a provider **port** (:class:`ChatProvider`) + two adapters — :class:`MockProvider`
  (the default, offline, zero-spend) and :class:`AnthropicProvider` (the real one,
  with the SDK imported *lazily*),
* **retries with backoff** for retryable failures (429/5xx/timeout),
* **streaming assembly** and **typed usage** on every response.

Routing, caching, metering, and guards are *not* here — they compose around this
client in :mod:`llm.gateway`. Keeping the base layer small is the point of the
"single door." (Mirrors the ``llm-gateway`` blueprint's ``ports.py`` + ``client.py``,
folded into one file to match Appendix C's ``llm/client.py``.)
"""

from __future__ import annotations

import hashlib
import os
import random
import time
from dataclasses import dataclass, field
from typing import (
    TYPE_CHECKING,
    Callable,
    Iterable,
    Iterator,
    Mapping,
    Protocol,
    runtime_checkable,
)

from core.errors import ProviderError

if TYPE_CHECKING:  # pragma: no cover - typing only
    from anthropic import Anthropic


# ---------------------------------------------------------------------------
# Typed request / response shapes
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Message:
    """One chat turn. ``content`` is plain text (the 80% case)."""

    role: str
    content: str

    def as_dict(self) -> dict[str, str]:
        return {"role": self.role, "content": self.content}


@dataclass(frozen=True)
class Usage:
    """Token accounting for a single call.

    ``cache_read_input_tokens`` is billed at ~0.1x and surfaced separately so the
    metering layer can price it correctly.
    """

    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_input_tokens: int = 0
    cache_creation_input_tokens: int = 0

    @property
    def total_tokens(self) -> int:
        return (
            self.input_tokens
            + self.output_tokens
            + self.cache_read_input_tokens
            + self.cache_creation_input_tokens
        )


@dataclass(frozen=True)
class ChatRequest:
    """A provider-agnostic request. ``model`` is the only required field."""

    model: str
    messages: tuple[Message, ...]
    system: str | None = None
    max_tokens: int = 1024
    # Anthropic-first defaults: adaptive thinking, no temperature/top_p/budget
    # (those 400 on Opus 4.8). `effort` tunes depth: low | medium | high | xhigh | max.
    effort: str | None = None
    metadata: Mapping[str, str] = field(default_factory=dict)

    @staticmethod
    def of(
        model: str,
        prompt: str | None = None,
        *,
        messages: Iterable[Message] | None = None,
        system: str | None = None,
        max_tokens: int = 1024,
        effort: str | None = None,
    ) -> "ChatRequest":
        """Convenience builder: a single ``prompt`` *or* an explicit ``messages`` list."""

        if messages is None:
            if prompt is None:
                raise ValueError("provide either `prompt` or `messages`")
            messages = (Message("user", prompt),)
        return ChatRequest(
            model=model,
            messages=tuple(messages),
            system=system,
            max_tokens=max_tokens,
            effort=effort,
        )


@dataclass(frozen=True)
class ChatResponse:
    """What every provider returns. ``provider`` records who actually served it."""

    text: str
    model: str
    usage: Usage
    provider: str
    stop_reason: str = "end_turn"
    cached: bool = False


@dataclass(frozen=True)
class StreamEvent:
    """One streamed chunk. ``text`` is the incremental delta."""

    text: str


# ---------------------------------------------------------------------------
# The provider port (the portability seam)
# ---------------------------------------------------------------------------


@runtime_checkable
class ChatProvider(Protocol):
    """The single seam every layer of the model stack depends on.

    A second provider (OpenAI for the eval-judge, say) slots in by writing one
    more adapter that satisfies this Protocol — nothing above this file changes.
    """

    name: str

    def complete(self, request: ChatRequest) -> ChatResponse:
        """Non-streaming completion."""
        ...

    def stream(self, request: ChatRequest) -> Iterator[StreamEvent]:
        """Token/chunk stream. Assemble with ``"".join(e.text for e in ...)``."""
        ...


# ---------------------------------------------------------------------------
# Token estimate (offline-only helper)
# ---------------------------------------------------------------------------


def estimate_tokens(text: str) -> int:
    """Cheap, deterministic token estimate (~4 chars/token). Offline-only.

    For real accounting use the provider's reported usage; this exists so the
    mock path produces realistic, stable numbers in CI and so streamed responses
    (which often omit a usage block until the terminal event) carry a floor.
    """

    if not text:
        return 0
    return max(1, len(text) // 4)


# ---------------------------------------------------------------------------
# Mock adapter — the default, deterministic, no spend
# ---------------------------------------------------------------------------


class MockProvider:
    """A canned, realistic provider. Same prompt → same answer, every time.

    Set ``COMPANION_MOCK=1`` (the repo default) to route the whole stack here.
    ``fail_times`` makes the first N calls raise a retryable
    :class:`~core.errors.ProviderError`, which exercises the client's retry and
    the gateway's fallback ladder in tests.
    """

    def __init__(
        self,
        name: str = "mock",
        *,
        canned: Mapping[str, str] | None = None,
        fail_times: int = 0,
        latency_s: float = 0.0,
    ) -> None:
        self.name = name
        self._canned = dict(canned or {})
        self._fail_times = fail_times
        self._latency_s = latency_s
        self.calls = 0

    def _answer(self, request: ChatRequest) -> str:
        last_user = next(
            (m.content for m in reversed(request.messages) if m.role == "user"),
            "",
        )
        if last_user in self._canned:
            return self._canned[last_user]
        digest = hashlib.sha256(last_user.encode("utf-8")).hexdigest()[:8]
        return f"[mock:{self.name}] response to {last_user!r} ({digest})"

    def _maybe_fail(self) -> None:
        if self.calls <= self._fail_times:
            raise ProviderError(
                f"{self.name}: simulated transient failure #{self.calls}",
                retryable=True,
            )

    def complete(self, request: ChatRequest) -> ChatResponse:
        self.calls += 1
        if self._latency_s:
            time.sleep(self._latency_s)
        self._maybe_fail()
        text = self._answer(request)
        prompt_text = (request.system or "") + "".join(
            m.content for m in request.messages
        )
        usage = Usage(
            input_tokens=estimate_tokens(prompt_text),
            output_tokens=estimate_tokens(text),
        )
        return ChatResponse(
            text=text, model=request.model, usage=usage, provider=self.name
        )

    def stream(self, request: ChatRequest) -> Iterator[StreamEvent]:
        # Reuse complete() so streamed and non-streamed text are identical, then
        # chunk on whitespace to mimic token-by-token delivery.
        response = self.complete(request)
        words = response.text.split(" ")
        for i, word in enumerate(words):
            yield StreamEvent(text=word if i == 0 else " " + word)


# ---------------------------------------------------------------------------
# Anthropic adapter — the real one (lazy import, Anthropic-first)
# ---------------------------------------------------------------------------


class AnthropicProvider:
    """Adapter over the official ``anthropic`` SDK.

    The SDK is imported lazily in ``__init__`` so importing this module never
    requires the dependency and the mock path always works. The key comes from
    the environment (``ANTHROPIC_API_KEY``) — never a constructor argument that
    might get logged or committed.
    """

    def __init__(
        self,
        name: str = "anthropic",
        *,
        client: "Anthropic | None" = None,
        max_retries: int = 2,
    ) -> None:
        self.name = name
        if client is not None:
            self._client = client
            return
        try:
            import anthropic
        except ImportError as exc:  # pragma: no cover - depends on env
            raise ProviderError(
                "anthropic SDK not installed; run `pip install anthropic` "
                "or use MockProvider (COMPANION_MOCK=1).",
                retryable=False,
            ) from exc
        if not os.getenv("ANTHROPIC_API_KEY"):
            raise ProviderError(
                "ANTHROPIC_API_KEY is not set. Put it in your environment (.env), "
                "or stay in mock mode (COMPANION_MOCK=1).",
                retryable=False,
            )
        # SDK auto-retries 429/5xx with backoff; let it own that.
        self._client = anthropic.Anthropic(max_retries=max_retries)

    def _build_kwargs(self, request: ChatRequest) -> dict[str, object]:
        kwargs: dict[str, object] = {
            "model": request.model,
            "max_tokens": request.max_tokens,
            "messages": [m.as_dict() for m in request.messages],
            # Adaptive thinking is the only on-mode for Opus 4.8 / Sonnet 4.6.
            "thinking": {"type": "adaptive"},
        }
        if request.system is not None:
            kwargs["system"] = request.system
        if request.effort is not None:
            kwargs["output_config"] = {"effort": request.effort}
        return kwargs

    def _translate_error(self, exc: Exception) -> ProviderError:
        try:
            import anthropic
        except ImportError:  # pragma: no cover
            return ProviderError(str(exc), retryable=False)
        retryable = isinstance(
            exc,
            (
                anthropic.RateLimitError,
                anthropic.APITimeoutError,
                anthropic.APIConnectionError,
                anthropic.InternalServerError,
            ),
        )
        if isinstance(exc, anthropic.APIStatusError):
            retryable = retryable or exc.status_code >= 500
        return ProviderError(f"{self.name}: {exc}", retryable=retryable)

    @staticmethod
    def _usage_from_sdk(raw_usage: object) -> Usage:
        def g(attr: str) -> int:
            value = getattr(raw_usage, attr, 0)
            return int(value) if value else 0

        return Usage(
            input_tokens=g("input_tokens"),
            output_tokens=g("output_tokens"),
            cache_read_input_tokens=g("cache_read_input_tokens"),
            cache_creation_input_tokens=g("cache_creation_input_tokens"),
        )

    def complete(self, request: ChatRequest) -> ChatResponse:
        try:
            message = self._client.messages.create(**self._build_kwargs(request))
        except ProviderError:
            raise
        except Exception as exc:  # SDK exception → portable error
            raise self._translate_error(exc) from exc
        text = "".join(
            block.text
            for block in message.content
            if getattr(block, "type", None) == "text"
        )
        return ChatResponse(
            text=text,
            model=getattr(message, "model", request.model),
            usage=self._usage_from_sdk(getattr(message, "usage", None)),
            provider=self.name,
            stop_reason=getattr(message, "stop_reason", "end_turn") or "end_turn",
        )

    def stream(self, request: ChatRequest) -> Iterator[StreamEvent]:
        try:
            with self._client.messages.stream(**self._build_kwargs(request)) as stream:
                for text in stream.text_stream:
                    yield StreamEvent(text=text)
        except ProviderError:
            raise
        except Exception as exc:  # pragma: no cover - needs live SDK
            raise self._translate_error(exc) from exc


def default_provider() -> ChatProvider:
    """Return the provider implied by the environment.

    ``COMPANION_MOCK`` defaults to ``"1"`` (the repo convention), so with no
    configuration at all you get the offline, zero-spend :class:`MockProvider`.
    Reads the env directly (not :class:`core.config.Settings`) so the model layer
    stays importable with no settings object constructed yet.
    """

    if os.getenv("COMPANION_MOCK", "1") == "1":
        return MockProvider()
    return AnthropicProvider()


# ---------------------------------------------------------------------------
# Retry policy + the client
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class RetryPolicy:
    """Exponential backoff with full jitter.

    ``sleep`` is injectable on the client so tests run instantly.
    """

    max_attempts: int = 3
    base_delay_s: float = 0.5
    max_delay_s: float = 8.0
    jitter: bool = True

    def delay_for(self, attempt: int) -> float:
        # attempt is 1-based; first retry waits ~base_delay_s.
        raw = self.base_delay_s * (2 ** (attempt - 1))
        capped = min(raw, self.max_delay_s)
        if self.jitter:
            return random.uniform(0, capped)
        return capped


class LLMClient:
    """The single door. Construct once, share everywhere a model is called."""

    def __init__(
        self,
        provider: ChatProvider | None = None,
        *,
        retry: RetryPolicy | None = None,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self.provider = provider or default_provider()
        self.retry = retry or RetryPolicy()
        self._sleep = sleep

    # -- non-streaming -----------------------------------------------------

    def complete(self, request: ChatRequest) -> ChatResponse:
        """Run one completion, retrying retryable failures with backoff."""

        last_exc: ProviderError | None = None
        for attempt in range(1, self.retry.max_attempts + 1):
            try:
                return self.provider.complete(request)
            except ProviderError as exc:
                last_exc = exc
                if not exc.retryable or attempt == self.retry.max_attempts:
                    raise
                self._sleep(self.retry.delay_for(attempt))
        assert last_exc is not None  # invariant: loop returns or raises
        raise last_exc

    def ask(
        self,
        model: str,
        prompt: str,
        *,
        system: str | None = None,
        max_tokens: int = 1024,
        effort: str | None = None,
    ) -> str:
        """Ergonomic helper: prompt in, text out."""

        request = ChatRequest.of(
            model, prompt, system=system, max_tokens=max_tokens, effort=effort
        )
        return self.complete(request).text

    # -- streaming ---------------------------------------------------------

    def stream_text(self, request: ChatRequest) -> Iterator[str]:
        """Yield text deltas as they arrive.

        Retries apply only *before* the first chunk — once bytes are flowing a
        provider error mid-stream is surfaced to the caller (partial output can't
        be silently retried without duplicating tokens).
        """

        for attempt in range(1, self.retry.max_attempts + 1):
            stream = self.provider.stream(request)
            try:
                first = next(stream)
            except StopIteration:
                return
            except ProviderError as exc:
                if not exc.retryable or attempt == self.retry.max_attempts:
                    raise
                self._sleep(self.retry.delay_for(attempt))
                continue
            yield first.text
            for event in stream:
                yield event.text
            return

    def stream_collect(self, request: ChatRequest) -> ChatResponse:
        """Stream, then return the assembled response.

        Usage is re-estimated from the streamed text because most streaming APIs
        deliver token counts only in the terminal event; for the mock this is
        exact, for a real provider it's a floor the metering layer can refine.
        """

        chunks: list[str] = list(self.stream_text(request))
        text = "".join(chunks)
        prompt_text = (request.system or "") + "".join(
            m.content for m in request.messages
        )
        usage = Usage(
            input_tokens=estimate_tokens(prompt_text),
            output_tokens=estimate_tokens(text),
        )
        return ChatResponse(
            text=text,
            model=request.model,
            usage=usage,
            provider=getattr(self.provider, "name", "unknown"),
        )


__all__ = [
    "Message",
    "Usage",
    "ChatRequest",
    "ChatResponse",
    "StreamEvent",
    "ChatProvider",
    "MockProvider",
    "AnthropicProvider",
    "default_provider",
    "estimate_tokens",
    "RetryPolicy",
    "LLMClient",
]
