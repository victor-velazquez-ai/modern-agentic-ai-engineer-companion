"""The model gateway — routing, fallbacks, cache, cost, guards (Ch 39–41).

Everything that wraps the base :class:`~llm.client.LLMClient` for production model
access, composed into one :class:`Gateway` — the platform's single door for
*application* model calls (the client is the door to the *provider*; the gateway
is the door for *callers*). The request path:

    guard(input) → route → cache → [fallback ladder over the client]
        → meter → cost-cap → guard(output)

The pieces (mirroring the ``llm-gateway`` blueprint's ``routing.py`` / ``cache.py``
/ ``metering.py`` / ``guards.py``, folded into this one file to match Appendix C's
``llm/gateway.py``):

* **Routing (Ch 39)** — :class:`TierRouter` picks a model by a coarse ``task`` hint
  and prompt length; :class:`FallbackLadder` retries down a typed ladder of
  ``(provider, model)`` rungs on *retryable* failure only.
* **Cache (Ch 40)** — :class:`ResponseCache`: exact-hash cache + optional semantic
  near-hit cache, with a pluggable embedder.
* **Metering (Ch 40)** — :class:`Meter`: per-call cost attribution by model and by
  label, plus a daily cost cap that fails closed.
* **Guards (Ch 41)** — :class:`Guard`: PII redaction + injection/unsafe blocking at
  the input and output edges. Shared with the ``security/`` module (Ch 41).

Secrets are never handled here — the provider is constructed in
:mod:`llm.client`, which reads keys from the environment only.
"""

from __future__ import annotations

import hashlib
import math
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Callable, Pattern, Sequence

from core.errors import GuardrailError
from core.logging import get_logger

from .client import (
    ChatProvider,
    ChatRequest,
    ChatResponse,
    LLMClient,
    RetryPolicy,
    Usage,
    default_provider,
)

log = get_logger(__name__)


# ===========================================================================
# Routing (Ch 39)
# ===========================================================================

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
        self, tiers: dict[str, str] | None = None, *, long_prompt_chars: int = 6000
    ) -> None:
        self.tiers = dict(tiers or TIER_MODELS)
        self.long_prompt_chars = long_prompt_chars

    def decide(self, request: ChatRequest, *, task: str = "general") -> RouteDecision:
        if request.model and request.model not in self.tiers:
            return RouteDecision(request.model, "explicit", "caller specified model")

        prompt_chars = sum(len(m.content) for m in request.messages) + len(
            request.system or ""
        )

        if task in ("classification", "extraction", "routing"):
            tier, reason = "cheap", f"task={task} -> cheap tier"
        elif (
            task in ("reasoning", "analysis", "code")
            or prompt_chars >= self.long_prompt_chars
        ):
            tier = "smart"
            reason = f"task={task} / long prompt ({prompt_chars} chars) -> smart tier"
        else:
            tier, reason = "balanced", "default -> balanced tier"

        return RouteDecision(self.tiers[tier], tier, reason)


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


def _with_model(request: ChatRequest, model: str) -> ChatRequest:
    return ChatRequest(
        model=model,
        messages=request.messages,
        system=request.system,
        max_tokens=request.max_tokens,
        effort=request.effort,
        metadata=request.metadata,
    )


class FallbackLadder:
    """Try each rung in order; advance only on *retryable* failure.

    A non-retryable error (bad request, auth) raises immediately — climbing
    wouldn't help and would waste spend. If every rung fails, the last error is
    re-raised so the caller sees a real exception, not a silent ``None``.
    """

    def __init__(self, rungs: list[Rung], *, client: LLMClient | None = None) -> None:
        if not rungs:
            raise ValueError("FallbackLadder needs at least one rung")
        self.rungs = rungs
        self._client = client or LLMClient(provider=rungs[0].provider)

    def complete(self, request: ChatRequest) -> FallbackResult:
        from core.errors import ProviderError

        attempts: list[str] = []
        last_exc: ProviderError | None = None
        for index, rung in enumerate(self.rungs):
            attempts.append(f"{rung.provider.name}:{rung.model}")
            self._client.provider = rung.provider
            try:
                response = self._client.complete(_with_model(request, rung.model))
                return FallbackResult(response, index, attempts)
            except ProviderError as exc:
                last_exc = exc
                if not exc.retryable:
                    raise
        assert last_exc is not None  # at least one rung ran
        raise last_exc


