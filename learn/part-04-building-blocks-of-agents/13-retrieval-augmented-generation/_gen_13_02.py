"""Generator for 13-02-grounded-answer-with-citations.ipynb (run once, then delete)."""
import json, os

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "13-02-grounded-answer-with-citations.ipynb")


def md(text):
    return {"cell_type": "markdown", "metadata": {}, "source": _split(text)}


def code(text):
    return {"cell_type": "code", "execution_count": None, "metadata": {},
            "outputs": [], "source": _split(text)}


def _split(text):
    lines = text.split("\n")
    out = [ln + "\n" for ln in lines[:-1]]
    if lines[-1] != "":
        out.append(lines[-1])
    return out


cells = []

cells.append(md(
"""# \U0001F527 Build: grounded answers with numbered citations

> \U0001F4D3 *Companion to* **Modern Agentic AI Engineer** *· Ch 13 §13.8 (Build) · type: walkthrough*

This is the chapter's **\U0001F527 Build** — the capstone's `rag/` retrieval + answer layer.
Wrap retrieval behind a `Retriever` protocol, index documents into Chroma, and generate an
answer that **cites numbered sources** and **declines** when the sources don't cover the question."""
))

cells.append(md(
"""## \U0001F9E0 Why this matters

The store you pick (Chroma, pgvector, Pinecone) is *not* your architecture — every option does
filtered cosine search fine at the scale most products reach. The architectural decision is the
seam: **agents and API routes depend on a `Retriever` interface, never on Chroma directly.** Put
that interface in now and the Part VIII swap to Pinecone is a config change, not a rewrite. The
other load-bearing piece is one sentence of system prompt: *grounding plus an explicit license to
say "not in the sources"* is the cheapest hallucination defense you will ever deploy."""
))

cells.append(md(
"""## Objectives & prereqs

**By the end you can:**
- Define the `Hit` dataclass and a `Retriever` **Protocol** — the swappable seam.
- Build a `ChromaRetriever` that indexes pre-chunked docs with `source`/`tags` metadata and
  searches with a `where` filter (metadata filtering as access control).
- Assemble numbered context and generate a **grounded, cited** answer.
- Watch the model **decline** on an out-of-corpus question — and watch invention return when
  you drop the "say so if not in the sources" line.

**Prereqs:** Notebook 13-01 (the retrieval stages); Ch 12 tool-loop (retrieval becomes a tool
in §13.6). `chromadb` and `sentence-transformers` are used live; both are gated behind `MOCK`,
which defaults the whole notebook to an in-memory store and a canned model response."""
))

cells.append(code(
'''# --- Setup -------------------------------------------------------------------
import os
import json
from pathlib import Path
from dataclasses import dataclass
from typing import Protocol

from dotenv import load_dotenv

load_dotenv()  # read ANTHROPIC_API_KEY (etc.) from .env if present; never hardcode

# MOCK=1 (default): in-memory retriever + canned generation -> FREE, OFFLINE, no key.
# MOCK=0: real Chroma (persistent) + real Anthropic generation.
#   Live generation cost: ~1-2 short messages (a few hundred tokens) per answer.
MOCK = os.getenv("COMPANION_MOCK", "1") == "1"

MODEL = "claude-sonnet-4-5"  # book's default for grounded answering; cheap + capable
DATA = Path("data")

print(f"MOCK mode: {MOCK}")
if not MOCK and not os.getenv("ANTHROPIC_API_KEY"):
    raise SystemExit("MOCK=0 requires ANTHROPIC_API_KEY in your environment (.env).")
print(f"Model (live mode): {MODEL}")'''
))

cells.append(md(
"""## 1. The seam: `Hit` and the `Retriever` protocol

This is the exact shape from §13.8. Everything downstream — agents, API routes, the
capstone — depends on `Retriever`, not on any concrete store. That is the whole point."""
))

cells.append(code(
'''@dataclass
class Hit:
    text: str
    source: str
    score: float


class Retriever(Protocol):
    def search(self, query: str, k: int = 6,
               where: dict | None = None) -> list[Hit]: ...'''
))

cells.append(md(
"""## 2. Load the pre-chunked corpus

We reuse 13-01's corpus, already shaped as `{id, text, source, tags}` — the form `index()`
expects. In a real system this is the output of your parse → chunk stage."""
))

