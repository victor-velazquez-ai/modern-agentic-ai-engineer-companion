"""Cost & token metering (Ch 40) — per-call attribution.

Turns a :class:`~llm_gateway.ports.Usage` into dollars and keeps a running ledger
so you can answer "what did this feature/tenant cost?" — the question Ch 40 says
every production system eventually has to answer.

Prices are per **million** tokens, matching Anthropic's published rates (current
as of this writing). Cache reads bill at ~0.1x input and cache writes at ~1.25x,
so they're priced from their own rates rather than lumped into input.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .ports import Usage


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


# Anthropic-first price book. Unknown models fall back to UNKNOWN_PRICE so a
# typo costs $0 rather than crashing the meter; metering should never be the
# thing that takes down a request.
PRICES: dict[str, ModelPrice] = {
    "claude-opus-4-8": ModelPrice(5.0, 25.0),
    "claude-opus-4-7": ModelPrice(5.0, 25.0),
    "claude-opus-4-6": ModelPrice(5.0, 25.0),
    "claude-sonnet-4-6": ModelPrice(3.0, 15.0),
    "claude-haiku-4-5": ModelPrice(1.0, 5.0),
    "claude-fable-5": ModelPrice(10.0, 50.0),
    # Mock models are free.
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


@dataclass
class Meter:
    """Running ledger of metered calls.

    ``label`` lets you attribute spend to a feature, tenant, or request id — call
    ``record(..., label="support-bot")`` and read it back via
    :meth:`cost_by_label`.
    """

    records: list[CallRecord] = field(default_factory=list)

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
            # A cache hit costs nothing downstream — it never reached the provider.
            cost_usd=0.0 if cached else cost_usd(model, usage),
            cached=cached,
            label=label,
        )
        self.records.append(rec)
        return rec

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


__all__ = [
    "ModelPrice",
    "PRICES",
    "price_for",
    "cost_usd",
    "CallRecord",
    "Meter",
]
