"""The seam between the platform and *a* reasoning engine (Ch 12, 18, 25).

The API never calls an agent or a model SDK directly — it calls an :class:`AgentEngine`. This
module provides two implementations behind that one port:

* :class:`MockAgentEngine` — offline and deterministic. With ``COMPANION_MOCK=1`` (the default)
  the whole request/stream path runs with **no API key and no spend**. This is what tests and
  local dev use.
* :class:`RawLoopAgentEngine` — the live adapter that wraps the capstone's framework-free
  ``agents/raw`` loop (the hardened version of the Ch 12 build, mirrored by the
  ``blueprints/agent-loop`` blueprint). It is imported *lazily* so this module — and the whole
  backend — compiles and mock-runs even before/without the ``agents/`` package present.

Swapping engines changes nothing in ``api/``: that decoupling is the entire point of the seam.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Any


@dataclass
class AgentRunEvent:
    """One streamed event from an engine — the concrete shape behind ``ports.AgentEvent``.

    ``type`` is one of ``start`` | ``token`` | ``end`` | ``error``; ``token`` carries an
    incremental chunk of output (present when ``type == "token"``). ``data`` holds structured
    payload for non-token events (e.g. an error message, a tool name, a citation).
    """

    type: str = "token"
    token: str | None = None
    data: dict[str, Any] = field(default_factory=dict)


# Canned tokens streamed in MOCK mode. Intentionally boring — they exist only to prove the
# stream path works end-to-end without a model call.
_MOCK_TOKENS: tuple[str, ...] = (
    "[mock] ",
    "Wired ",
    "the ",
    "agent ",
    "engine ",
    "behind ",
    "the ",
    "AgentEngine ",
    "port. ",
    "Set ",
    "COMPANION_MOCK=0 ",
    "and ",
    "wire ",
    "agents/raw ",
    "for ",
    "the ",
    "live ",
    "loop.",
)


class MockAgentEngine:
    """A deterministic, offline engine. Satisfies ``domain.ports.AgentEngine`` structurally."""

    def __init__(self, *, token_delay_s: float = 0.0) -> None:
        # A tiny delay makes the stream observably incremental in a live demo; 0 in tests.
        self._token_delay_s = token_delay_s

    async def run(self, task: str, *, tenant_id: str) -> str:
        """Return a canned final answer that echoes the task (no model call)."""
        await asyncio.sleep(0)  # yield control; keeps the contract truly async
        body = "".join(_MOCK_TOKENS)
        return f"{body} (task: {task!r}, tenant: {tenant_id})"

    async def stream(self, task: str, *, tenant_id: str) -> AsyncIterator[AgentRunEvent]:
        """Yield a ``start`` event, one ``token`` per chunk, then ``end``."""
        yield AgentRunEvent(type="start", data={"task": task, "tenant_id": tenant_id})
        for token in _MOCK_TOKENS:
            if self._token_delay_s:
                await asyncio.sleep(self._token_delay_s)
            yield AgentRunEvent(type="token", token=token)
        yield AgentRunEvent(type="end")


class RawLoopAgentEngine:
    """Live adapter over the capstone's framework-free ``agents/raw`` loop (Ch 12).

    Kept thin and import-lazy: the heavy ``agents`` package (and any model SDK it pulls) is only
    imported when a live engine is actually constructed, so MOCK mode and ``py_compile`` never
    touch it. If the package is not present yet (it is built by its own chapters), construction
    raises a clear error and the caller falls back to the mock.

    ▢ TODO: when ``agents/raw`` lands its public entrypoint, map ``run``/``stream`` onto it here.
    The expected shape (mirroring the agent-loop blueprint) is a ``run(task, tools, model)`` that
    returns an ``AgentResult`` and an async token iterator. Until then this raises on use so the
    backend defaults to the mock rather than failing silently.
    """

    def __init__(self, *, model: str, api_key: str | None) -> None:
        self._model = model
        self._api_key = api_key
        self._loop = self._build_loop()

    def _build_loop(self) -> Any:
        try:
            # Lazy import: only reached in live mode with a real key.
            import agents.raw as _raw  # noqa: F401  (capstone package, built by Ch 12)
        except ModuleNotFoundError as exc:  # pragma: no cover - depends on build order
            raise RuntimeError(
                "Live agent engine requested but the capstone 'agents/raw' package is not "
                "available. Build it (Ch 12) or run with COMPANION_MOCK=1."
            ) from exc
        # ▢ TODO: construct and return the real loop once its API is fixed.
        raise NotImplementedError(
            "RawLoopAgentEngine is a wiring point. Connect it to agents/raw's entrypoint, "
            "or run with COMPANION_MOCK=1 to use MockAgentEngine."
        )

    async def run(self, task: str, *, tenant_id: str) -> str:  # pragma: no cover - live only
        raise NotImplementedError

    async def stream(  # pragma: no cover - live only
        self, task: str, *, tenant_id: str
    ) -> AsyncIterator[AgentRunEvent]:
        raise NotImplementedError
        yield AgentRunEvent()  # unreachable; tells the type checker this is an async generator


def build_agent_engine(*, mock: bool, model: str, api_key: str | None) -> Any:
    """Factory: pick the engine for the current configuration.

    Returns the offline :class:`MockAgentEngine` when ``mock`` is true (the default), otherwise
    the live :class:`RawLoopAgentEngine`. The return type is the ``AgentEngine`` port — callers
    depend only on ``run`` / ``stream``.
    """
    if mock:
        return MockAgentEngine(token_delay_s=0.0)
    return RawLoopAgentEngine(model=model, api_key=api_key)
