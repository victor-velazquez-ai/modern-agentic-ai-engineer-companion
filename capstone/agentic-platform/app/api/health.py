"""Health endpoints — liveness + readiness (Ch 25, 28).

``GET /health`` is the always-200 liveness probe (the Dockerfile ``HEALTHCHECK`` and the
orchestrator hit it). ``GET /readyz`` is the readiness probe: it checks the dependencies the app
needs to serve traffic (the database) and returns 503 when one is down, so a rolling deploy does
not send traffic to a pod that cannot talk to Postgres.
"""

from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.core.config import get_settings
from app.db.session import get_sessionmaker

router = APIRouter(tags=["health"])


@router.get("/health", summary="Liveness probe")
async def health() -> dict[str, str]:
    """Return service health. Always 200 when the process is serving."""
    return {"status": "ok"}


@router.get("/readyz", summary="Readiness probe")
async def readyz() -> JSONResponse:
    """Return 200 only when downstream dependencies are reachable, else 503."""
    settings = get_settings()
    checks: dict[str, str] = {}
    healthy = True

    try:
        factory = get_sessionmaker(settings)
        async with factory() as session:
            await session.execute(text("SELECT 1"))
        checks["database"] = "ok"
    except Exception as exc:  # pragma: no cover - depends on a live DB
        checks["database"] = f"error: {exc.__class__.__name__}"
        healthy = False

    code = 200 if healthy else 503
    return JSONResponse(status_code=code, content={"status": "ok" if healthy else "degraded", "checks": checks})
