"""Agent-run routes: create, fetch, list, and SSE token stream (Ch 25, 26).

- ``POST /v1/runs``             — create a run (enqueued for a worker) and return it.
- ``GET  /v1/runs``             — list the tenant's runs.
- ``GET  /v1/runs/{id}``        — fetch one run.
- ``GET  /v1/runs/{id}/stream`` — stream a run's tokens as Server-Sent Events.

There is **no agent logic here** — only transport. Every route is auth- and rate-limit-gated and
delegates to ``RunService``. The SSE endpoint is written against FastAPI's native
``StreamingResponse`` (no extra dependency): each frame is a ``data: <json>\\n\\n`` line carrying
a serialized ``RunEvent``. Browsers consume it with ``EventSource``.

Streaming contract: ``EventSource`` cannot send a request body, so the prompt is passed as a
query parameter on the GET endpoint. ▢ TODO: once runs persist their input, replace the
``input`` query param with a lookup of the run created by ``POST /v1/runs``.
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse

from app.api.schemas import RunRequest, RunResponse
from app.core.auth import Principal, get_current_principal
from app.core.deps import get_run_service
from app.core.ratelimit import enforce_rate_limit
from app.services.run_service import RunService

router = APIRouter(prefix="/runs", tags=["runs"])


@router.post(
    "",
    response_model=RunResponse,
    status_code=202,
    summary="Create an agent run (enqueued)",
    dependencies=[Depends(enforce_rate_limit)],
)
async def create_run(
    request: RunRequest,
    runs: RunService = Depends(get_run_service),
    principal: Principal = Depends(get_current_principal),
) -> RunResponse:
    """Create a run for the caller's tenant. A worker executes it asynchronously."""
    run = await runs.create_run(
        tenant_id=principal.tenant_id, task=request.input, metadata=request.metadata
    )
    return RunResponse.from_domain(run)


@router.get("", response_model=list[RunResponse], summary="List the tenant's runs")
async def list_runs(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    runs: RunService = Depends(get_run_service),
    principal: Principal = Depends(get_current_principal),
) -> list[RunResponse]:
    """Return the tenant's runs, newest first."""
    items = await runs.list_runs(tenant_id=principal.tenant_id, limit=limit, offset=offset)
    return [RunResponse.from_domain(r) for r in items]


@router.get("/{run_id}", response_model=RunResponse, summary="Fetch one run")
async def get_run(
    run_id: str,
    runs: RunService = Depends(get_run_service),
    principal: Principal = Depends(get_current_principal),
) -> RunResponse:
    """Fetch a single run for the tenant (404 if it does not exist / is not theirs)."""
    run = await runs.get_run(tenant_id=principal.tenant_id, run_id=run_id)
    return RunResponse.from_domain(run)


@router.get(
    "/{run_id}/stream",
    summary="Stream an agent run (SSE)",
    # Streaming returns a raw Response, not a JSON model.
    response_model=None,
    dependencies=[Depends(enforce_rate_limit)],
)
async def stream_run(
    run_id: str,
    input: str = Query(..., min_length=1, description="The prompt to run."),
    runs: RunService = Depends(get_run_service),
    principal: Principal = Depends(get_current_principal),
) -> StreamingResponse:
    """Stream a run's output as Server-Sent Events (one ``RunEvent`` JSON per ``data:`` frame)."""

    async def event_stream() -> AsyncIterator[bytes]:
        async for event in runs.stream_run(
            tenant_id=principal.tenant_id, task=input, run_id=None
        ):
            payload = json.dumps(
                {"type": event.type, "token": event.token, "data": event.data}
            )
            # SSE framing: an `event:` line (the type) then a `data:` line, blank line ends frame.
            frame = f"event: {event.type}\ndata: {payload}\n\n"
            yield frame.encode("utf-8")

    headers = {
        "Cache-Control": "no-cache",
        "Connection": "keep-alive",
        "X-Accel-Buffering": "no",  # disable proxy buffering so tokens flush immediately
    }
    return StreamingResponse(
        event_stream(), media_type="text/event-stream", headers=headers
    )
