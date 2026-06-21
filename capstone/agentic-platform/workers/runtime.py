"""Worker runtime helpers — the bridge from sync Celery tasks to the async app (Ch 31).

Celery task bodies are synchronous, but the platform's services are ``async`` (they own a DB
session). ``run_async`` runs a coroutine to completion on a fresh event loop so a task can call
the same use-cases the API does, with no duplicated logic.

``session_scope`` yields a request-style transactional session built from the same engine config
as the API, and ``build_engine`` returns the agent engine for the worker (mock or live) — so a
worker and a web request reach the model through the identical seam.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Awaitable, Callable, Coroutine
from contextlib import asynccontextmanager
from typing import TypeVar

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.db.session import get_sessionmaker
from app.domain.ports import AgentEngine
from app.services.agent_service import build_agent_engine

T = TypeVar("T")


def run_async(coro: Coroutine[None, None, T]) -> T:
    """Run an async coroutine to completion from a synchronous Celery task body.

    Uses ``asyncio.run`` (a fresh loop per call), which is correct for the short-lived,
    one-coroutine-per-task shape of Celery work. For a long-lived loop reused across tasks, swap
    this for a persistent loop on the worker process (▢ TODO if throughput demands it).
    """
    return asyncio.run(coro)


@asynccontextmanager
async def session_scope() -> AsyncIterator[AsyncSession]:
    """Yield a transactional async session, committing on success and rolling back on error."""
    factory = get_sessionmaker()
    async with factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


def build_engine() -> AgentEngine:
    """Return the agent engine for the worker, honoring ``COMPANION_MOCK`` (mock by default)."""
    settings = get_settings()
    return build_agent_engine(
        mock=settings.is_mock,
        model=settings.default_model,
        api_key=settings.anthropic_api_key,
    )


async def gather_stream(
    make_stream: Callable[[], AsyncIterator[T]],
) -> list[T]:
    """Drain an async iterator into a list — handy when a task needs the whole stream."""
    items: list[T] = []
    async for item in make_stream():
        items.append(item)
    return items


def as_awaitable(value: T) -> Awaitable[T]:
    """Wrap a plain value in a coroutine (small adapter for uniform task bodies)."""

    async def _coro() -> T:
        return value

    return _coro()
