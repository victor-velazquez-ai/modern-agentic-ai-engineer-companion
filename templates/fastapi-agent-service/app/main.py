"""Application factory (Ch 25, 28).

``create_app()`` builds and returns a configured FastAPI instance. Using a
factory (rather than a module-level ``app``) keeps the app testable: tests build
a fresh app, override dependencies, and tear it down without import-time side
effects.

Run locally::

    uvicorn app.main:app --reload   # uses the module-level `app` below
    # or, explicitly via the factory:
    uvicorn "app.main:create_app" --factory --reload
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.api import api_router
from app.core.settings import get_settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup/shutdown hooks.

    ▢ TODO: open shared resources on startup (DB pool, HTTP client, model client)
    and close them on shutdown. Store them on ``app.state`` so DI providers can
    reach them.
    """
    settings = get_settings()
    logging.basicConfig(level=settings.log_level)
    log = logging.getLogger(settings.app_name)
    log.info(
        "starting %s (env=%s, mock=%s)",
        settings.app_name,
        settings.app_env,
        settings.is_mock,
    )
    # --- startup work goes here ---
    yield
    # --- shutdown work goes here ---
    log.info("shutting down %s", settings.app_name)


def create_app() -> FastAPI:
    """Build and configure the FastAPI application."""
    settings = get_settings()

    app = FastAPI(
        title=settings.app_name,
        version="0.1.0",
        lifespan=lifespan,
    )

    # Mount all routers (/health and /v1/...).
    app.include_router(api_router)

    # --- Exception handlers -------------------------------------------------
    # ▢ TODO: add handlers for your domain exceptions. This catch-all keeps
    # unexpected errors from leaking stack traces to clients.
    @app.exception_handler(Exception)
    async def _unhandled_exception_handler(
        _request: Request, exc: Exception
    ) -> JSONResponse:
        logging.getLogger(settings.app_name).exception("unhandled error: %s", exc)
        return JSONResponse(
            status_code=500,
            content={"detail": "Internal server error."},
        )

    return app


# Module-level app for `uvicorn app.main:app`. Tests should call create_app().
app = create_app()
