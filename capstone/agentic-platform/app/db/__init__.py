"""Data layer — SQLAlchemy models, async sessions, repositories (Ch 30).

``db/`` is an *adapter* layer: it implements the domain's persistence ports
(``RunRepository``, ``ChatRepository``, ``DocumentRepository``) on top of SQLAlchemy. The domain
never imports from here; ``services/`` wires these repositories to the domain through the ports.

Contents
--------
``base.py``          the declarative ``Base`` + shared column/type conventions.
``models.py``        ORM row classes (``AgentRunRow`` …) — the storage shape, distinct from the
                     domain entities they map to/from.
``session.py``       the async engine + ``sessionmaker`` + a request-scoped session dependency.
``repositories.py``  the concrete repositories that translate ORM rows ↔ domain objects.
``migrations/``      Alembic environment + versions (schema as code).

The compose stack uses Postgres + pgvector; tests and MOCK runs default to in-memory SQLite, so
nothing here needs a database server to import or unit-test.
"""

from __future__ import annotations

__all__: list[str] = []
