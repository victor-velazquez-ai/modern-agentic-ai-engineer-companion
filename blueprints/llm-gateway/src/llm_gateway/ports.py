"""Provider-agnostic port + adapters (the portability seam).

The whole gateway speaks to one small interface — :class:`ChatProvider` — so the
base client, routing, cache, metering, and guards never import a vendor SDK
directly. Two adapters implement it:

* :class:`MockProvider` — deterministic, offline, zero-spend. The default, so the
  entire stack (and everything built on top of it) runs with no API key.
* :class:`AnthropicProvider` — the real Anthropic adapter. Imported lazily so the
  package installs and the mock path runs even when ``anthropic`` is absent.

A second provider (OpenAI, etc.) slots in by writing one more adapter that
satisfies the same Protocol — nothing above this file changes. This mirrors the
book's Ch 11 "single door" lesson: one typed request/response shape, one place
the SDK lives.
"""

from __future__ import annotations

import hashlib
import os
import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Iterable, Iterator, Mapping, Protocol, runtime_checkable

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

    ``cache_read_input_tokens`` is billed at ~0.1x and is surfaced separately so
    :mod:`llm_gateway.metering` can price it correctly.
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
    # Anthropic-first defaults: adaptive thinking, no temperature/budget_tokens
    # (those 400 on Opus 4.8). effort tunes depth: low | medium | high | xhigh | max.
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
# The port
# ---------------------------------------------------------------------------


@runtime_checkable
class ChatProvider(Protocol):
    """The single seam every layer of the gateway depends on."""

    name: str

    def complete(self, request: ChatRequest) -> ChatResponse:
        """Non-streaming completion."""
        ...

    def stream(self, request: ChatRequest) -> Iterator[StreamEvent]:
        """Token/chunk stream. Assemble with ``"".join(e.text for e in ...)``."""
        ...


# ---------------------------------------------------------------------------
# Mock adapter — the default, deterministic, no spend
# ---------------------------------------------------------------------------


def _estimate_tokens(text: str) -> int:
    """Cheap, deterministic token estimate (~4 chars/token). Offline-only.

    For real accounting use the provider's reported usage; this exists so the
    mock path produces realistic, stable numbers in CI.
    """

    if not text:
        return 0
    return max(1, len(text) // 4)


class MockProvider:
    """A canned, realistic provider. Same prompt → same answer, every time.

    Set ``COMPANION_MOCK=1`` (the repo default) to route the whole gateway here.
    ``fail_times`` makes the first N calls raise :class:`ProviderError`, which the
    routing layer's fallback ladder and the client's retry both exercise in tests.
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
        # Deterministic, prompt-derived stub so callers can assert on output.
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
        prompt_text = (request.system or "") + "".join(m.content for m in request.messages)
        usage = Usage(
            input_tokens=_estimate_tokens(prompt_text),
            output_tokens=_estimate_tokens(text),
        )
        return ChatResponse(
            text=text,
            model=request.model,
            usage=usage,
            provider=self.name,
        )

    def stream(self, request: ChatRequest) -> Iterator[StreamEvent]:
        # Reuse complete() so streamed and non-streamed text are identical, then
        # chunk on whitespace to mimic token-by-token delivery.
        response = self.complete(request)
        words = response.text.split(" ")
        for i, word in enumerate(words):
            yield StreamEvent(text=word if i == 0 else " " + word)


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class ProviderError(RuntimeError):
    """Raised by an adapter when a call fails.

    ``retryable`` lets the client decide whether backoff-retry makes sense
    (429/5xx/timeouts) versus failing fast (400/401/permission).
    """

    def __init__(self, message: str, *, retryable: bool = False) -> None:
        super().__init__(message)
        self.retryable = retryable


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
        else:
            try:
                import anthropic
            except ImportError as exc:  # pragma: no cover - depends on env
                raise ProviderError(
                    "anthropic SDK not installed; run `pip install anthropic` "
                    "or use MockProvider (COMPANION_MOCK=1)."
                ) from exc
            if not os.getenv("ANTHROPIC_API_KEY"):
                raise ProviderError(
                    "ANTHROPIC_API_KEY is not set. Put it in your environment "
                    "(.env), or stay in mock mode (COMPANION_MOCK=1)."
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
        # Map SDK exceptions to a provider-agnostic error with a retry hint.
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
            block.text for block in message.content if getattr(block, "type", None) == "text"
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
    """

    if os.getenv("COMPANION_MOCK", "1") == "1":
        return MockProvider()
    return AnthropicProvider()
