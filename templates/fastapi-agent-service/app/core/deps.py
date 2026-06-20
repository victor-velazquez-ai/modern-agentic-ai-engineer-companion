"""Dependency-injection providers (Ch 26, 28).

A single place that wires the app's collaborators so routes declare *what* they
need (``Depends(...)``) and never construct it themselves. This keeps the
transport layer thin and makes everything trivially overridable in tests.

Providers here:
- ``get_settings``     — re-exported from ``core.settings`` (cached).
- ``get_agent_service`` — the orchestration object the routes call.
- ``get_current_principal`` — re-exported from ``core.security`` (auth).
"""

from __future__ import annotations

from functools import lru_cache

from fastapi import Depends

from app.core.security import Principal, get_current_principal
from app.core.settings import Settings, get_settings
from app.services.agent_service import AgentService

__all__ = [
    "Settings",
    "Principal",
    "get_settings",
    "get_current_principal",
    "get_agent_service",
]


@lru_cache
def _build_agent_service(mock: bool) -> AgentService:
    """Construct the agent service once per (mock) configuration."""
    return AgentService(mock=mock)


def get_agent_service(
    settings: Settings = Depends(get_settings),
) -> AgentService:
    """Provide the ``AgentService`` used by the run routes.

    ▢ TODO: if your agent needs other collaborators (an LLM client, a tool
    registry, a vector store), build them here and pass them into
    ``AgentService`` so routes stay decoupled from construction details.
    """
    return _build_agent_service(settings.is_mock)
