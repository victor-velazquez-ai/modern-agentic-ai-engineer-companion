"""agents.tools — the typed ledger, tool schemas + risk tiers, safe executors, and model port.

This is the shared foundation the three agent variants (``raw/``, ``graph/``, ``pydantic_ai/``)
and the ``supervisor`` all build on. It owns four concerns:

* **the ledger** (:mod:`messages`) — provider-neutral, immutable, append-only turns;
* **tools** (:mod:`schemas`, :mod:`executors`) — the model-facing schema, the declared
  :class:`RiskTier`, the safe executor, and the dispatch registry;
* **the model seam** (:mod:`model`) — one :class:`ModelPort` everything calls, mock by default;
* **failure handling** (:mod:`errors`) — malformed-call repair and the retry policy.

It mirrors the ``agent-loop`` blueprint's package surface, extended with the platform-specific
:class:`RiskTier` (Ch 20) and the concrete safe executors (Ch 12/19) that the blueprint leaves to
the caller.
"""

from __future__ import annotations

from .errors import (
    MalformedToolCall,
    RetryPolicy,
    repair_arguments,
    repair_tool_call,
)
from .executors import (
    Retriever,
    calculate,
    callable_toolset,
    create_ticket,
    default_toolset,
    make_search_docs,
    now,
    send_email,
)
from .messages import (
    Message,
    Role,
    ToolCall,
    ToolResult,
    Transcript,
    assistant,
    system,
    tool as tool_message,
    user,
)
from .model import (
    DEFAULT_LIVE_MODEL,
    MockModel,
    ModelPort,
    ModelResponse,
    ScriptStep,
    default_model,
    keyword_tool_picker,
    mock_enabled,
)
from .schemas import (
    RiskTier,
    Tool,
    ToolError,
    ToolFn,
    ToolRegistry,
    ToolSpec,
    tool,
)

__all__ = [
    # ledger
    "Transcript",
    "Message",
    "Role",
    "ToolCall",
    "ToolResult",
    "system",
    "user",
    "assistant",
    "tool_message",
    # tools / schemas / risk
    "Tool",
    "ToolSpec",
    "ToolRegistry",
    "ToolError",
    "ToolFn",
    "RiskTier",
    "tool",
    # executors
    "default_toolset",
    "callable_toolset",
    "make_search_docs",
    "Retriever",
    "calculate",
    "now",
    "create_ticket",
    "send_email",
    # model port
    "ModelPort",
    "ModelResponse",
    "MockModel",
    "ScriptStep",
    "default_model",
    "keyword_tool_picker",
    "mock_enabled",
    "DEFAULT_LIVE_MODEL",
    # errors / recovery
    "RetryPolicy",
    "MalformedToolCall",
    "repair_arguments",
    "repair_tool_call",
]
