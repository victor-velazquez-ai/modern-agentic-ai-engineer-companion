"""Enrich: fill gaps in a CRM record from an external provider (composes ``mcp-server``).

The CRM is perpetually incomplete — ``industry`` and ``employees`` are ``null`` on the accounts
that came in via inbound. This stage closes those gaps *conservatively*: it looks the account's
domain up through the **guarded MCP boundary** (the ``enrich_company`` tool, reached via
``SafeMCPClient``), and proposes the firmographic fields back through the *same conservative
write* the call->CRM stage uses. Nothing is written that the CRM already has, and nothing is
invented — a domain the provider doesn't know returns ``found: False`` and we flag, never guess.

Why route enrichment through the conservative write too? Because the PLAN's rule is universal:
*bad data in the forecast is worse than missing data.* Enrichment is a classic source of stale or
wrong firmographics (an acquired company, a renamed entity); treating its output as a *proposal*
that only fills **empty** fields — never overwrites a human-entered value — is the senior default.

Composition: this is the ``mcp-server`` pattern blueprint again (discovery + allow-list +
schema-validated call), not a new client. ``COMPANION_MOCK=1`` (default) uses the in-memory mock
provider in :mod:`tools.crm_mock`; swap the handler for your real enrichment API and the shape and
guardrails are unchanged. No model, no spend.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from revops.compose import ensure_on_path

ensure_on_path()

from tools.crm_mock import CRMStore, connect_crm  # noqa: E402

# Firmographic fields enrichment is allowed to *propose*. Identity / pipeline fields (owner,
# stage, amount) are never enrichment's job — those come from the rep and the call.
ENRICHABLE_FIELDS: tuple[str, ...] = ("industry", "employees", "hq", "funding_stage")

# Enrichment fields fill **empty** CRM slots only; we never overwrite a human value with a guess.
# The confidence we attach to provider data — high enough to write into an *empty* slot, but the
# conservative-write policy still gates it, so one knob (``min_confidence``) governs both stages.
_ENRICHMENT_CONFIDENCE = 0.9


@dataclass(frozen=True)
class EnrichmentResult:
    """The outcome of enriching one account."""

    account_id: str
    domain: str
    found: bool
    write_report: dict[str, Any] = field(default_factory=dict)

    @property
    def applied(self) -> dict[str, Any]:
        return dict(self.write_report.get("applied", {}))

    @property
    def flagged(self) -> list[dict[str, Any]]:
        return list(self.write_report.get("flagged", []))


def _missing(value: Any) -> bool:
    """A CRM slot counts as empty (enrichable) when it's null or blank."""
    return value is None or (isinstance(value, str) and not value.strip())


def enrich_account(
    account_id: str,
    *,
    store: CRMStore | None = None,
    min_confidence: float = 0.75,
) -> EnrichmentResult:
    """Look up firmographics for one account and conservatively fill only its **empty** fields.

    Steps (all through the guarded MCP client — discovery, allow-list, schema validation apply):

    1. read the account snapshot (``crm_get_account``) to learn its domain and which fields are
       already populated;
    2. call ``enrich_company`` for that domain;
    3. propose only the :data:`ENRICHABLE_FIELDS` that the provider returned **and** the CRM is
       missing, each tagged with a confidence, through ``crm_update_fields`` — so the same
       conservative-write policy (and audit log) governs enrichment writes.

    A domain the provider doesn't know yields ``found=False`` and an empty write — we do not invent
    firmographics. Returns an :class:`EnrichmentResult` with the write report.
    """
    store = store or CRMStore()
    client = connect_crm(store)

    account = client.call("crm_get_account", {"account_id": account_id})
    domain = str(account.get("domain", "")).strip()
    if not domain:
        return EnrichmentResult(account_id=account_id, domain="", found=False)

    enrichment = client.call("enrich_company", {"domain": domain})
    if not enrichment.get("found"):
        return EnrichmentResult(account_id=account_id, domain=domain, found=False)

    # Only propose fields the provider returned that the CRM is actually missing — never overwrite
    # a value a human already entered.
    proposals: dict[str, Any] = {}
    for name in ENRICHABLE_FIELDS:
        if name not in enrichment:
            continue
        if not _missing(account.get(name)):
            continue  # CRM already has it; enrichment never overwrites a human value
        proposals[name] = {"value": enrichment[name], "confidence": _ENRICHMENT_CONFIDENCE}

    if not proposals:
        # Nothing to fill — the account is already complete on the enrichable fields.
        return EnrichmentResult(
            account_id=account_id,
            domain=domain,
            found=True,
            write_report={"account_id": account_id, "applied": {}, "flagged": [], "rejected": []},
        )

    report = client.call(
        "crm_update_fields",
        {"account_id": account_id, "fields": proposals, "min_confidence": min_confidence},
    )
    return EnrichmentResult(
        account_id=account_id,
        domain=domain,
        found=True,
        write_report=report,
    )
