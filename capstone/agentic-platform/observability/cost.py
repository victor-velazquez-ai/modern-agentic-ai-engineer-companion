"""Token → cost accounting, and the per-run cost roll-up (Ch 23).

Two jobs, both small but worth testing:

1. **Price one model call.** Given a model id and its input/output token counts, return the
   USD cost. Prices live in a table you can swap; the table is the *policy*, the math is the
   *mechanism*. In production the ``llm/`` gateway metering layer is the source of truth for
   *usage*; this module is the source of truth for turning that usage into *money* and
   attributing it to spans and tenants.

2. **Roll the cost up the tree.** A run's total cost is the sum of its model-call costs, but
   you also want each intermediate span to carry the cost of *its* subtree — so a dashboard can
   answer "what did the retrieval phase cost?" not just "what did the run cost?".
   :func:`roll_up_cost` walks the span tree and writes both the per-span cost (``agent.cost.usd``
   on LLM spans) and the subtree roll-up (``agent.cost.rollup_usd`` on every span), returning
   the run total.

Prices are USD per **million** tokens. The table mirrors the ``llm/`` gateway price book so the
two subsystems agree on what a model costs; update both from the provider's pricing page before
trusting a real bill. The point of the module is the *shape* of the calculation, not a frozen
price sheet — unknown models price at zero and are surfaced via :func:`unknown_models` so a new
model never silently costs $0.
"""

from __future__ import annotations

from dataclasses import dataclass

from . import attributes as attrs
from .tracing import Span, Trace


@dataclass(frozen=True)
class ModelPrice:
    """Price of a model in USD per **million** tokens, split by direction."""

    input_per_mtok: float
    output_per_mtok: float


# Anthropic-first price book, aligned with llm/ gateway metering. USD / 1M tokens.
# NOT a live price feed — see the module docstring.
PRICES: dict[str, ModelPrice] = {
    "claude-opus-4-8": ModelPrice(5.0, 25.0),
    "claude-opus-4-7": ModelPrice(5.0, 25.0),
    "claude-opus-4-6": ModelPrice(5.0, 25.0),
    "claude-sonnet-4-6": ModelPrice(3.0, 15.0),
    "claude-haiku-4-5": ModelPrice(1.0, 5.0),
    "claude-fable-5": ModelPrice(10.0, 50.0),
    # OpenAI (secondary — routing / judge chapters)
    "gpt-4o": ModelPrice(2.50, 10.0),
    "gpt-4o-mini": ModelPrice(0.15, 0.60),
    # Free local/mock model so MOCK demos price to exactly $0.
    "mock": ModelPrice(0.0, 0.0),
    "mock-model": ModelPrice(0.0, 0.0),
}

# Used when a model id is not in the table, so cost is never silently wrong-but-plausible:
# unknown models price at zero and are reported via `unknown_models()`.
UNKNOWN_PRICE = ModelPrice(0.0, 0.0)

_MTOK = 1_000_000


def price_for(model: str) -> ModelPrice:
    """Look up a model's price, tolerant of provider-prefixed or dated ids.

    Tries the exact id, then a few normalizations (strip a ``provider/`` prefix, strip a
    trailing ``-YYYYMMDD`` date, match a known prefix). Falls back to :data:`UNKNOWN_PRICE`.
    """

    if model in PRICES:
        return PRICES[model]
    # strip a "provider/" or "provider:" prefix
    base = model.split("/")[-1].split(":")[-1]
    if base in PRICES:
        return PRICES[base]
    # strip a trailing -YYYYMMDD snapshot date, e.g. claude-sonnet-4-6-20250514
    trimmed = base
    parts = base.rsplit("-", 1)
    if len(parts) == 2 and parts[1].isdigit() and len(parts[1]) >= 6:
        trimmed = parts[0]
    if trimmed in PRICES:
        return PRICES[trimmed]
    # longest known prefix wins (handles versioned aliases)
    candidates = [k for k in PRICES if trimmed.startswith(k) or base.startswith(k)]
    if candidates:
        return PRICES[max(candidates, key=len)]
    return UNKNOWN_PRICE


def is_known(model: str) -> bool:
    """True if ``model`` resolves to a real entry in the price table."""

    return price_for(model) is not UNKNOWN_PRICE


def token_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    """USD cost of a single model call. Returns 0.0 for unknown/free models."""

    price = price_for(model)
    return (
        input_tokens * price.input_per_mtok + output_tokens * price.output_per_mtok
    ) / _MTOK


def span_cost(span: Span) -> float:
    """Direct cost of one span (0.0 unless it carries model usage attributes)."""

    a = span.attributes
    if not attrs.has_usage(a):
        return 0.0
    return token_cost(
        str(a[attrs.MODEL]),
        int(a[attrs.INPUT_TOKENS]),
        int(a[attrs.OUTPUT_TOKENS]),
    )


def roll_up_cost(trace_or_span: Trace | Span) -> float:
    """Compute and attach costs across a span tree; return the run total (USD).

    Side effects (idempotent — safe to call again):

    - every **LLM** span gets ``agent.cost.usd`` = its own model-call cost;
    - **every** span gets ``agent.cost.rollup_usd`` = the summed cost of its whole subtree.

    The root span's roll-up therefore equals the run total, which is also the return value.
    """

    root = trace_or_span.root if isinstance(trace_or_span, Trace) else trace_or_span

    def visit(span: Span) -> float:
        subtotal = span_cost(span)
        if attrs.has_usage(span.attributes):
            span.set_attribute(attrs.COST, round(subtotal, 10))
        for child in span.children:
            subtotal += visit(child)
        span.set_attribute(attrs.COST_ROLLUP, round(subtotal, 10))
        return subtotal

    return round(visit(root), 10)


def unknown_models(trace_or_span: Trace | Span) -> set[str]:
    """Model ids in the tree that priced at the unknown fallback (likely a missing price).

    Surfacing these prevents the quiet failure mode where a new model silently costs $0.
    """

    root = trace_or_span.root if isinstance(trace_or_span, Trace) else trace_or_span
    found: set[str] = set()
    for span in root.iter_tree():
        a = span.attributes
        if attrs.has_usage(a):
            model = str(a[attrs.MODEL])
            if not is_known(model):
                found.add(model)
    return found


@dataclass
class CostSummary:
    """A small report: total cost, total tokens, and per-model breakdown."""

    total_usd: float
    input_tokens: int
    output_tokens: int
    per_model_usd: dict[str, float]
    llm_call_count: int

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens


def summarize(trace_or_span: Trace | Span) -> CostSummary:
    """Aggregate the tree into a :class:`CostSummary` (also runs the roll-up)."""

    root = trace_or_span.root if isinstance(trace_or_span, Trace) else trace_or_span
    roll_up_cost(root)
    per_model: dict[str, float] = {}
    in_tok = out_tok = calls = 0
    for span in root.iter_tree():
        a = span.attributes
        if not attrs.has_usage(a):
            continue
        calls += 1
        model = str(a[attrs.MODEL])
        in_tok += int(a[attrs.INPUT_TOKENS])
        out_tok += int(a[attrs.OUTPUT_TOKENS])
        per_model[model] = round(per_model.get(model, 0.0) + span_cost(span), 10)
    total = round(sum(per_model.values()), 10)
    return CostSummary(
        total_usd=total,
        input_tokens=in_tok,
        output_tokens=out_tok,
        per_model_usd=per_model,
        llm_call_count=calls,
    )
