"""Per-user + per-tenant scope — isolation by construction (Ch 41/43).

A customer-facing copilot serves many tenants from one deployment. The catastrophic failure
mode is **cross-tenant leakage**: tenant A's question surfaces tenant B's invoice, document, or
account. The PLAN is explicit that scoping must hold on *both* retrieval and tools, and that a
mis-scoped cache is just as dangerous as a mis-scoped query.

This module makes isolation **structural**, so it cannot be forgotten:

1. **Retrieval** — each tenant gets its **own** :class:`~rag_pipeline.InMemoryVectorStore`. A
   query embedded for tenant ``acme`` is searched only against ``acme``'s index, because the
   other tenant's vectors are not in the same store at all. There is no shared collection and
   therefore no ``WHERE tenant = ?`` to get wrong. (A production swap to Chroma/Pinecone keeps
   the shape: one namespace/collection per tenant, selected here, not filtered after the fact.)
2. **Tools** — a :class:`Session` carries the authenticated ``user_id`` + ``tenant_id``. The
   session tools (see ``app.session_tools``) take a ``Session`` and read/write **only** that
   tenant's records. No tool ever runs under a privileged service identity.
3. **Cache** — the gateway cache key is salted per *(tenant, user)* via
   :func:`tenant_cache_label`, so one user's cached answer can never be served to another — the
   subtle leak the PLAN warns about.

Nothing here calls a model or the network: scope resolution is a pure, synchronous decision so
it is cheap and *always on*.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Sequence

from . import _patch_path  # noqa: F401  (side effect: pattern blueprints on sys.path)

from rag_pipeline import (  # type: ignore  # noqa: E402
    Document,
    EmbeddedChunk,
    HybridRetriever,
    InMemoryVectorStore,
    RetrievalResult,
    chunk_documents,
    embed_chunks,
)


@dataclass(frozen=True)
class Session:
    """The authenticated principal for one in-app request.

    There is exactly one identity in the request path and this is it. ``tenant_id`` selects the
    isolated retrieval index and the tool sandbox; ``user_id`` scopes the cache and attributes
    cost/abuse signals. ``plan`` lets per-user limits differ by subscription tier (a free-tier
    user gets a tighter budget than an enterprise seat) — margin engineering *is* product
    engineering here (PLAN.md → "treat cost per user per month as a hard product budget").

    A real deployment builds this from a verified session token / SSO claim on the request, the
    same way ``internal-knowledge-assistant`` builds its ``Principal`` from IdP groups. **Keep
    the contract, replace the source** — never trust a tenant id the client merely *claims*.
    """

    user_id: str
    tenant_id: str
    display_name: str = ""
    plan: str = "free"

    def __post_init__(self) -> None:
        if not self.user_id:
            raise ValueError("Session.user_id must be a non-empty string")
        if not self.tenant_id:
            raise ValueError("Session.tenant_id must be a non-empty string")

    @property
    def label(self) -> str:
        """A stable ``tenant/user`` attribution label for metering, tracing, and the cache."""
        return tenant_cache_label(self.tenant_id, self.user_id)


def new_session(
    user_id: str, tenant_id: str, *, display_name: str = "", plan: str = "free"
) -> Session:
    """Construct a :class:`Session` (thin helper so callers don't import the dataclass)."""
    return Session(
        user_id=user_id, tenant_id=tenant_id, display_name=display_name, plan=plan
    )


def tenant_cache_label(tenant_id: str, user_id: str) -> str:
    """The per-*(tenant, user)* salt used as the gateway cache label.

    The gateway's cache key already covers the prompt; this label is what keeps two *different*
    users' caches apart even when they ask the identical question. Because retrieved evidence is
    woven into each user's prompt (their own scoped data), their prompts already differ — but
    salting the label is the belt-and-suspenders that makes a cross-user cache hit impossible by
    construction, not by luck.
    """
    return f"{tenant_id}/{user_id}"


class TenantStores:
    """A registry of **isolated, per-tenant** retrieval indexes.

    The isolation guarantee lives here: :meth:`retriever_for` only ever returns a retriever bound
    to *one* tenant's store, and there is no API that searches across tenants. Ingesting tenant
    ``acme``'s docs into ``acme``'s store leaves every other tenant's index untouched — so a
    leak would require constructing a query against the *wrong* store on purpose, not merely
    forgetting a filter.

    Backed by the ``rag-pipeline`` blueprint's in-memory store (deterministic, offline, $0). The
    same shape holds for a real backend: swap :class:`~rag_pipeline.InMemoryVectorStore` for a
    Chroma collection or a Pinecone namespace *named for the tenant*, and nothing above changes.
    """

    def __init__(self) -> None:
        self._stores: dict[str, InMemoryVectorStore] = {}

    def _store(self, tenant_id: str) -> InMemoryVectorStore:
        store = self._stores.get(tenant_id)
        if store is None:
            store = InMemoryVectorStore()
            self._stores[tenant_id] = store
        return store

    def ingest(self, tenant_id: str, documents: Sequence[Document]) -> int:
        """Chunk → embed → upsert ``documents`` into **only** ``tenant_id``'s index.

        Returns the number of chunks added. Re-ingesting the same docs is idempotent (chunk ids
        are stable), so this is safe to call on every startup.
        """
        if not tenant_id:
            raise ValueError("tenant_id must be a non-empty string")
        chunks = chunk_documents(list(documents))
        embedded: list[EmbeddedChunk] = embed_chunks(chunks)
        self._store(tenant_id).add(embedded)
        return len(embedded)

    def retriever_for(self, tenant_id: str) -> HybridRetriever:
        """A :class:`~rag_pipeline.HybridRetriever` bound to **one** tenant's store.

        This is the only door to retrieval, and it is single-tenant by type: the returned
        retriever physically cannot see another tenant's vectors.
        """
        if not tenant_id:
            raise ValueError("tenant_id must be a non-empty string")
        return HybridRetriever(self._store(tenant_id))

    def retrieve(
        self, session: Session, query: str, *, k: int = 4
    ) -> list[RetrievalResult]:
        """Retrieve the top-``k`` chunks for ``query`` **within the session's tenant**.

        The session — not a caller-supplied string — chooses the index, so a request can never
        widen its own scope. An unknown tenant simply has an empty store and returns ``[]``.
        """
        return self.retriever_for(session.tenant_id).retrieve(query, k=k)

    def tenant_ids(self) -> list[str]:
        """The tenants that have been ingested (for the demo's tenant picker)."""
        return sorted(self._stores)

    def size(self, tenant_id: str) -> int:
        """Number of chunks stored for one tenant (0 if never ingested)."""
        store = self._stores.get(tenant_id)
        return len(store) if store is not None else 0
