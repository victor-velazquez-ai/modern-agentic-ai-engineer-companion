"""Async engine, session factory, and the request-scoped session dependency (Ch 30).

One engine per process (a connection pool), one ``AsyncSession`` per request. The
``get_session`` dependency yields a session inside a transaction and guarantees it is committed
on success and rolled back on error, then closed — so routes never leak connections and never
half-commit.

The engine is created lazily from ``Settings.database_url`` so importing this module never
touches a database (tests and MOCK runs stay dependency-free). ``create_all`` is offered for
local/test bootstrapping; production schema changes go through Alembic (``db/migrations``).
"""

from __future__ import annotations

from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import Settings, get_settings
from app.db.base import Base

# Lazily-built singletons. Built on first use so import has no side effects.
_engine: AsyncEngine | None = None
_sessionmaker: async_sessionmaker[AsyncSession] | None = None


def get_engine(settings: Settings | None = None) -> AsyncEngine:
    """Return the process-wide async engine, building it once from settings."""
    global _engine
    if _engine is None:
        settings = settings or get_settings()
        # SQLite (tests/mock) does not accept pool sizing args; guard on the dialect.
        is_sqlite = settings.database_url.startswith("sqlite")
        kwargs: dict[str, object] = {"echo": settings.db_echo, "future": True}
        if not is_sqlite:
            kwargs["pool_size"] = settings.db_pool_size
            kwargs["pool_pre_ping"] = True
        _engine = create_async_engine(settings.database_url, **kwargs)
    return _engine


def get_sessionmaker(
    settings: Settings | None = None,
) -> async_sessionmaker[AsyncSession]:
    """Return the process-wide session factory bound to the engine."""
    global _sessionmaker
    if _sessionmaker is None:
        _sessionmaker = async_sessionmaker(
            bind=get_engine(settings),
            expire_on_commit=False,
            class_=AsyncSession,
        )
    return _sessionmaker


async def get_session() -> AsyncIterator[AsyncSession]:
    """FastAPI dependency: yield a transactional session, commit/rollback/close around it."""
    factory = get_sessionmaker()
    async with factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def create_all() -> None:
    """Create every table from the ORM metadata (local/test bootstrap only).

    Production uses Alembic migrations (``db/migrations``); this is the convenience path so a
    test or a ``COMPANION_MOCK`` run can stand up the schema in one call.
    """
    engine = get_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def dispose_engine() -> None:
    """Dispose the engine's pool on shutdown (called from the app lifespan)."""
    global _engine, _sessionmaker
    if _engine is not None:
        await _engine.dispose()
    _engine = None
    _sessionmaker = None
