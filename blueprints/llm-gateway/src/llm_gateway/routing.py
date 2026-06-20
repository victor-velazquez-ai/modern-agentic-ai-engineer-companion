"""Model routing + fallback ladder (Ch 39).

Production model access is rarely "call model X." It's:

* **Routing** — pick the right model for *this* request. A cheap classification
  can go to Haiku; a hard reasoning task to Opus. The default
  :class:`TierRouter` chooses by a coarse ``task`` hint and prompt length, with a
  hard override when the caller already named a model.
* **Fallback** — if the chosen provider/model fails (overloaded, rate-limited,
  timeout), try the next rung of a ladder rather than failing the user. The ladder
  is *typed*: each rung is a (provider, model) pair, tried in order, and only
  *retryable* errors advance it — a 400 fails fast.

Routing decides *what to call*; the base :class:`~llm_gateway.client.LLMClient`
decides *how to call it* (retries within a single rung). The two compose: per-rung
backoff handles a blip, the ladder handles a rung that's down.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .client import LLMClient
from .ports import ChatProvider, ChatRequest, ChatResponse, ProviderError


# ---------------------------------------------------------------------------
# Routing policy
# ---------------------------------------------------------------------------

# Anthropic-first tier map: capability ↑ as you go down, cost ↑ too.
TIER_MODELS: dict[str, str] = {
    "cheap": "claude-haiku-4-5",
    "balanced": "claude-sonnet-4-6",
    "smart": "claude-opus-4-8",
}


@dataclass(frozen=True)
class RouteDecision:
    model: str
    tier: str
    reason: str


class TierRouter:
    """Choose a model from a coarse task hint and prompt size.

    If the request already names a model that isn't a tier alias, that's an
    explicit caller choice and wins — the router never second-guesses it.
    """

    def __init__(
        self,
        tiers: dict[str, str] | None = None,
        *,
        long_prompt_chars: int = 6000,
    ) -> None:
        self.tiers = dict(tiers or TIER_MODELS)
        self.long_prompt_chars = long_prompt_chars

    def decide(self, request: ChatRequest, *, task: str = "general") -> RouteDecision:
        # Explicit model wins (unless it's a tier alias the caller used as shorthand).
        if request.model and request.model not in self.tiers:
            return RouteDecision(request.model, "explicit", "caller specified model")

        prompt_chars = sum(len(m.content) for m in request.messages) + len(request.system or "")

        if task in ("classification", "extraction", "routing"):
            tier = "cheap"
            reason = f"task={task} -> cheap tier"
        elif task in ("reasoning", "analysis", "code") or prompt_chars >= self.long_prompt_chars:
            tier = "smart"
            reason = (
                f"task={task} / long prompt ({prompt_chars} chars) -> smart tier"
            )
        else:
            tier = "balanced"
            reason = "default -> balanced tier"

        return RouteDecision(self.tiers[tier], tier, reason)


# ---------------------------------------------------------------------------
# Fallback ladder
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Rung:
    """One step of the fallback ladder: a provider and the model to ask it for."""

    provider: ChatProvider
    model: str


@dataclass
class FallbackResult:
    response: ChatResponse
    rung_index: int
    attempts: list[str] = field(default_factory=list)


class FallbackLadder:
    """Try each rung in order; advance only on *retryable* failure.

    A non-retryable error (bad request, auth) raises immediately — climbing the
    ladder wouldn't help and would waste spend. If every rung fails, the last
    error is re-raised so the caller sees a real exception, not a silent ``None``.
    """

    def __init__(self, rungs: list[Rung], *, client: LLMClient | None = None) -> None:
        if not rungs:
            raise ValueError("FallbackLadder needs at least one rung")
        self.rungs = rungs
        # One client wraps each per-rung call so retry/backoff still applies.
        self._client = client or LLMClient(provider=rungs[0].provider)

    def complete(self, request: ChatRequest) -> FallbackResult:
        attempts: list[str] = []
        last_exc: ProviderError | None = None

        for index, rung in enumerate(self.rungs):
            attempts.append(f"{rung.provider.name}:{rung.model}")
            # Re-point the shared client at this rung's provider, override the model.
            self._client.provider = rung.provider
            rung_request = _with_model(request, rung.model)
            try:
                response = self._client.complete(rung_request)
                return FallbackResult(response=response, rung_index=index, attempts=attempts)
            except ProviderError as exc:
                last_exc = exc
                if not exc.retryable:
                    raise
                # else: climb to the next rung
        assert last_exc is not None  # at least one rung ran
        raise last_exc


def _with_model(request: ChatRequest, model: str) -> ChatRequest:
    return ChatRequest(
        model=model,
        messages=request.messages,
        system=request.system,
        max_tokens=request.max_tokens,
        effort=request.effort,
        metadata=request.metadata,
    )


def ladder_from_models(
    provider: ChatProvider,
    models: list[str],
    *,
    client: LLMClient | None = None,
) -> FallbackLadder:
    """Build a same-provider ladder (Opus → Sonnet → Haiku, say)."""

    return FallbackLadder([Rung(provider, m) for m in models], client=client)


__all__ = [
    "TierRouter",
    "RouteDecision",
    "TIER_MODELS",
    "FallbackLadder",
    "FallbackResult",
    "Rung",
    "ladder_from_models",
]
