"""Alembic environment (Ch 30).

Bridges Alembic to the application's settings and ORM metadata so migrations and the running app
agree on one schema. The DSN comes from ``Settings.database_url`` (env-driven, never hard-coded);
``target_metadata`` is the app's ``Base.metadata`` so ``--autogenerate`` sees every model.

Alembic drives this with a sync DSN, so we strip any async driver suffix (``+asyncpg`` /
``+aiosqlite``) before handing the URL to the engine here.
"""

from __future__ import annotations

from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from app.core.config import get_settings
from app.db.base import Base

# Import models so they register on Base.metadata before autogenerate runs.
from app.db import models as _models  # noqa: F401

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def _sync_url() -> str:
    """Return a sync SQLAlchemy URL for Alembic from the app's (async) DSN."""
    url = get_settings().database_url
    return url.replace("+asyncpg", "+psycopg").replace("+aiosqlite", "")


def run_migrations_offline() -> None:
    """Emit SQL to a script without a live connection (``alembic upgrade --sql``)."""
    context.configure(
        url=_sync_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations against a live connection."""
    section = config.get_section(config.config_ini_section) or {}
    section["sqlalchemy.url"] = _sync_url()
    connectable = engine_from_config(
        section, prefix="sqlalchemy.", poolclass=pool.NullPool
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection, target_metadata=target_metadata, compare_type=True
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
