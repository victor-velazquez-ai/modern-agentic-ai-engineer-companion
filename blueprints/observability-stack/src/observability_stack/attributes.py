"""Span attribute conventions for agent-run traces.

One agent run becomes a tree of spans; the *value* of that tree is only as good as the
attributes we hang on each span. Conventions matter more than cleverness here: if every
blueprint that this stack instruments (`agent-loop`, `rag-pipeline`,
`multi-agent-supervisor`, `llm-gateway`) names the run id, model, token counts, and cost
the *same* way, then a dashboard, a cost roll-up, or a CI assertion can read any trace
without special-casing the producer.

We borrow the shape of OpenTelemetry's semantic conventions (dotted, namespaced keys) but
keep the keys defined here as plain constants so the package has **zero import-time
dependency on OTel** — the console exporter and the cost roll-up work on stdlib alone, and
the OTel-backed exporters (see ``exporters.py``) translate these same keys when present.

Keep keys stable: chapter 23, the capstone ``observability/``, and downstream tests all
read them by name.
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Mapping

# --- Span kinds -----------------------------------------------------------------
# The four span kinds a senior actually wants to see in an agent trace. The root of a
# run is a RUN span; everything else nests under it.


class SpanKind(str, Enum):
    """The role a span plays in an agent run.

    Subclasses ``str`` so a kind serializes to a plain string in attributes and JSON.
    """

    RUN = "run"  # the whole agent run (the trace root)
    LLM = "llm"  # a single model call
    TOOL = "tool"  # a single tool / function call
    RETRIEVAL = "retrieval"  # a retrieval / vector-search step
    CHAIN = "chain"  # a grouping step (a sub-plan, a reasoning phase)

    def __str__(self) -> str:  # so f-strings render "tool", not "SpanKind.TOOL"
        return self.value


# --- Attribute keys -------------------------------------------------------------
# Namespaced like OTel semantic conventions so a real OTLP backend groups them sensibly.

# Identity / structure
RUN_ID = "agent.run.id"
SPAN_KIND = "agent.span.kind"
SESSION_ID = "agent.session.id"
USER_ID = "agent.user.id"

# Model-call attributes (set on LLM spans; produced by the llm-gateway metering layer)
MODEL = "gen_ai.request.model"
PROVIDER = "gen_ai.system"
INPUT_TOKENS = "gen_ai.usage.input_tokens"
OUTPUT_TOKENS = "gen_ai.usage.output_tokens"
TOTAL_TOKENS = "gen_ai.usage.total_tokens"

# Cost (USD). COST is what a single span spent; COST_ROLLUP is the subtree total that
# cost.py computes by summing descendant model-call costs into ancestor spans.
COST = "agent.cost.usd"
COST_ROLLUP = "agent.cost.rollup_usd"

# Tool attributes (set on TOOL spans)
TOOL_NAME = "agent.tool.name"
TOOL_ERROR = "agent.tool.error"

# Retrieval attributes (set on RETRIEVAL spans)
RETRIEVAL_QUERY = "agent.retrieval.query"
RETRIEVAL_K = "agent.retrieval.k"
RETRIEVAL_HITS = "agent.retrieval.hits"

# Error / status (any span)
ERROR = "error"
ERROR_TYPE = "error.type"
ERROR_MESSAGE = "error.message"


def usage_attributes(
    *,
    model: str,
    input_tokens: int,
    output_tokens: int,
    provider: str | None = None,
) -> dict[str, Any]:
    """Build the canonical attribute dict for a model call.

    This is the one place that knows how to name token usage, so every instrumented
    model call (the gateway, a raw SDK call in a notebook, a test) agrees. ``cost.py``
    reads exactly these keys to price the call.
    """
    attrs: dict[str, Any] = {
        SPAN_KIND: str(SpanKind.LLM),
        MODEL: model,
        INPUT_TOKENS: int(input_tokens),
        OUTPUT_TOKENS: int(output_tokens),
        TOTAL_TOKENS: int(input_tokens) + int(output_tokens),
    }
    if provider:
        attrs[PROVIDER] = provider
    return attrs


def has_usage(attrs: Mapping[str, Any]) -> bool:
    """True if a span carries model-usage attributes (i.e., it is a priceable LLM call)."""
    return MODEL in attrs and INPUT_TOKENS in attrs and OUTPUT_TOKENS in attrs


def error_attributes(exc: BaseException) -> dict[str, Any]:
    """Standard attributes for a span that ended in an exception."""
    return {
        ERROR: True,
        ERROR_TYPE: type(exc).__name__,
        ERROR_MESSAGE: str(exc),
    }
