"""API router aggregation (Ch 25).

Collects the route modules into a single ``api_router`` that ``main.py`` mounts. ``/health`` and
``/readyz`` are intentionally unversioned (probes shouldn't care about API versions); the
application endpoints live under ``/v1`` so the surface can evolve without breaking clients.

▢ TODO: add new versioned routers here as the API grows (e.g. ``/v1/approvals`` for Ch 20).
"""

from __future__ import annotations

from fastapi import APIRouter

from app.api import chats, documents, health, runs

# Unversioned operational endpoints (probes).
api_router = APIRouter()
api_router.include_router(health.router)

# Versioned application endpoints.
v1_router = APIRouter(prefix="/v1")
v1_router.include_router(runs.router)
v1_router.include_router(chats.router)
v1_router.include_router(documents.router)

api_router.include_router(v1_router)

__all__ = ["api_router"]
