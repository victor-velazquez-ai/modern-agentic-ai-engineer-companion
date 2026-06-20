"""LLM Gateway — the single door to every model call.

Two layers, per the book:

* **Base client (Ch 11)** — :class:`LLMClient` over a provider port: typed
  request/response, retries, streaming, usage.
* **Gateway (Ch 39–41)** — :class:`Gateway` wraps the client with routing +
  fallbacks (Ch 39), an exact + semantic cache (Ch 40), cost/token metering
  (Ch 40), and input/output guards (Ch 41).

Everything runs **offline with zero API spend** by default: with
``COMPANION_MOCK=1`` (the repo default) the provider is :class:`MockProvider`.
Point it at Anthropic by setting ``COMPANION_MOCK=0`` and ``ANTHROPIC_API_KEY``.

    >>> from llm_gateway import Gateway
    >>> gw = Gateway()                      # mock provider, all layers on
    >>> result = gw.complete("Summarize the CAP theorem in one line.")
    >>> result.response.text                # doctest: +ELLIPSIS
    '[mock:...] response to ...'
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .cache import ResponseCache
from .client import LLMClient, RetryPolicy
from .guards import Guard, GuardConfig, GuardResult, GuardrailError
from .metering import CallRecord, Meter, cost_usd
from .ports import (
    AnthropicProvider,
    ChatProvider,
    ChatRequest,
    ChatResponse,
    Message,
    MockProvider,
    ProviderError,
    Usage,
    default_provider,
)
from .routing import (
    FallbackLadder,
    FallbackResult,
    RouteDecision,
    Rung,
    TierRouter,
    ladder_from_models,
)

__all__ = [
    "Gateway",
    "GatewayResult",
    "LLMClient",
    "RetryPolicy",
    "ResponseCache",
    "Guard",
    "GuardConfig",
    "GuardResult",
    "GuardrailError",
    "Meter",
    "CallRecord",
    "cost_usd",
    "TierRouter",
    "RouteDecision",
    "FallbackLadder",
    "FallbackResult",
    "Rung",
    "ladder_from_models",
    "ChatProvider",
    "ChatRequest",
    "ChatResponse",
    "Message",
    "Usage",
    "MockProvider",
    "AnthropicProvider",
    "ProviderError",
    "default_provider",
]

__version__ = "0.1.0"


@dataclass
class GatewayResult:
    """Everything the gateway did for one request — the observable trace.

    ``response`` is what you return to the user; the rest is for logging, evals,
    and the demo: which model was routed to, whether the cache served it, the PII
    findings on the way in/out, and the per-call cost record.
    """

    response: ChatResponse
    route: RouteDecision
    cached: bool
    record: CallRecord
    input_guard: GuardResult
    output_guard: GuardResult
    fallback_attempts: list[str] = field(default_factory=list)


class Gateway:
    """Compose the four Ch 39–41 layers around the Ch 11 base client.

    Request path: **guard(input) → route → cache → [fallback ladder over the
    client] → meter → guard(output)**. Each layer is optional and injectable, so
    you can disable the cache, swap the router, or hand in a real provider without
    touching callers — the portability seam from :mod:`llm_gateway.ports`.
    """

    def __init__(
        self,
        provider: ChatProvider | None = None,
        *,
        router: TierRouter | None = None,
        cache: ResponseCache | None = None,
        guard: Guard | None = None,
        meter: Meter | None = None,
        fallback_models: list[str] | None = None,
        retry: RetryPolicy | None = None,
        default_model: str = "claude-sonnet-4-6",
    ) -> None:
        self.provider = provider or default_provider()
        self.router = router if router is not None else TierRouter()
        self.cache = cache if cache is not None else ResponseCache()
        self.guard = guard if guard is not None else Guard()
        self.meter = meter if meter is not None else Meter()
        self.client = LLMClient(provider=self.provider, retry=retry)
        # Same-provider fallback ladder: smart → balanced → cheap by default.
        self.fallback_models = fallback_models or [
            "claude-opus-4-8",
            "claude-sonnet-4-6",
            "claude-haiku-4-5",
        ]
        self.default_model = default_model

    def complete(
        self,
        prompt: str,
        *,
        task: str = "general",
        system: str | None = None,
        model: str | None = None,
        max_tokens: int = 1024,
        effort: str | None = None,
        label: str = "",
    ) -> GatewayResult:
        # 1. Input guard — redact PII, block injection/unsafe (fail-closed).
        in_guard = self.guard.check_input(prompt)
        if in_guard.blocked:
            raise GuardrailError(in_guard)
        safe_prompt = in_guard.text

        # 2. Route — pick a model unless the caller forced one. When the caller
        #    didn't name a model we hand the router a tier *alias* ("balanced")
        #    rather than a concrete model, so the task hint governs the choice
        #    instead of being treated as an explicit override.
        route_seed = model if model is not None else "balanced"
        route_request = ChatRequest.of(
            route_seed,
            safe_prompt,
            system=system,
            max_tokens=max_tokens,
            effort=effort,
        )
        route = self.router.decide(route_request, task=task)
        request = ChatRequest.of(
            route.model,
            safe_prompt,
            system=system,
            max_tokens=max_tokens,
            effort=effort,
        )

        # 3. Cache — exact then semantic.
        cached = self.cache.get(request)
        fallback_attempts: list[str] = []
        if cached is not None:
            response = cached
            is_cached = True
        else:
            # 4. Call through the fallback ladder (which uses the base client's
            #    retry/backoff per rung). The ladder starts at the routed model.
            ladder = self._build_ladder(route.model)
            result = ladder.complete(request)
            response = result.response
            fallback_attempts = result.attempts
            is_cached = False
            self.cache.put(request, response)

        # 5. Meter — attribute cost (a cache hit costs $0).
        record = self.meter.record(
            response.model,
            response.provider,
            response.usage,
            cached=is_cached,
            label=label,
        )

        # 6. Output guard — redact any PII the model echoed.
        out_guard = self.guard.check_output(response.text)
        guarded = ChatResponse(
            text=out_guard.text,
            model=response.model,
            usage=response.usage,
            provider=response.provider,
            stop_reason=response.stop_reason,
            cached=is_cached,
        )

        return GatewayResult(
            response=guarded,
            route=route,
            cached=is_cached,
            record=record,
            input_guard=in_guard,
            output_guard=out_guard,
            fallback_attempts=fallback_attempts,
        )

    def _build_ladder(self, primary_model: str) -> FallbackLadder:
        # Primary first, then the remaining tiers (deduped, order preserved).
        models = [primary_model] + [m for m in self.fallback_models if m != primary_model]
        return ladder_from_models(self.provider, models, client=self.client)
