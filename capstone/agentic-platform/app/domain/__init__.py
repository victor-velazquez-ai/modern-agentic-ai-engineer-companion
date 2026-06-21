"""Framework-free business logic — the core of the modular monolith (Ch 28).

``domain/`` is the platform's nucleus. The cardinal rule: **it imports nothing from**
``app.api``, ``app.db``, ``app.services``, FastAPI, SQLAlchemy, or any model SDK. Dependencies
point *inward* — the outer layers depend on the domain, never the reverse. That is what lets
the same business rules be exercised by a unit test, an HTTP route, or a Celery worker without
change.

Contents
--------
``models.py``   plain entities + value objects (``AgentRun``, ``ChatMessage``, ``Document``) and
                their state machine — dataclasses and enums, no ORM, no Pydantic.
``ports.py``    the abstract seams (``Protocol`` interfaces) the domain depends on:
                ``RunRepository``, ``ChatRepository``, ``DocumentRepository``, ``AgentEngine``.
                ``services/`` and ``db/`` provide the concrete adapters.
``errors.py``   the domain's own exception hierarchy — raised here, translated to HTTP in ``api``.

If a change here needs an import from ``db`` or ``api``, the boundary is in the wrong place —
that is exactly the seam the book's "extract this" advice is about.
"""

from __future__ import annotations

__all__: list[str] = []
