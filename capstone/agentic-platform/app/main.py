"""Application factory + lifespan (Ch 25, 28).

``create_app()`` builds and returns a configured FastAPI instance. Using a factory (not a
module-level ``app`` constructed at import) keeps the app testable: a test builds a fresh app,
overrides dependencies, and tears it down without import-time side effects.

The ``lifespan`` context manages shared resources: on startup it configures logging and — in
local/MOCK mode — creates the schema so the in-memory SQLite database is ready without a separate
migration step (production runs ``alembic upgrade head`` instead). On shutdown it disposes the
database engine's connection pool so a graceful stop drains cleanly (Ch 28).

Run locally::

    uvicorn app.main:app --reload                       # the module-level app below
    uvicorn "app.main:create_app" --factory --reload    # explicitly via the factory
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api import api_router
from app.api.errors import register_exception_handlers
from app.core.config import get_settings
from app.db.session import create_all, dispose_engine


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Open shared resources on startup, close them on shutdown."""
    settings = get_settings()
    logging.basicConfig(level=settings.log_level)
    log = logging.getLogger(settings.app_name)
    log.info(
        "starting %s (env=%s, mock=%s)",
        settings.app_name,
        settings.app_env,
        settings.is_mock,
    )

    # In local/MOCK mode, stand up the schema so the app runs with zero external setup.
    # Production relies on Alembic migrations (app/db/migrations), not this path.
    if settings.app_env == "local":
        try:
            await create_all()
            log.info("schema ensured (local bootstrap)")
        except Exception as exc:  # pragma: no cover - depends on a reachable DB
            log.warning("schema bootstrap skipped: %s", exc)

    yield

    # --- shutdown: drain the pool ---
    await dispose_engine()
    log.info("shutting down %s", settings.app_name)


def create_app() -> FastAPI:
    """Build and configure the FastAPI application."""
    settings = get_settings()

    app = FastAPI(
        title=settings.app_name,
        version="0.1.0",
        summary="Agentic platform backend — runs, chats, documents, with SSE streaming.",
        lifespan=lifespan,
    )

    # Mount all routers (/health, /readyz, /v1/...).
    app.include_router(api_router)

    # Translate domain errors → HTTP and install the catch-all handler.
    register_exception_handlers(app)

    return app


# Module-level app for `uvicorn app.main:app`. Tests should call create_app().
app = create_app()
