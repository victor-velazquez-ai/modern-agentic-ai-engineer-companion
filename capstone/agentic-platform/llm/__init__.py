"""The model layer — the platform's only door to model APIs.

Three pieces, per Appendix C (and the ``llm-gateway`` blueprint):

* :mod:`llm.client` — the base SDK client (Ch 11): a provider port + mock/Anthropic
  adapters, retries with backoff, streaming assembly, typed usage. The "single
  door" to the *provider*.
* :mod:`llm.structured` — :func:`complete_structured` (Ch 15): the model choke
  point for *typed data* — ask for JSON, parse, validate, repair-and-retry.
* :mod:`llm.gateway` — the production :class:`Gateway` (Ch 39–41): routing by
  difficulty + a fallback ladder, an exact + semantic cache, cost metering with a
  daily cap, and input/output guards. The "single door" for *callers*.

Everything runs **offline with zero API spend** by default: with
``COMPANION_MOCK=1`` (the repo convention) the provider is ``MockProvider``. Point
it at Anthropic by setting ``COMPANION_MOCK=0`` and ``ANTHROPIC_API_KEY`` — keys
are read from the environment only, never passed to a constructor.

    >>> from llm import Gateway
    >>> gw = Gateway()                      # mock provider, all layers on
    >>> result = gw.complete("Summarize the CAP theorem.", label="docs")
    >>> result.response.text                # doctest: +ELLIPSIS
    '[mock:...] response to ...'
"""

from __future__ import annotations

from .client import (
    AnthropicProvider,
    ChatProvider,
    ChatRequest,
    ChatResponse,
    LLMClient,
    Message,
    MockProvider,
    RetryPolicy,
    Usage,
    default_provider,
    estimate_tokens,
)
from .gateway import (
    CallRecord,
    CostCapExceeded,
    FallbackLadder,
    Gateway,
    GatewayResult,
    Guard,
    GuardAction,
    GuardConfig,
    GuardResult,
    Meter,
    ModelPrice,
    ResponseCache,
    RouteDecision,
    Rung,
    TierRouter,
    cost_usd,
    hashing_embedder,
    ladder_from_models,
    price_for,
)
from .structured import StructuredResult, complete_structured

__all__ = [
    # client (Ch 11)
    "LLMClient",
    "RetryPolicy",
    "ChatProvider",
    "ChatRequest",
    "ChatResponse",
    "Message",
    "Usage",
    "MockProvider",
    "AnthropicProvider",
    "default_provider",
    "estimate_tokens",
    # structured (Ch 15)
    "complete_structured",
    "StructuredResult",
    # gateway (Ch 39-41)
    "Gateway",
    "GatewayResult",
    "TierRouter",
    "RouteDecision",
    "Rung",
    "FallbackLadder",
    "ladder_from_models",
    "ResponseCache",
    "hashing_embedder",
    "Meter",
    "CallRecord",
    "ModelPrice",
    "cost_usd",
    "price_for",
    "CostCapExceeded",
    "Guard",
    "GuardConfig",
    "GuardResult",
    "GuardAction",
]

__version__ = "0.1.0"