cells.append(code(
'''docs = [json.loads(line) for line in (DATA / "corpus.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
print(f"{len(docs)} pre-chunked docs")
for d in docs[:2]:
    print(f"  {d['id']:<12} tags={d['tags']} :: {d['text'][:60]!r}")'''
))

cells.append(md(
"""## 3. Build the retriever

The book's `ChromaRetriever` uses a persistent client, cosine space, local
`bge-small-en-v1.5` embeddings, and a `where` filter for access control. To keep this
notebook free and offline by default, `MOCK=1` provides an `InMemoryRetriever` with the
**identical interface and identical Chroma-style `where` semantics** — so the rest of the
notebook is store-agnostic, exactly as production should be. `MOCK=0` runs the real Chroma code."""
))

cells.append(code(
'''import math


def _normalize(v):
    n = math.sqrt(sum(x * x for x in v)) or 1.0
    return [x / n for x in v]


def _mock_embed(texts):
    """Deterministic offline embedding (bag-of-words hash), matches 13-01."""
    DIM = 256
    out = []
    for t in texts:
        v = [0.0] * DIM
        for tok in t.lower().replace("\\n", " ").split():
            tok = tok.strip(".,:;!?()[]\\"'")
            if tok:
                v[hash(("salt", tok)) % DIM] += 1.0
        out.append(_normalize(v))
    return out


def _matches_where(meta, where):
    """Subset of Chroma's where semantics: equality and $in / $nin on metadata."""
    if not where:
        return True
    for key, cond in where.items():
        val = meta.get(key)
        if isinstance(cond, dict):
            if "$in" in cond and val not in cond["$in"]:
                return False
            if "$nin" in cond and val in cond["$nin"]:
                return False
        elif val != cond:
            return False
    return True


class InMemoryRetriever:
    """MOCK Retriever with Chroma-compatible interface. Offline + free."""

    def __init__(self):
        self._docs = []

    def index(self, docs: list[dict]) -> None:
        for d in docs:
            tag = d["tags"][0] if d.get("tags") else ""
            self._docs.append({
                "text": d["text"], "source": d["source"],
                "tag": tag, "vec": _mock_embed([d["text"]])[0],
            })

    def search(self, query: str, k: int = 6, where: dict | None = None) -> list[Hit]:
        q = _mock_embed([query])[0]
        scored = []
        for d in self._docs:
            if not _matches_where({"source": d["source"], "tag": d["tag"]}, where):
                continue
            score = sum(a * b for a, b in zip(q, d["vec"]))  # cosine
            scored.append(Hit(text=d["text"], source=d["source"], score=score))
        scored.sort(key=lambda h: h.score, reverse=True)
        return scored[:k]'''
))

cells.append(code(
'''# The real book code (runs when MOCK=0). Shown here so the shape is visible either way.
class ChromaRetriever:
    """Book §13.8. Persistent Chroma, cosine space, local bge-small embeddings."""

    def __init__(self, path: str = "./chroma"):
        import chromadb
        from sentence_transformers import SentenceTransformer
        self._embedder = SentenceTransformer("BAAI/bge-small-en-v1.5")
        self.col = chromadb.PersistentClient(path).get_or_create_collection(
            "capstone_docs", metadata={"hnsw:space": "cosine"}
        )

    def _embed(self, texts):
        return self._embedder.encode(texts, normalize_embeddings=True).tolist()

    def index(self, docs: list[dict]) -> None:
        """docs: [{'id','text','source','tags'}, ...] -- pre-chunked."""
        self.col.upsert(
            ids=[d["id"] for d in docs],
            documents=[d["text"] for d in docs],
            embeddings=self._embed([d["text"] for d in docs]),
            metadatas=[{"source": d["source"], "tag": d["tags"][0]} for d in docs],
        )

    def search(self, query: str, k: int = 6, where: dict | None = None) -> list[Hit]:
        res = self.col.query(query_embeddings=self._embed([query]),
                             n_results=k, where=where)
        return [Hit(text=t, source=m["source"], score=1 - dist)
                for t, m, dist in zip(res["documents"][0], res["metadatas"][0],
                                      res["distances"][0])]


retriever: Retriever = InMemoryRetriever() if MOCK else ChromaRetriever()
retriever.index(docs)
print(f"Indexed {len(docs)} docs into {type(retriever).__name__}")

for h in retriever.search("how long do refunds take?", k=3):
    print(f"  {h.score:.3f}  ({h.source})  {h.text[:60]!r}")'''
))

