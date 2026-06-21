"""Alembic migration environment (Ch 30).

Schema as code. ``env.py`` wires Alembic to the app's ``Base.metadata`` and ``DATABASE_URL`` so
``alembic upgrade head`` (run by the compose ``api`` service on boot) brings any database to the
current schema. ``versions/`` holds the ordered migration scripts; the initial one creates the
four core tables. ``alembic.ini`` lives at the repo root in the assembled stack.
"""

from __future__ import annotations

__all__: list[str] = []
