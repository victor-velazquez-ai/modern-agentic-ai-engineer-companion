"""Tool boundary for the RevOps solution — the (mock) CRM exposed over MCP.

The PLAN's structure puts the CRM tool surface here, behind the ``mcp-server`` pattern blueprint
so the agent reaches the CRM only through a guarded, allow-listed client (conservative writes
only). See :mod:`tools.crm_mock`.
"""

from __future__ import annotations