cells.append(md(
"""## 4. Metadata filtering = access control

Retrieval happens in *your* code, so you can filter what a user is allowed to see **before**
the model ever sees it — something fine-tuning can never offer. Our corpus has a
`restricted` security runbook tagged `internal`. A `where` clause excludes it for an external
user. Use a query that would otherwise surface it."""
))

cells.append(code(
'''leaky_q = "what do I do if an API key leaks?"

print("WITHOUT filter (internal docs reachable):")
for h in retriever.search(leaky_q, k=3):
    flag = "  <-- RESTRICTED" if "security-runbook" in h.source else ""
    print(f"  ({h.source})  {h.text[:55]!r}{flag}")

print("\\nWITH access-control filter (exclude internal-only docs):")
public_only = {"tag": {"$nin": ["security", "internal", "restricted", "catalog"]}}
for h in retriever.search(leaky_q, k=3, where=public_only):
    print(f"  ({h.source})  {h.text[:55]!r}")'''
))

cells.append(md(
"""## 5. Grounded generation with numbered citations

Assemble the retrieved hits into numbered context `[1] (source)\\n…`, then call the model with
the book's grounding system prompt. The `answer()` shape matches §13.8 exactly. In `MOCK` mode
the model call is replaced by a deterministic canned responder that *only* uses the supplied
sources and cites them — the same contract the real model is held to."""
))

cells.append(code(
'''GROUNDING_SYSTEM = (
    "Answer using ONLY the numbered sources provided. Cite "
    "sources like [2] after each claim. If the sources do not "
    "contain the answer, say so explicitly -- do not guess."
)


def _build_context(hits: list[Hit]) -> str:
    return "\\n\\n".join(f"[{i+1}] ({h.source})\\n{h.text}" for i, h in enumerate(hits))


def _mock_generate(system: str, question: str, hits: list[Hit]) -> str:
    """Canned, grounded responder: keyword-overlap pick, cite, or decline. Deterministic."""
    qtoks = {w.strip(".,:;!?") for w in question.lower().split() if len(w) > 3}
    best_i, best_overlap = -1, 0
    for i, h in enumerate(hits):
        overlap = len(qtoks & {w.strip(".,:;!?") for w in h.text.lower().split()})
        if overlap > best_overlap:
            best_i, best_overlap = i, overlap
    # Decline only when the prompt licenses it AND nothing overlaps.
    can_decline = "do not contain the answer" in system or "say so" in system
    if best_overlap < 2:
        if can_decline:
            return "The provided sources do not contain the answer to this question."
        # Without the decline license: invent a confident, uncited answer (the pitfall).
        return "Yes -- this is generally supported and should work as expected."
    h = hits[best_i]
    snippet = h.text.split(". ")[0]
    return f"{snippet}. [{best_i + 1}]"


def answer(question: str, retriever: Retriever, k: int = 6,
           system: str = GROUNDING_SYSTEM, where: dict | None = None) -> str:
    hits = retriever.search(question, k=k, where=where)
    context = _build_context(hits)
    if MOCK:
        return _mock_generate(system, question, hits)
    from anthropic import Anthropic
    client = Anthropic()
    resp = client.messages.create(
        model=MODEL, max_tokens=1024, system=system,
        messages=[{"role": "user",
                   "content": f"Sources:\\n{context}\\n\\nQuestion: {question}"}],
    )
    return next((b.text for b in resp.content if b.type == "text"), "")


print(answer("How long do I have to refund a domestic order?", retriever))'''
))

cells.append(md(
"""## \U0001F52E Predict before you run

The next question — **"What is your CEO's home address?"** — is *not* covered anywhere in the
corpus.

**Predict:** with the grounding system prompt (which explicitly licenses "say so if not in the
sources"), will the model **invent** an answer or **decline**? Then run the cell."""
))