def ladder_from_models(
    provider: ChatProvider, models: list[str], *, client: LLMClient | None = None
) -> FallbackLadder:
    """Build a same-provider ladder (Opus → Sonnet → Haiku, say)."""

    return FallbackLadder([Rung(provider, m) for m in models], client=client)


# ===========================================================================
# Cache (Ch 40)
# ===========================================================================

Embedder = Callable[[str], Sequence[float]]
_WORD_RE = re.compile(r"[a-z0-9']+")


def cache_key(request: ChatRequest) -> str:
    """Stable hash over the fields that change the answer.

    ``metadata`` is intentionally excluded — two requests that differ only in a
    tracing tag should share a cache entry (the "cost-aware key").
    """

    parts = [
        request.model,
        request.system or "",
        str(request.max_tokens),
        request.effort or "",
    ]
    parts.extend(f"{m.role}:{m.content}" for m in request.messages)
    return hashlib.sha256("\x1f".join(parts).encode("utf-8")).hexdigest()


def prompt_text(request: ChatRequest) -> str:
    """The text the semantic layer embeds (system + all turns)."""

    head = (request.system or "").strip()
    body = " ".join(m.content for m in request.messages)
    return f"{head} {body}".strip()


def hashing_embedder(text: str, dim: int = 256) -> list[float]:
    """Deterministic bag-of-words hashing embedding (L2-normalized).

    No model, no network, no extra dependency. Good enough to *demonstrate*
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


@dataclass
class _SemanticEntry:
    embedding: Sequence[float]
    response: ChatResponse


@dataclass
class ResponseCache:
    """Exact + semantic response cache.

    Set ``semantic=False`` for an exact-only cache (no false positives, lower
    recall). ``threshold`` is the cosine-similarity bar for a semantic hit; higher
    is safer (fewer wrong answers), lower is cheaper (more hits).
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
        self._exact[cache_key(request)] = response
        if self.semantic:
            self._semantic.append(
                _SemanticEntry(self.embedder(prompt_text(request)), response)
            )

    @staticmethod
    def _mark(response: ChatResponse) -> ChatResponse:
        if response.cached:
            return response
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
        return (self.exact_hits + self.semantic_hits) / total if total else 0.0

    def stats(self) -> dict[str, float | int]:
        return {
            "exact_hits": self.exact_hits,
            "semantic_hits": self.semantic_hits,
            "misses": self.misses,
            "hit_rate": round(self.hit_rate, 4),
            "size": len(self._exact),
        }


# ===========================================================================
# Metering (Ch 40)
# ===========================================================================


@dataclass(frozen=True)
class ModelPrice:
    """Per-million-token prices for one model."""

    input_per_mtok: float
    output_per_mtok: float

    @property
    def cache_read_per_mtok(self) -> float:
        return self.input_per_mtok * 0.1

    @property
    def cache_write_per_mtok(self) -> float:
        return self.input_per_mtok * 1.25


# Anthropic-first price book. Unknown models fall back to UNKNOWN_PRICE so a typo
# costs $0 rather than crashing the meter — metering should never take down a call.
PRICES: dict[str, ModelPrice] = {
    "claude-opus-4-8": ModelPrice(5.0, 25.0),
    "claude-opus-4-7": ModelPrice(5.0, 25.0),
    "claude-sonnet-4-6": ModelPrice(3.0, 15.0),
    "claude-haiku-4-5": ModelPrice(1.0, 5.0),
    "claude-fable-5": ModelPrice(10.0, 50.0),
    "mock": ModelPrice(0.0, 0.0),
}

UNKNOWN_PRICE = ModelPrice(0.0, 0.0)


def price_for(model: str) -> ModelPrice:
    return PRICES.get(model, UNKNOWN_PRICE)


def cost_usd(model: str, usage: Usage) -> float:
    """Dollar cost of one call, cache-aware."""

    price = price_for(model)
    return (
        usage.input_tokens * price.input_per_mtok
        + usage.output_tokens * price.output_per_mtok
        + usage.cache_read_input_tokens * price.cache_read_per_mtok
        + usage.cache_creation_input_tokens * price.cache_write_per_mtok
    ) / 1_000_000


