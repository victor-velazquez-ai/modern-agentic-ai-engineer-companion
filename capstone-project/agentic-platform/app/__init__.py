"""The platform's HTTP backend (Appendix C · ``app/``).

This package is the capstone's *assembled* FastAPI backend — the integrated counterpart to
the [`fastapi-agent-service`](../../../templates/fastapi-agent-service) **template**. Where
the template is the smallest copy-into-your-job scaffold, this is the full modular-monolith
service the book builds across Part VII (Ch 25–31): a thin transport layer over a
framework-free domain, with strict module boundaries.

Layout (matches Appendix C)
---------------------------
``main.py``    app factory + lifespan + router mount + exception handlers (Ch 25, 28).
``api/``       route modules — runs (sync + SSE), chats, documents, health (Ch 25, 26).
``core/``      Pydantic ``Settings``, auth/principal, rate limiting, DI providers (Ch 26, 28).
``domain/``    framework-free business logic — entities + ports, imports nothing web/db (Ch 28).
``db/``        SQLAlchemy models, async session/engine, repositories (Ch 30).
``services/``  orchestration between ``domain`` ports and the db/agent adapters (Ch 28).

The cardinal rule of the modular monolith (Ch 27–28): ``domain/`` is the core and imports
*nothing* from ``api``, ``db``, or ``services``; dependencies point inward. ``services/`` wires
the domain ports to concrete adapters (repositories, the agent engine). Everything is
MOCK-runnable: with ``COMPANION_MOCK=1`` (the default) the backend serves the full
request/stream path with no API key and no spend — the single seam to a real model lives behind
``services.agent_service.AgentEngine``.
"""

from __future__ import annotations

__all__ = ["__version__"]

__version__ = "0.1.0"