cells.append(code(
'''out_of_corpus = "What is your CEO's home address?"
print("WITH grounding prompt (decline licensed):")
print("  ->", answer(out_of_corpus, retriever))'''
))

cells.append(md(
"""## ⚠️ Pitfall: drop the decline license and invention returns

The last sentence of the system prompt — *"if the sources do not contain the answer, say so
explicitly"* — is load-bearing. Remove it and the model treats answering as mandatory and fills
the retrieval gap with fluent, confident invention. **The cheapest hallucination defense you
will ever deploy is one line of system prompt.**"""
))

cells.append(code(
'''NO_DECLINE_SYSTEM = (
    "Answer using ONLY the numbered sources provided. Cite "
    "sources like [2] after each claim."
)  # <-- the 'say so if not in the sources' sentence is GONE

print("WITHOUT the decline license (same out-of-corpus question):")
print("  ->", answer(out_of_corpus, retriever, system=NO_DECLINE_SYSTEM))
print("\\nSame retrieval, opposite behavior. The fix cost one sentence.")'''
))

cells.append(md(
"""## \U0001F3AF Senior lens

The store choice reduces to one question: **another stateful system, or not?** If your data is
already in Postgres, `pgvector` means no new backup story, no new auth story, no sync pipeline
keeping two stores consistent — it's the pragmatic production default. Chroma is the zero-ops
*dev* default. You reach for a dedicated store (Pinecone, Qdrant) only when measured scale or
latency demands it.

Because everything depends on the `Retriever` protocol and never on Chroma directly, that
decision stays a **deployment detail, not a rewrite**. Interface first; swap later."""
))

cells.append(md(
"""## Recap

- The `Retriever` **protocol** is the seam: depend on the interface, never the concrete store.
- `ChromaRetriever` (persistent, cosine, local `bge-small` embeddings) indexes
  `{id,text,source,tags}` and searches with a `where` filter.
- **Metadata filtering is access control** applied *before* the model sees anything.
- Grounded generation = numbered context + a system prompt that demands citations and
  **licenses declining**.
- Dropping the "say so if not in the sources" sentence brings confident invention straight back."""
))

cells.append(md(
"""## Exercises

1. **Tighten access control.** Add a `where` filter that restricts to `tag == "billing"` and
   confirm the API-error chunks vanish from results. Predict which questions now fail to answer.
2. **Citation discipline.** Modify `_build_context` to omit the `(source)` line. Predict how the
   cited answer degrades — can a reader still verify a claim?
3. **Decline boundary.** Find a question the corpus *partially* covers and decide whether the
   model should answer, partially answer, or decline. Tune the overlap threshold (or, in
   `MOCK=0`, the prompt) to match your judgment.
4. **Live mode (optional).** Set `COMPANION_MOCK=0` with `ANTHROPIC_API_KEY` and `chromadb`
   installed. Does the real model decline on the out-of-corpus question? Does it still cite?"""
))

cells.append(code('''# Exercise 1: tag-restricted where filter
'''))
cells.append(code('''# Exercise 2: drop the (source) line and inspect the answer
'''))
cells.append(code('''# Exercise 3: partial-coverage question + threshold tuning
'''))
cells.append(code('''# Exercise 4 (optional): COMPANION_MOCK=0 live grounded answer
'''))

cells.append(md(
"""## Next

You stood up a swappable retriever and produced grounded, citable answers with an explicit
"I don't know." Next, **Notebook 13-03** *measures* this system on a golden set — because RAG
quality is decided by retrieval, and retrieval is only as good as your evals.

- Next notebook: [`13-03-rag-eval-golden-set.ipynb`](./13-03-rag-eval-golden-set.ipynb)
- Production version (hybrid + rerank + query transform + caching): [`blueprints/rag-pipeline/`](../../../blueprints/rag-pipeline/)
- Capstone module this builds: [`capstone/rag/`](../../../capstone/rag/) (the `Retriever`
  protocol, `ChromaRetriever`, and the cited `answer()`)"""
))

nb = {"cells": cells,
      "metadata": {"kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
                   "language_info": {"name": "python"}},
      "nbformat": 4, "nbformat_minor": 5}

with open(OUT, "w", encoding="utf-8") as f:
    json.dump(nb, f, ensure_ascii=False, indent=1)
print("wrote", OUT)