@dataclass
class CallRecord:
    """One metered call — the unit of attribution."""

    model: str
    provider: str
    usage: Usage
    cost_usd: float
    cached: bool
    label: str = ""


class CostCapExceeded(GuardrailError):
    """Raised when a call would push spend past the configured daily cap."""

    code = "cost_cap_exceeded"


@dataclass
class Meter:
    """Running ledger of metered calls, with an optional daily cost cap.

    ``label`` attributes spend to a feature/tenant/request id. ``daily_cap_usd``
    (0 = off) fails *closed*: :meth:`check_cap` raises :class:`CostCapExceeded`
    before a call that would breach the cap, so a runaway loop can't drain spend.
    """

    records: list[CallRecord] = field(default_factory=list)
    daily_cap_usd: float = 0.0

    def record(
        self,
        model: str,
        provider: str,
        usage: Usage,
        *,
        cached: bool = False,
        label: str = "",
    ) -> CallRecord:
        rec = CallRecord(
            model=model,
            provider=provider,
            usage=usage,
            cost_usd=0.0 if cached else cost_usd(model, usage),
            cached=cached,
            label=label,
        )
        self.records.append(rec)
        return rec

    def check_cap(self) -> None:
        """Fail closed if we've already hit the daily cap (call before spending)."""

        if self.daily_cap_usd > 0 and self.total_cost_usd >= self.daily_cap_usd:
            raise CostCapExceeded(
                f"daily cost cap reached: ${self.total_cost_usd:.4f} "
                f">= ${self.daily_cap_usd:.4f}",
                details={
                    "spent_usd": round(self.total_cost_usd, 6),
                    "cap_usd": self.daily_cap_usd,
                },
            )

    @property
    def total_cost_usd(self) -> float:
        return sum(r.cost_usd for r in self.records)

    @property
    def total_tokens(self) -> int:
        return sum(r.usage.total_tokens for r in self.records)

    @property
    def call_count(self) -> int:
        return len(self.records)

    @property
    def cache_hits(self) -> int:
        return sum(1 for r in self.records if r.cached)

    def cost_by_label(self) -> dict[str, float]:
        out: dict[str, float] = {}
        for rec in self.records:
            out[rec.label] = out.get(rec.label, 0.0) + rec.cost_usd
        return out

    def cost_by_model(self) -> dict[str, float]:
        out: dict[str, float] = {}
        for rec in self.records:
            out[rec.model] = out.get(rec.model, 0.0) + rec.cost_usd
        return out

    def summary(self) -> dict[str, object]:
        return {
            "calls": self.call_count,
            "cache_hits": self.cache_hits,
            "total_tokens": self.total_tokens,
            "total_cost_usd": round(self.total_cost_usd, 6),
            "by_model": {k: round(v, 6) for k, v in self.cost_by_model().items()},
            "by_label": {k: round(v, 6) for k, v in self.cost_by_label().items()},
        }


# ===========================================================================
# Guards (Ch 41)
# ===========================================================================


class GuardAction(str, Enum):
    ALLOW = "allow"
    REDACT = "redact"
    BLOCK = "block"


@dataclass(frozen=True)
class GuardFinding:
    category: str
    action: GuardAction
    detail: str = ""


@dataclass
class GuardResult:
    text: str
    findings: list[GuardFinding] = field(default_factory=list)

    @property
    def blocked(self) -> bool:
        return any(f.action is GuardAction.BLOCK for f in self.findings)

    @property
    def redacted(self) -> bool:
        return any(f.action is GuardAction.REDACT for f in self.findings)


# PII patterns → replacement token. Order matters (email before generic digits).
_PII_PATTERNS: list[tuple[str, Pattern[str], str]] = [
    ("email", re.compile(r"\b[\w.%+-]+@[\w.-]+\.[A-Za-z]{2,}\b"), "[REDACTED_EMAIL]"),
    ("credit_card", re.compile(r"\b(?:\d[ -]?){13,16}\b"), "[REDACTED_CC]"),
    ("ssn", re.compile(r"\b\d{3}-\d{2}-\d{4}\b"), "[REDACTED_SSN]"),
    (
        "phone",
        re.compile(r"\b(?:\+?1[ .-]?)?\(?\d{3}\)?[ .-]?\d{3}[ .-]?\d{4}\b"),
        "[REDACTED_PHONE]",
    ),
    (
        "api_key",
        re.compile(r"\b(?:sk|pk|ghp|xoxb)[-_](?:[A-Za-z0-9]+[-_])?[A-Za-z0-9]{16,}\b"),
        "[REDACTED_KEY]",
    ),
]

