"""Structured NL -> SQL generation, grounded by retrieval over the semantic layer (Ch 13, 15).

This is the *generate* stage of the copilot. A real deployment asks an LLM (through the
``llm-gateway``) for structured SQL constrained to the schema; here, by default, a deterministic
**mock planner** produces the same SQL with **zero API spend**, so the demo and evals are free and
reproducible. Either way the shape is the senior one:

1. **Retrieve, don't dump.** Rather than pasting the whole schema into the prompt, we index the
   semantic layer's table/column/metric docs in the **rag-pipeline** (``HybridRetriever`` +
   ``MockReranker``) and retrieve only the elements a question is *about*. That is the Ch 13
   contribution to text-to-SQL: language maps to the *right* tables, joins, and metric expressions.
2. **Generate against a pinned vocabulary.** The model never invents an aggregation for "revenue";
   it reuses the metric's canonical SQL from the semantic layer, so numbers stay refund-correct and
   consistent across questions.
3. **Return a typed plan**, not a bare string — the metric, dimensions, filters, and the SQL — so
   verify.py and the "show me the SQL" affordance have something structured to inspect.

The live path swaps the mock planner for an ``llm-gateway`` call behind the same
:class:`SqlGenerator` surface; nothing downstream changes. The mock is wired to the *same*
retrieved context the LLM would see, so the demo honestly exercises the retrieval grounding.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field

from . import _compose  # noqa: F401  (wires the pattern blueprints onto sys.path)
from .semantic import Dimension, Metric, SemanticLayer, load_semantic_layer

# Composed pattern blueprint: rag-pipeline (chunk omitted — schema docs are already chunk-sized).
from rag_pipeline import (  # noqa: E402  (after _compose puts it on sys.path)
    Document,
    HybridRetriever,
    InMemoryVectorStore,
    MockReranker,
    chunk_documents,
    embed_chunks,
)

MOCK = os.getenv("COMPANION_MOCK", "1") != "0"


@dataclass(frozen=True)
class SqlPlan:
    """A structured query plan — what the copilot decided to run, and why.

    Carrying the resolved ``metric`` / ``dimensions`` / ``filters`` (not just the final ``sql``)
    is what makes the plan auditable: verify.py checks it, the eval-harness grades it, and the
    "show me the SQL" affordance renders it for the human.
    """

    question: str
    sql: str
    metric: str
    dimensions: tuple[str, ...] = ()
    filters: tuple[str, ...] = ()
    tables: tuple[str, ...] = ()
    retrieved: tuple[str, ...] = ()  # doc ids the retriever surfaced (the grounding evidence)
    rationale: str = ""


class SemanticIndex:
    """The rag-pipeline indexing the semantic layer — retrieval over schema/metric docs.

    Composes ``rag-pipeline`` directly: ingest the semantic layer's ``schema_docs`` as a tiny
    corpus, then hybrid-retrieve + rerank the elements relevant to a question. This is the Ch 13
    grounding that keeps language mapped to the right tables/joins/metrics instead of dumping the
    whole schema into a prompt.
    """

    def __init__(self, layer: SemanticLayer) -> None:
        self.layer = layer
        self.store = InMemoryVectorStore()
        docs = [Document(id=doc_id, text=text) for doc_id, text in layer.schema_docs()]
        # Schema docs are already short; one chunk each keeps doc ids == retrieval ids.
        chunks = chunk_documents(docs, chunk_size=200, overlap=0)
        self.store.add(embed_chunks(chunks))
        self.retriever = HybridRetriever(self.store)
        self.reranker = MockReranker()

    def retrieve(self, question: str, *, k: int = 5) -> list[str]:
        """Return the doc ids most relevant to ``question`` (rerank-ordered)."""
        hits = self.retriever.retrieve(question, k=k)
        reranked = self.reranker.rerank(question, hits)
        return [s.chunk.doc_id for s in reranked]


class SqlGenerator:
    """NL -> SqlPlan, grounded on the semantic layer and its retrieval index.

    Construct once with a :class:`SemanticLayer`; call :meth:`generate` per question. In MOCK
    mode a deterministic planner maps the question to a metric + dimensions + filters using the
    layer's synonyms and the retrieved context. The live path replaces only the planner.
    """

    def __init__(self, layer: SemanticLayer | None = None, *, row_limit: int = 1000) -> None:
        self.layer = layer or load_semantic_layer()
        self.index = SemanticIndex(self.layer)
        self.row_limit = row_limit

    def generate(self, question: str) -> SqlPlan:
        retrieved = self.index.retrieve(question, k=5)
        if MOCK:
            return self._mock_plan(question, retrieved)
        return self._live_plan(question, retrieved)

    # -- the mock planner (free, deterministic) ------------------------------------
    def _mock_plan(self, question: str, retrieved: list[str]) -> SqlPlan:
        q = question.lower()
        metric = self._match_metric(q, retrieved)
        dimensions = self._match_dimensions(q)
        filters = self._match_filters(q)
        sql = self._assemble_sql(metric, dimensions, filters)
        rationale = (
            f"metric={metric.name}; "
            f"dims={[d.name for d in dimensions]}; "
            f"filters={list(filters)}; grounded_on={retrieved[:3]}"
        )
        return SqlPlan(
            question=question,
            sql=sql,
            metric=metric.name,
            dimensions=tuple(d.name for d in dimensions),
            filters=tuple(filters),
            tables=self._tables_for(metric, dimensions, filters),
            retrieved=tuple(retrieved),
            rationale=rationale,
        )

    def _live_plan(self, question: str, retrieved: list[str]) -> SqlPlan:
        """Live path: ask an LLM (via ``llm-gateway``) for structured SQL over the retrieved schema.

        Not vendored here (no keys, no spend by default). Wire an ``llm-gateway`` client and have
        it return the same :class:`SqlPlan` shape, prompted with ``self.index.retrieve(...)`` as
        the grounded context. The mock above documents exactly what that output must look like.
        """
        raise RuntimeError(
            "COMPANION_MOCK=0 requested live generation, but no llm-gateway client is wired in. "
            "Inject one in _live_plan (see README -> Live path) or run with COMPANION_MOCK=1."
        )

    # -- matching helpers (synonym-driven, semantic-layer-grounded) ----------------
    def _match_metric(self, q: str, retrieved: list[str]) -> Metric:
        # Prefer a metric the retriever surfaced (retrieval grounding wins), then synonyms.
        for doc_id in retrieved:
            if doc_id.startswith("metric:"):
                m = self.layer.metric(doc_id.split(":", 1)[1])
                if m is not None and self._mentions(q, m.synonyms):
                    return m
        for m in self.layer.metrics:
            if self._mentions(q, m.synonyms):
                return m
        # Default to the first metric (revenue) so a vague question still produces a plan.
        return self.layer.metrics[0]

    def _match_dimensions(self, q: str) -> list[Dimension]:
        dims: list[Dimension] = []
        for d in self.layer.dimensions:
            if self._mentions(q, d.synonyms):
                dims.append(d)
        return dims

    def _match_filters(self, q: str) -> list[str]:
        """Extract simple, safe equality filters from the question via semantic-layer values."""
        filters: list[str] = []
        # Region literals declared in the customers.region docs.
        for region in ("AMER", "EMEA", "APAC"):
            if region.lower() in q:
                filters.append(f"customers.region = '{region}'")
        for plan in ("free", "pro", "enterprise"):
            if re.search(rf"\b{plan}\b", q):
                filters.append(f"customers.plan = '{plan}'")
        return filters

    def _tables_for(
        self, metric: Metric, dimensions: list[Dimension], filters: tuple[str, ...]
    ) -> tuple[str, ...]:
        tables: list[str] = list(metric.requires_tables)
        text = " ".join(d.sql() for d in dimensions) + " " + " ".join(filters)
        for t in self.layer.known_tables():
            if f"{t}." in text and t not in tables:
                tables.append(t)
        return tuple(tables)

    def _assemble_sql(self, metric: Metric, dimensions: list[Dimension], filters: list[str]) -> str:
        select_dims = [f"{d.sql()} AS {d.name}" for d in dimensions]
        select = ", ".join(select_dims + [f"{metric.expression} AS {metric.name}"])
        from_clause, used_tables = self._from_clause(metric, dimensions, filters)
        where = f"\nWHERE {' AND '.join(filters)}" if filters else ""
        group = (
            "\nGROUP BY " + ", ".join(d.sql() for d in dimensions) if dimensions else ""
        )
        order = f"\nORDER BY {metric.name} DESC" if dimensions else ""
        limit = f"\nLIMIT {self.row_limit}"
        return f"SELECT {select}\nFROM {from_clause}{where}{group}{order}{limit}"

    def _from_clause(
        self, metric: Metric, dimensions: list[Dimension], filters: list[str]
    ) -> tuple[str, set[str]]:
        used = set(metric.requires_tables)
        text = " ".join(d.sql() for d in dimensions) + " " + " ".join(filters)
        for t in self.layer.known_tables():
            if f"{t}." in text:
                used.add(t)
        if used == {"orders"} or "orders" in used and len(used) == 1:
            return "orders", used
        if used == {"customers"}:
            return "customers", used
        # Join orders <-> customers on the canonical key (the only join in this warehouse).
        if "orders" in used and "customers" in used:
            return (
                "orders\nJOIN customers ON orders.customer_id = customers.customer_id",
                used,
            )
        only = next(iter(used)) if used else "orders"
        return only, used

    @staticmethod
    def _mentions(text: str, synonyms: tuple[str, ...]) -> bool:
        return any(s.lower() in text for s in synonyms)


def generate_sql(question: str, layer: SemanticLayer | None = None) -> SqlPlan:
    """One-call convenience: question -> :class:`SqlPlan` (used by the demo and evals)."""
    return SqlGenerator(layer).generate(question)
