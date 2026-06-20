"""Health endpoint (liveness + readiness).

A single ``GET /health`` that returns ``{"status": "ok"}``. The Dockerfile's
``HEALTHCHECK`` hits it, and orchestrators (Kubernetes, ECS) can use it for both
liveness and readiness probes.

▢ TODO: if readiness should depend on a downstream (DB, cache, vector store),
add a check here and return 503 when a dependency is unavailable.
"""

from __future__ import annotations

from fastapi import APIRouter

router = APIRouter(tags=["health"])


@router.get("/health", summary="Liveness/readiness probe")
async def health() -> dict[str, str]:
    """Return service health. Always 200 when the process is serving."""
    return {"status": "ok"}
