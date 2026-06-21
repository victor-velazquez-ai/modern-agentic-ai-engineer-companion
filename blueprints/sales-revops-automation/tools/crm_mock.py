"""Mock CRM exposed over MCP — the guarded tool boundary (composes ``mcp-server``, Ch 19).

The whole revenue motion depends on the CRM, so the agent must touch it through a *boundary*,
not a raw SDK call. We compose the ``mcp-server`` pattern blueprint for exactly that: the CRM
lives behind an in-process MCP server, and the workflow reaches it through ``SafeMCPClient`` — an
allow-listed, schema-validating, timeout-bounded client. Discovery sees every tool; only the
allow-listed ones are callable.

What this module exposes:

* ``crm_get_account``    — read one account snapshot (read-only).
* ``crm_update_fields``  — a **conservative** write: it refuses to write low-confidence or
  ``null`` field values, and it never silently overwrites a non-empty CRM field with a guess.
  (Bad data in the forecast is worse than missing data — the PLAN's rule.)
* ``enrich_company``     — mock external-data enrichment (no real provider call).

The store is an in-memory dict seeded from ``data/accounts.json`` so the demo and tests are
deterministic and free. Swap the handlers for your real CRM's API/MCP server and your
enrichment provider; the *shapes* and the guardrails do not change. (PLAN -> "How to adapt".)
"""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any, Mapping

# Make the sibling pattern blueprints importable (no fork; relative-import composition).
from revops.compose import data_dir

from mcp_server import (  # noqa: E402  (import after path bootstrap)
    InProcessTransport,
    MCPServer,
    SafeMCPClient,
    Tool,
)

# The fields a write is *allowed* to touch. Anything else is rejected at the boundary — an agent
# cannot invent new CRM columns, and cannot touch identity fields (owner, account_id, contact).
WRITABLE_FIELDS: frozenset[str] = frozenset(
    {"stage", "amount", "next_step", "close_date", "industry", "employees", "notes"}
)

# Tools the workflow is permitted to call. Least privilege: the safe client denies everything
# not on this list, even though discovery can see more.
ALLOWED_TOOLS: tuple[str, ...] = ("crm_get_account", "crm_update_fields", "enrich_company")


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


class CRMStore:
    """An in-memory CRM seeded from the bundled sample data.

    Holds accounts by id and the mock enrichment table by domain. Deep-copies on read so a caller
    can't mutate the store by holding a reference — the only mutation path is :meth:`update_fields`,
    which is where the conservative-write policy lives.
    """

    def __init__(
        self,
        accounts: Mapping[str, Any] | None = None,
        enrichment: Mapping[str, Any] | None = None,
    ) -> None:
        d = data_dir()
        self._accounts: dict[str, Any] = dict(
            accounts if accounts is not None else _load_json(d / "accounts.json")
        )
        self._enrichment: dict[str, Any] = dict(
            enrichment if enrichment is not None else _load_json(d / "enrichment.json")
        )
        # Audit log of every accepted/rejected write — the trail RevOps actually wants.
        self.write_log: list[dict[str, Any]] = []

    # --- reads ---------------------------------------------------------------------------------

    def get_account(self, account_id: str) -> dict[str, Any]:
        acct = self._accounts.get(account_id)
        if acct is None:
            raise KeyError(f"no such account: {account_id!r}")
        return copy.deepcopy(acct)

    def enrich(self, domain: str) -> dict[str, Any]:
        record = self._enrichment.get(domain)
        if record is None:
            return {"domain": domain, "found": False}
        out = dict(record)
        out["found"] = True
        return out

    # --- the conservative write ----------------------------------------------------------------

    def update_fields(
        self,
        account_id: str,
        fields: Mapping[str, Any],
        *,
        min_confidence: float = 0.75,
    ) -> dict[str, Any]:
        """Write only high-confidence, non-empty, writable fields. Flag the rest.

        ``fields`` maps a CRM field name to ``{"value": ..., "confidence": float}``. A field is
        written only if **all** of these hold:

        * the field name is in :data:`WRITABLE_FIELDS` (no inventing columns / touching identity);
        * ``confidence >= min_confidence`` (don't poison the forecast with a guess);
        * the value is not ``None``/empty (missing is better than wrong).

        Everything else is returned under ``flagged`` for a human to confirm — never written
        silently. Returns a structured report (``applied`` / ``flagged`` / ``rejected``).
        """
        acct = self._accounts.get(account_id)
        if acct is None:
            raise KeyError(f"no such account: {account_id!r}")

        applied: dict[str, Any] = {}
        flagged: list[dict[str, Any]] = []
        rejected: list[dict[str, Any]] = []

        for name, proposal in fields.items():
            value = proposal.get("value") if isinstance(proposal, Mapping) else proposal
            confidence = (
                float(proposal.get("confidence", 0.0))
                if isinstance(proposal, Mapping)
                else 0.0
            )

            if name not in WRITABLE_FIELDS:
                rejected.append({"field": name, "reason": "field is not writable"})
                continue
            if value is None or (isinstance(value, str) and not value.strip()):
                flagged.append(
                    {"field": name, "value": value, "reason": "empty/null value — not written"}
                )
                continue
            if confidence < min_confidence:
                flagged.append(
                    {
                        "field": name,
                        "value": value,
                        "confidence": round(confidence, 2),
                        "reason": f"low confidence (< {min_confidence}); left for human review",
                    }
                )
                continue
            acct[name] = value
            applied[name] = value

        report = {
            "account_id": account_id,
            "applied": applied,
            "flagged": flagged,
            "rejected": rejected,
        }
        self.write_log.append(report)
        return report


