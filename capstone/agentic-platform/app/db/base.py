"""Declarative base + shared conventions (Ch 30).

A single ``Base`` all ORM models inherit from, plus small mixins for the columns every table
shares (timestamps, a tenant id). Keeping these here means the table definitions in
``models.py`` stay about the *domain* columns, not boilerplate.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, String, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """Declarative base for all ORM models."""


class TimestampMixin:
    """``created_at`` / ``updated_at`` columns managed by the database."""

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class TenantMixin:
    """The ``tenant_id`` column + an index, so every table is multi-tenant by construction.

    Repositories *always* filter by this column; it is the storage-level half of the tenant
    isolation the ``Principal`` enforces at the edge (Ch 26).
    """

    tenant_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