_INJECTION_PATTERNS: list[tuple[str, Pattern[str]]] = [
    ("injection", re.compile(r"ignore (?:all |the )?(?:previous|prior|above) instructions", re.I)),
    ("injection", re.compile(r"disregard (?:all |the )?(?:previous|prior|above)", re.I)),
    ("injection", re.compile(r"you are now (?:in )?(?:dan|developer|jailbreak) mode", re.I)),
    ("injection", re.compile(r"reveal (?:your )?(?:system prompt|instructions)", re.I)),
    ("injection", re.compile(r"\bprint (?:your )?(?:system prompt|secret)", re.I)),
]

_UNSAFE_PATTERNS: list[tuple[str, Pattern[str]]] = [
    ("self_harm", re.compile(r"\bhow to (?:kill|harm) (?:myself|yourself)\b", re.I)),
    ("weapons", re.compile(r"\b(?:build|make) a (?:bomb|bioweapon)\b", re.I)),
]


def redact_pii(text: str) -> tuple[str, list[GuardFinding]]:
    """Replace recognised PII with redaction tokens. Fails safe (leaves unknown)."""

    findings: list[GuardFinding] = []
    out = text
    for category, pattern, token in _PII_PATTERNS:
        new, n = pattern.subn(token, out)
        if n:
            findings.append(GuardFinding(category, GuardAction.REDACT, f"{n} match(es)"))
            out = new
    return out, findings


def detect_injection(text: str) -> list[GuardFinding]:
    return [
        GuardFinding(cat, GuardAction.BLOCK, pat.pattern)
        for cat, pat in _INJECTION_PATTERNS
        if pat.search(text)
    ]


def detect_unsafe(text: str) -> list[GuardFinding]:
    return [
        GuardFinding(cat, GuardAction.BLOCK, pat.pattern)
        for cat, pat in _UNSAFE_PATTERNS
        if pat.search(text)
    ]


@dataclass
class GuardConfig:
    block_injection: bool = True
    block_unsafe: bool = True
    redact_pii_input: bool = True
    redact_pii_output: bool = True


class Guard:
    """Runs the configured detectors over input and output text.

    Blocks fail *closed* (raise via the gateway); redaction fails *safe* (unknown
    → leave alone). Shared with the ``security/`` module, which configures the
    same detectors as a reviewable policy in one place.
    """

    def __init__(self, config: GuardConfig | None = None) -> None:
        self.config = config or GuardConfig()

    def check_input(self, text: str) -> GuardResult:
        findings: list[GuardFinding] = []
        out = text
        if self.config.block_injection:
            findings.extend(detect_injection(text))
        if self.config.block_unsafe:
            findings.extend(detect_unsafe(text))
        if self.config.redact_pii_input:
            out, pii = redact_pii(out)
            findings.extend(pii)
        return GuardResult(text=out, findings=findings)

    def check_output(self, text: str) -> GuardResult:
        findings: list[GuardFinding] = []
        out = text
        if self.config.redact_pii_output:
            out, pii = redact_pii(out)
            findings.extend(pii)
        if self.config.block_unsafe:
            findings.extend(detect_unsafe(text))
        return GuardResult(text=out, findings=findings)

    def enforce_input(self, text: str) -> str:
        result = self.check_input(text)
        if result.blocked:
            raise GuardrailError(
                "input blocked by guardrail",
                details={
                    "categories": [
                        f.category for f in result.findings if f.action is GuardAction.BLOCK
                    ]
                },
            )
        return result.text


# ===========================================================================
# The composed gateway
# ===========================================================================


