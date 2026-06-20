"""Agent orchestration layer (the seam between transport and *your* agent).

The API routes never call your agent directly — they call this service. That
boundary is the whole point of the template: swap the body of the two methods
below for your real agent and nothing in ``api/`` has to change.

MOCK mode (``COMPANION_MOCK=1``, the default) yields a canned response so the
sync and streaming paths are fully exercisable in tests with **no API spend**.

# TODO: call your agent.
#   - In ``run``: invoke your agent and return its final text.
#   - In ``stream``: yield ``RunEvent`` objects as tokens arrive from your agent.
# The agent you build is taught by the book; see the agent-loop blueprint:
#   ../../blueprints/agent-loop/  (the hardened version of what you wire in here)
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator

from app.schemas.runs import RunEvent, RunRequest, RunResponse

# Canned tokens streamed in MOCK mode. Intentionally boring — they exist only to
# prove the stream path works end-to-end without a model call.
_MOCK_TOKENS: tuple[str, ...] = (
    "[mock] ",
    "This ",
    "is ",
    "a ",
    "canned ",
    "streamed ",
    "response. ",
    "Wire ",
    "your ",
    "agent ",
    "in ",
    "services/agent_service.py.",
)


class AgentService:
    """Orchestrates a single agent run.

    Parameters
    ----------
    mock:
        When True, return/stream canned output instead of calling a real agent.
        Driven by ``Settings.companion_mock`` via the DI provider.
    """

    def __init__(self, *, mock: bool = True) -> None:
        self._mock = mock

    async def run(self, request: RunRequest) -> RunResponse:
        """Run the agent synchronously and return its final output.

        ▢ TODO (live mode): replace the body below with a call to your agent and
        return ``RunResponse(output=<agent final text>)``.
        """
        if self._mock:
            output = "".join(_MOCK_TOKENS)
            return RunResponse(output=output, metadata=request.metadata)

        # TODO: call your agent here and build a RunResponse from its result.
        raise NotImplementedError(
            "Live agent call not implemented. Set COMPANION_MOCK=1 to use the "
            "mock, or wire your agent in AgentService.run()."
        )

    async def stream(self, request: RunRequest) -> AsyncIterator[RunEvent]:
        """Stream the agent's output as a sequence of ``RunEvent`` objects.

        Yields a ``start`` event, then one ``token`` event per chunk, then an
        ``end`` event. The route serializes each event as an SSE ``data:`` frame.

        ▢ TODO (live mode): replace the mock loop with your agent's token stream,
        yielding ``RunEvent(type="token", token=chunk)`` as chunks arrive.
        """
        yield RunEvent(type="start")

        if self._mock:
            for token in _MOCK_TOKENS:
                # Tiny sleep so the stream is observably incremental.
                await asyncio.sleep(0.01)
                yield RunEvent(type="token", token=token)
            yield RunEvent(type="end")
            return

        # TODO: stream tokens from your agent here, then yield the end event.
        yield RunEvent(
            type="error",
            data={"message": "Live streaming not implemented; set COMPANION_MOCK=1."},
        )