# --- MCP tool handlers (close over a single store instance) -----------------------------------


def build_crm_tools(store: CRMStore) -> list[Tool]:
    """Build the MCP :class:`Tool` set backed by ``store`` (handlers are pure over the store)."""

    def _get_account(args: Mapping[str, Any]) -> dict[str, Any]:
        return store.get_account(str(args["account_id"]))

    def _update_fields(args: Mapping[str, Any]) -> dict[str, Any]:
        return store.update_fields(
            str(args["account_id"]),
            dict(args["fields"]),
            min_confidence=float(args.get("min_confidence", 0.75)),
        )

    def _enrich(args: Mapping[str, Any]) -> dict[str, Any]:
        return store.enrich(str(args["domain"]))

    return [
        Tool(
            name="crm_get_account",
            description="Read one CRM account snapshot by account_id (read-only).",
            input_schema={
                "type": "object",
                "properties": {"account_id": {"type": "string"}},
                "required": ["account_id"],
                "additionalProperties": False,
            },
            handler=_get_account,
        ),
        Tool(
            name="crm_update_fields",
            description=(
                "Conservatively write CRM fields. Each field carries a value and a confidence; "
                "low-confidence or empty fields are flagged for human review, not written."
            ),
            input_schema={
                "type": "object",
                "properties": {
                    "account_id": {"type": "string"},
                    "fields": {"type": "object"},
                    "min_confidence": {"type": "number", "minimum": 0, "maximum": 1},
                },
                "required": ["account_id", "fields"],
                "additionalProperties": False,
            },
            handler=_update_fields,
        ),
        Tool(
            name="enrich_company",
            description="Look up external firmographic data for a company domain (mock provider).",
            input_schema={
                "type": "object",
                "properties": {"domain": {"type": "string"}},
                "required": ["domain"],
                "additionalProperties": False,
            },
            handler=_enrich,
        ),
    ]


def build_crm_server(store: CRMStore | None = None, *, name: str = "crm-mock") -> MCPServer:
    """Stand up an in-process MCP server exposing the CRM tools."""
    store = store or CRMStore()
    server = MCPServer(name=name)
    for tool in build_crm_tools(store):
        server.add_tool(tool)
    return server


def connect_crm(
    store: CRMStore | None = None,
    *,
    allow: tuple[str, ...] = ALLOWED_TOOLS,
    timeout: float = 5.0,
) -> SafeMCPClient:
    """Return a *ready* guarded MCP client for the CRM: handshaked, discovered, allow-listed.

    This is the seam the workflow imports. The client denies anything not in ``allow`` and
    validates every call against the discovered schema before it reaches the (mock) CRM.
    """
    server = build_crm_server(store)
    transport = InProcessTransport(server)
    client = SafeMCPClient(transport, allow=allow, timeout=timeout)
    client.initialize()
    client.discover()
    return client
