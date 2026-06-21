"""tenancy — per-user + per-tenant isolation for the product copilot (Ch 41/43).

The single most important property of a *customer-facing* copilot is that one tenant can never
see another tenant's data — not through retrieval, not through a tool, not through a shared
cache. This package makes that property **structural** rather than a runtime check you can
forget:

* :class:`Session` — the authenticated principal: who is asking, in which tenant. Every tool
  and retrieval call is scoped to it; there is no privileged service identity anywhere in the
  request path (PLAN.md → "tools are scoped to the signed-in user's session").
* :class:`TenantStores` — one isolated retrieval index **per tenant**, so a query physically
  cannot reach another tenant's vectors. Isolation by construction beats isolation by ``WHERE``
  clause.

See :mod:`tenancy.scope`.
"""

from __future__ import annotations

from .scope import (
    Session,
    TenantStores,
    new_session,
    tenant_cache_label,
)

__all__ = [
    "Session",
    "TenantStores",
    "new_session",
    "tenant_cache_label",
]
__version__ = "0.1.0"