@dataclass
class GatewayResult:
    """Everything the gateway did for one request — the observable trace.

    ``response`` is what you return to the user; the rest is for logging, evals,
    and tracing: which model was routed to, whether the cache served it, the PII
    findings on the way in/out, the per-call cost record, and the fallback path.
    """

    response: ChatResponse
    route: RouteDecision
    cached: bool
    record: CallRecord
    input_guard: GuardResult
    output_guard: GuardResult
    fallback_attempts: list[str] = field(default_factory=list)


class Gateway:
    """Compose the Ch 39–41 layers around the Ch 11 base client.

    Request path: **guard(input) → route → cache → [fallback ladder over the
    client] → meter → cost-cap → guard(output)**. Each layer is injectable, so you
    can disable the cache, swap the router, set a cost cap, or hand in a real
    provider without touching callers.

    Construct from settings with :meth:`from_settings` so the mock switch, default
    model, cache threshold, and daily cost cap all come from one config object.
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
        self.fallback_models = fallback_models or [
            "claude-opus-4-8",
            "claude-sonnet-4-6",
            "claude-haiku-4-5",
        ]
        self.default_model = default_model

    @classmethod
    def from_settings(cls, settings: object | None = None) -> "Gateway":
        """Build a gateway from :class:`core.config.Settings`.

        Reads the mock switch (via the provider), default model, cache settings,
        retry budget, and the daily cost cap from one config object. Pass an
        explicit ``settings`` in tests; otherwise the process-wide one is used.
        """

        from core.config import get_settings

        cfg = settings or get_settings()
        cache = ResponseCache(
            threshold=getattr(cfg, "cache_threshold", 0.95),
            semantic=getattr(cfg, "cache_semantic", True),
        )
        meter = Meter(daily_cap_usd=getattr(cfg, "daily_cost_cap_usd", 0.0))
        retry = RetryPolicy(max_attempts=getattr(cfg, "llm_max_retries", 3))
        return cls(
            cache=cache,
            meter=meter,
            retry=retry,
            default_model=getattr(cfg, "default_model", "claude-sonnet-4-6"),
        )

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
            raise GuardrailError(
                "input blocked by guardrail",
                details={
                    "categories": [
                        f.category
                        for f in in_guard.findings
                        if f.action is GuardAction.BLOCK
                    ]
                },
            )
        safe_prompt = in_guard.text

        # 2. Route — hand the router a tier alias when the caller didn't force a
        #    model, so the task hint governs instead of being an explicit override.
        route_seed = model if model is not None else "balanced"
        route_request = ChatRequest.of(
            route_seed, safe_prompt, system=system, max_tokens=max_tokens, effort=effort
        )
        route = self.router.decide(route_request, task=task)
        request = ChatRequest.of(
            route.model, safe_prompt, system=system, max_tokens=max_tokens, effort=effort
        )

        # 3. Cache — exact then semantic.
        cached = self.cache.get(request)
        fallback_attempts: list[str] = []
        if cached is not None:
            response = cached
            is_cached = True
        else:
            # 3a. Cost cap (fail closed) — only gates fresh spend, never cache hits.
            self.meter.check_cap()
            # 4. Call through the fallback ladder (per-rung retry from the client).
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

        log.debug(
            "gateway.complete",
            extra={
                "model": route.model,
                "tier": route.tier,
                "cached": is_cached,
                "cost_usd": record.cost_usd,
                "label": label,
            },
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
        models = [primary_model] + [
            m for m in self.fallback_models if m != primary_model
        ]
        return ladder_from_models(self.provider, models, client=self.client)


__all__ = [
    # routing
    "TierRouter",
    "RouteDecision",
    "TIER_MODELS",
    "FallbackLadder",
    "FallbackResult",
    "Rung",
    "ladder_from_models",
    # cache
    "ResponseCache",
    "Embedder",
    "hashing_embedder",
    "cosine_similarity",
    "cache_key",
    "prompt_text",
    # metering
    "ModelPrice",
    "PRICES",
    "price_for",
    "cost_usd",
    "CallRecord",
    "Meter",
    "CostCapExceeded",
    # guards
    "Guard",
    "GuardConfig",
    "GuardResult",
    "GuardFinding",
    "GuardAction",
    "redact_pii",
    "detect_injection",
    "detect_unsafe",
    # gateway
    "Gateway",
    "GatewayResult",
]
