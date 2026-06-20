"""Agent run routes (Ch 25): synchronous run + SSE token stream.

- ``POST /v1/runs``            — run the agent and return the final output.
- ``GET  /v1/runs/{id}/stream`` — stream the agent's tokens as Server-Sent Events.

Both routes are protected by the bearer-auth dependency (a stub until you wire
your IdP — see ``core/security.py``) and delegate all work to ``AgentService``.
There is **no agent logic here** — only transport.

Note on the streaming contract: this template streams the run *input* via a query
parameter on the GET endpoint so a browser ``EventSource`` (which cannot send a
body) can consume it. ▢ TODO: if you persist runs, replace the query param with a
real lookup of the run created by ``POST /v1/runs`` using ``{id}``.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sse_starlette.sse import EventSourceResponse

from app.core.deps import get_agent_service, get_current_principal
from app.core.security import Principal
from app.schemas.runs import RunRequest, RunResponse
from app.services.agent_service import AgentService

router = APIRouter(prefix="/runs", tags=["runs"])


@router.post("", response_model=RunResponse, summary="Run the agent (synchronous)")
async def create_run(
    request: RunRequest,
    agent: AgentService = Depends(get_agent_service),
    _principal: Principal = Depends(get_current_principal),
) -> RunResponse:
    """Run the agent to completion and return its final output."""
    return await agent.run(request)


@router.get(
    "/{run_id}/stream",
    summary="Stream an agent run (SSE)",
    # Streaming endpoint returns a raw Response, not a JSON model — tell FastAPI
    # not to build a response model from the return annotation.
    response_model=None,
)
async def stream_run(
    run_id: str,
    input: str = Query(..., min_length=1, description="The prompt to run."),
    agent: AgentService = Depends(get_agent_service),
    _principal: Principal = Depends(get_current_principal),
) -> EventSourceResponse:
    """Stream the agent's output as Server-Sent Events.

    Each SSE frame's ``data`` is a JSON-serialized ``RunEvent``.
    """
    request = RunRequest(input=input, metadata={"run_id": run_id})

    async def event_publisher():
        async for event in agent.stream(request):
            # sse-starlette sends the dict's "data" as the SSE payload.
            yield {"event": event.type, "data": event.model_dump_json()}

    return EventSourceResponse(event_publisher())
