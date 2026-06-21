"""Dependency-injection providers — the one place collaborators are wired (Ch 26, 28).

Routes declare *what* they need (``Depends(get_run_service)``) and never construct it. Here we
assemble the dependency graph for each request: a DB session → repositories (adapters for the
domain ports) → services. Swapping an implementation (a fake repo in a test, a different engine
in live mode) happens here or via FastAPI dependency overrides — the routes don't change.

Re-exports of ``get_settings`` / ``get_current_principal`` keep ``api/`` importing one module.
"""

from __future__ import annotations

from functools import lru_cache

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import Principal, get_current_principal, require_scope
from app.core.config import Settings, get_settings
from app.db.repositories import (
    SqlAlchemyChatRepository,
    SqlAlchemyDocumentRepository,
    SqlAlchemyRunRepository,
)
from app.db.session import get_session
from app.domain.ports import AgentEngine
from app.services.agent_service import build_agent_engine
from app.services.chat_service import ChatService
from app.services.document_service import DocumentService
from app.services.run_service import RunService

__all__ = [
    "Settings",
    "Principal",
    "get_settings",
    "get_current_principal",
    "require_scope",
    "get_agent_engine",
    "get_run_service",
    "get_chat_service",
    "get_document_service",
]


@lru_cache
def _build_engine(mock: bool, model: str, api_key: str | None) -> AgentEngine:
    """Construct the agent engine once per (mock, model, key) configuration."""
    return build_agent_engine(mock=mock, model=model, api_key=api_key)


def get_agent_engine(settings: Settings = Depends(get_settings)) -> AgentEngine:
    """Provide the agent engine (mock offline, or the live raw-loop adapter)."""
    return _build_engine(settings.is_mock, settings.default_model, settings.anthropic_api_key)


def get_run_service(
    session: AsyncSession = Depends(get_session),
    engine: AgentEngine = Depends(get_agent_engine),
) -> RunService:
    """Assemble the run service from a request-scoped session + the engine."""
    return RunService(runs=SqlAlchemyRunRepository(session), engine=engine)


def get_chat_service(
    session: AsyncSession = Depends(get_session),
) -> ChatService:
    """Assemble the chat service from a request-scoped session."""
    return ChatService(chats=SqlAlchemyChatRepository(session))


def get_document_service(
    session: AsyncSession = Depends(get_session),
) -> DocumentService:
    """Assemble the document service from a request-scoped session."""
    return DocumentService(documents=SqlAlchemyDocumentRepository(session))
