"""Least-privilege ops tools, exposed via the ``mcp-server`` pattern (Ch 19, 41)."""

from __future__ import annotations

from .ops_mock import (
    MUTATING_TOOLS,
    READ_TOOLS,
    build_ops_client,
    build_ops_server,
)

__all__ = [
    "build_ops_server",
    "build_ops_client",
    "READ_TOOLS",
    "MUTATING_TOOLS",
]
