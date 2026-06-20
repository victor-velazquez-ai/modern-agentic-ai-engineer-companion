"""Request/response/event models for agent runs (Ch 25).

These Pydantic models are the public contract of the ``/v1/runs`` endpoints.
Keep them stable and versioned with the router. Validation here means malformed
requests are rejected at the boundary, before they ever reach your agent.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, Field


def _new_run_id() -> str:
    return f"run_{uuid4().hex}"


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class RunRequest(BaseModel):
    """Input to start an agent run.

    ▢ TODO: add the fields your agent actually needs (tools, system prompt,
    conversation id, model overrides, ...). Keep ``input`` as the primary user
    message or extend it to a structured message list.
    """

    input: str = Field(
        ...,
        min_length=1,
        description="The user's prompt / task for the agent.",
        examples=["Summarize the latest quarterly report."],
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Optional caller-supplied metadata, echoed back for tracing.",
    )


class RunResponse(BaseModel):
    """The result of a synchronous (non-streaming) run."""

    id: str = Field(default_factory=_new_run_id)
    status: Literal["completed", "failed"] = "completed"
    output: str = Field(description="The agent's final text output.")
    created_at: datetime = Field(default_factory=_utcnow)
    metadata: dict[str, Any] = Field(default_factory=dict)


class RunEvent(BaseModel):
    """A single Server-Sent Event emitted while a run streams.

    The SSE endpoint serializes one of these per ``data:`` frame. ``token``
    carries an incremental chunk of output; ``type`` lets clients distinguish
    deltas from lifecycle/terminal events.
    """

    type: Literal["start", "token", "end", "error"] = "token"
    token: str | None = Field(
        default=None,
        description="Incremental output chunk (present when type == 'token').",
    )
    data: dict[str, Any] = Field(
        default_factory=dict,
        description="Extra structured payload for non-token events.",
    )
