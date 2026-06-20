"""Base client (Ch 11) — the thin, single door over a provider.

This is the ``LLMClient`` the book's Ch 11 §"single-door" Build points at. It
wraps one :class:`~llm_gateway.ports.ChatProvider` with the cross-cutting
concerns every call needs:

* **Retries with backoff** for *retryable* failures (429/5xx/timeouts). Real SDKs
  retry internally too; this layer also covers the mock and any provider that
  doesn't, and gives one consistent policy.
* **Streaming assembly** — ``stream_text`` yields deltas; ``complete`` from a
  stream is assembled here so callers never reassemble chunks by hand.
* **Typed usage** — every response carries a :class:`~llm_gateway.ports.Usage`.

It deliberately does *not* know about routing, caching, metering, or guards —
those compose *around* it in :mod:`llm_gateway.routing` and the gateway. Keeping
the base layer small is the whole point of the "single door."
"""

from __future__ import annotations

import random
import time
from dataclasses import dataclass
from typing import Callable, Iterator

from .ports import (
    ChatProvider,
    ChatRequest,
    ChatResponse,
    Message,
    ProviderError,
    StreamEvent,
    default_provider,
)


@dataclass(frozen=True)
class RetryPolicy:
    """Exponential backoff with full jitter.

    ``sleep`` is injectable so tests run instantly (pass ``lambda _: None``).
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
        # Unreachable: the loop either returns or raises. Guard for type-checkers.
        assert last_exc is not None  # noqa: S101 - invariant
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
            model,
            prompt,
            system=system,
            max_tokens=max_tokens,
            effort=effort,
        )
        return self.complete(request).text

    # -- streaming ---------------------------------------------------------

    def stream_text(self, request: ChatRequest) -> Iterator[str]:
        """Yield text deltas as they arrive.

        Retries only apply *before* the first chunk — once bytes are flowing a
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

        from .ports import Usage, _estimate_tokens

        chunks: list[str] = list(self.stream_text(request))
        text = "".join(chunks)
        prompt_text = (request.system or "") + "".join(m.content for m in request.messages)
        usage = Usage(
            input_tokens=_estimate_tokens(prompt_text),
            output_tokens=_estimate_tokens(text),
        )
        return ChatResponse(
            text=text,
            model=request.model,
            usage=usage,
            provider=getattr(self.provider, "name", "unknown"),
        )


__all__ = [
    "LLMClient",
    "RetryPolicy",
    "ChatRequest",
    "ChatResponse",
    "Message",
]
