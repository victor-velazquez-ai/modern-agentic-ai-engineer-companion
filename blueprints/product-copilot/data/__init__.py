"""Sample dataset loader — shared product docs + two isolated mock tenants.

The demo and evals need a tiny, committed corpus that makes **multi-tenant isolation visible**.
The shape:

* ``data/product_docs/shared-*.md`` — ~6 snippets of the (fictional) **Nimbus** product's public
  help center. These are shared across *every* tenant: any signed-in user may see them.
* ``data/tenants/<tenant>/*.md`` — each tenant's **private** runbook, carrying a tenant-specific
  secret (a warehouse name, an escalation code phrase). If tenant *globex*'s query ever surfaces
  *acme*'s code phrase, isolation is broken — which is exactly what the demo proves cannot happen,
  because each tenant is ingested into its **own** ``rag_pipeline`` store via
  :class:`~tenancy.TenantStores`.

This module returns the docs as ``rag_pipeline.Document`` objects (composing the pattern
blueprint, not forking it) and provides the per-user account/order fixtures the session tools
read. No model, no network — just file reads, so it runs offline and deterministically.
"""

from __future__ import annotations

from pathlib import Path

import sys

# Make the blueprint root importable so ``import app`` / ``import tenancy`` resolve regardless of
# how this module is reached, then wire the pattern blueprints onto sys.path via app._compose.
_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import app._compose  # noqa: F401,E402  (side effect: pattern blueprints on sys.path)

from rag_pipeline import Document  # type: ignore  # noqa: E402

# The two demo tenants. Real tenant ids come from your IdP / billing system; these are fixtures.
TENANTS = ("acme", "globex")

_DATA_DIR = Path(__file__).resolve().parent
_SHARED_DIR = _DATA_DIR / "product_docs"
_TENANTS_DIR = _DATA_DIR / "tenants"

# Shared docs are tagged with this sentinel so every tenant's index includes them. It matches
# the ``SHARED_TENANT`` convention documented in tenancy/scope.py.
SHARED_TENANT = "_shared"


def _load_markdown(path: Path) -> str:
    return path.read_text(encoding="utf-8").strip()


def shared_documents() -> list[Document]:
    """The product's public help-center snippets, visible to every tenant."""
    docs: list[Document] = []
    for md in sorted(_SHARED_DIR.glob("*.md")):
        text = _load_markdown(md)
        title = text.splitlines()[0].lstrip("# ").strip() if text else md.stem
        docs.append(
            Document(
                id=md.stem,
                text=text,
                metadata={
                    "title": title,
                    "tenant_id": SHARED_TENANT,
                    "visibility": "public",
                    "source": "product_docs",
                },
            )
        )
    return docs


def tenant_documents(tenant_id: str) -> list[Document]:
    """One tenant's **private** documents (its runbook). Empty for an unknown tenant."""
    tenant_dir = _TENANTS_DIR / tenant_id
    if not tenant_dir.is_dir():
        return []
    docs: list[Document] = []
    for md in sorted(tenant_dir.glob("*.md")):
        text = _load_markdown(md)
        title = text.splitlines()[0].lstrip("# ").strip() if text else md.stem
        docs.append(
            Document(
                id=md.stem,
                text=text,
                metadata={
                    "title": title,
                    "tenant_id": tenant_id,
                    "visibility": "tenant",
                    "source": "tenant_private",
                },
            )
        )
    return docs


def documents_for(tenant_id: str) -> list[Document]:
    """Everything a tenant's index should contain: shared product docs + that tenant's private docs.

    Crucially this returns *only* ``tenant_id``'s private docs (plus the shared set) — never
    another tenant's. Ingest the result into that tenant's isolated store and the isolation holds
    by construction.
    """
    return shared_documents() + tenant_documents(tenant_id)


# ---------------------------------------------------------------------------
# Per-user fixtures for the session tools (orders + account), keyed by (tenant, user).
# ---------------------------------------------------------------------------

# Each entry: (tenant_id, user_id) -> {"account": {...}, "orders": [{...}, ...]}
USER_FIXTURES: dict[tuple[str, str], dict] = {
    ("acme", "alice"): {
        "account": {"plan": "team", "seats": 12, "notifications": True},
        "orders": [
            {"order_id": "A-1001", "status": "shipped", "total_usd": 240.00},
            {"order_id": "A-1002", "status": "processing", "total_usd": 60.00},
        ],
    },
    ("globex", "bob"): {
        "account": {"plan": "enterprise", "seats": 80, "notifications": False},
        "orders": [
            {"order_id": "G-7001", "status": "delivered", "total_usd": 1500.00},
        ],
    },
}


__all__ = [
    "TENANTS",
    "SHARED_TENANT",
    "shared_documents",
    "tenant_documents",
    "documents_for",
    "USER_FIXTURES",
]
