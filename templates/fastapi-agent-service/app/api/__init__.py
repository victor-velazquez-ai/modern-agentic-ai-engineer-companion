"""API router aggregation.

Collects the versioned routers into a single ``api_router`` that ``main.py``
mounts. ``/health`` is intentionally unversioned (probes shouldn't care about API
versions); run routes live under ``/v1``.

▢ TODO: add new versioned routers here as your API grows.
"""

from __future__ import annotations

from fastapi import APIRouter

from app.api import health, runs

# Unversioned operational endpoints (probes).
api_router = APIRouter()
api_router.include_router(health.router)

# Versioned application endpoints.
v1_router = APIRouter(prefix="/v1")
v1_router.include_router(runs.router)

api_router.include_router(v1_router)

__all__ = ["api_router"]
