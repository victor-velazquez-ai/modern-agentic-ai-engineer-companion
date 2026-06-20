"""Generator for 13-01-chunk-embed-retrieve-rerank.ipynb (run once, then delete)."""
import json, os

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "13-01-chunk-embed-retrieve-rerank.ipynb")


def md(text):
    return {"cell_type": "markdown", "metadata": {}, "source": _split(text)}


def code(text):
    return {"cell_type": "code", "execution_count": None, "metadata": {},
            "outputs": [], "source": _split(text)}


def _split(text):
    # Preserve trailing newlines on every line except the last (nbformat list-of-lines).
    lines = text.split("\n")
    out = [ln + "\n" for ln in lines[:-1]]
    if lines[-1] != "":
        out.append(lines[-1])
    return out


cells = []

cells.append(md(
"""# RAG, end to end: chunk -> embed -> retrieve -> rerank

> \U0001F4D3 *Companion to* **Modern Agentic AI Engineer** *· Ch 13 §13.2–13.5 · type: walkthrough*

Build a working retriever from raw text and *see* each stage change which evidence
reaches the model: parse the document, chunk it, embed the chunks, run vector search,
fuse with BM25, then rerank with a cross-encoder."""
))

cells.append(md(
"""## \U0001F9E0 Why this matters

A RAG system has two halves. The **left half runs offline**: you parse documents, split
them into chunks, and embed those chunks into a vector index. The **right half runs online**:
you embed the user's query, find the nearest chunks, and hand them to the model. The model
only ever sees what retrieval hands it — so **most quality problems live on the left half
and in the retrieval step, not in the model**. This notebook walks that pipeline one stage
at a time so you can watch *which evidence* reaches the model change as you improve each stage."""
))

cells.append(md(
"""## Objectives & prereqs

**By the end you can:**
- Run the book's paragraph-aware `chunk()` and read a *sample* of the actual chunks.
- Embed chunks and a query locally, rank by cosine similarity (a normalized dot product).
- Add BM25 keyword scoring and fuse the two lists with **reciprocal rank fusion (RRF)**.
- Stage a **cross-encoder reranker** over the candidates and compare order before vs. after.

**Prereqs:** Ch 11 (model APIs, embeddings) — `learn/part-03-llm-substrate/11-*`; the
embedding intuition from Ch 8. Optional packages used live (`sentence-transformers`,
`rank-bm25`) are gated behind `MOCK`; the notebook runs fully offline by default."""
))

cells.append(code(
'''# --- Setup -------------------------------------------------------------------
import os
import math
import random
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()  # read any keys from a local .env (never hardcode them)

# MOCK=1 (default) runs FREE and OFFLINE with canned, realistic embeddings/scores.
# MOCK=0 uses real local models (sentence-transformers, rank-bm25) -- no API key needed,
# but downloads small model weights on first run.
MOCK = os.getenv("COMPANION_MOCK", "1") == "1"

random.seed(13)  # determinism for the mock embeddings below

DATA = Path("data")
print(f"MOCK mode: {MOCK}  (set COMPANION_MOCK=0 to use real local models)")
print(f"Corpus file present: {(DATA / 'corpus.jsonl').exists()}")'''
))

cells.append(md(
"""## 1. Load one messy-ish document

Real corpora arrive hostile: identifiers, near-duplicate pages, policy text where a single
clause means nothing without its heading. Our tiny corpus deliberately includes literal
identifiers (`ERR_QUOTA_42`, `WIDGET-PRO-128`) and a **near-duplicate pair** (cancel vs.
upgrade a subscription) so the failure modes show up at this scale.

We concatenate the snippets into one document to chunk, the way a parser would hand you the
extracted text of a page."""
))

cells.append(code(
'''import json

records = [json.loads(line) for line in (DATA / "corpus.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
# Join into one document with blank-line paragraph separators (what a parser emits).
document = "\\n\\n".join(r["text"] for r in records)
print(f"{len(records)} source snippets, {len(document)} chars total\\n")
print(document[:320], "...")'''
))

cells.append(md(
"""## 2. Chunk with the book's paragraph-aware `chunk()`

This is the exact greedy, paragraph-aware chunker from §13.2. It splits on blank lines
(paragraph boundaries the author already drew), packs paragraphs up to a token budget, and
carries a small character overlap so a thought cut at a boundary survives in the next chunk."""
))

cells.append(code(
'''def chunk(text: str, max_tokens: int = 600, overlap: int = 80,
          count=lambda s: len(s) // 4) -> list[str]:
    """Greedy paragraph-aware chunker with overlap (token estimate). From book §13.2."""
    paras, chunks, buf = text.split("\\n\\n"), [], ""
    for p in paras:
        if buf and count(buf) + count(p) > max_tokens:
            chunks.append(buf.strip())
            buf = buf[-overlap * 4:]          # overlap is in CHARS (~tokens*4)
        buf = f"{buf}\\n\\n{p}"
    if buf.strip():
        chunks.append(buf.strip())
    return chunks


# A SMALL budget makes this tiny corpus produce several chunks to inspect the mechanics.
demo_chunks = chunk(document, max_tokens=60, overlap=20)
print(f"{len(demo_chunks)} chunks at max_tokens=60")
for i, c in enumerate(demo_chunks):
    print(f"\\n--- chunk {i}  (~{len(c)//4} tokens, {len(c)} chars) ---")
    print(c[:200])'''
))

cells.append(md(
"""## ⚠️ Pitfall: read a *random sample* of the actual chunks

The most common chunking failure is invisible — a fixed-size splitter severs a table from
its header, or code from its explanation, and retrieval surfaces fragments that *almost*
contain the answer. **Five minutes of reading real chunks catches what no metric will.**
Below we contrast a naive fixed-size character splitter (cuts mid-sentence, mid-identifier)
with our structure-aware split."""
))

cells.append(code(
'''def fixed_size_split(text, size=120):
    """A naive splitter that ignores structure -- the anti-pattern."""
    return [text[i:i + size] for i in range(0, len(text), size)]


naive = fixed_size_split(document, size=120)
print("NAIVE fixed-size split (note the mid-word / mid-identifier cuts):")
for c in naive[2:5]:
    print("  |", repr(c))

print("\\nSTRUCTURE-AWARE split (paragraph boundaries kept intact):")
sample = random.sample(range(len(demo_chunks)), k=min(3, len(demo_chunks)))
for i in sorted(sample):
    print(f"  | chunk {i}: {demo_chunks[i][:90]!r}")'''
))

cells.append(md(
"""## 3. The retrieval corpus

For the rest of the pipeline we retrieve over **one clean chunk per source snippet** — each is
already a self-contained, document-sized unit, exactly the `{id, text, source}` shape a real
parse-and-chunk stage emits (and what Notebook 13-02 indexes). Keeping a literal identifier in
*one* chunk is what lets us see hybrid search rescue it below."""
))

cells.append(code(
'''chunks = [r["text"] for r in records]
ids = [r["id"] for r in records]
print(f"{len(chunks)} retrieval chunks (one per snippet):")
for i, c in enumerate(chunks):
    print(f"  [{i}] {ids[i]:<12} {c[:55]!r}")'''
))

cells.append(md(
"""## 4. Embed chunks and the query, rank by cosine similarity

An embedding model maps text to a vector so that similar meanings land near each other.
Retrieval is then geometry: embed the query, find the nearest chunk vectors, return their
text. On **normalized** vectors, cosine similarity is just a dot product.

In `MOCK` mode we use a tiny deterministic hashing embedder (no downloads) that still
captures lexical overlap well enough to teach ranking. With `MOCK=0` we use the book's
local model `BAAI/bge-small-en-v1.5` via `sentence-transformers`."""
))

cells.append(code(
'''def _normalize(v):
    n = math.sqrt(sum(x * x for x in v)) or 1.0
    return [x / n for x in v]


def _mock_embed(texts):
    """Deterministic bag-of-words hash embedding, L2-normalized. Offline + free."""
    DIM = 256
    vecs = []
    for t in texts:
        v = [0.0] * DIM
        for tok in t.lower().replace("\\n", " ").split():
            tok = tok.strip(".,:;!?()[]\\"'")
            if tok:
                v[hash(("salt", tok)) % DIM] += 1.0
        vecs.append(_normalize(v))
    return vecs


if MOCK:
    def embed(texts):
        return _mock_embed(texts)
else:
    from sentence_transformers import SentenceTransformer
    _EMBEDDER = SentenceTransformer("BAAI/bge-small-en-v1.5")  # book's model, §13.8

    def embed(texts):
        return _EMBEDDER.encode(texts, normalize_embeddings=True).tolist()


def cosine_rank(query, chunk_texts, k=5):
    q = embed([query])[0]
    D = embed(chunk_texts)
    scores = [sum(qi * di for qi, di in zip(q, d)) for d in D]  # dot product = cosine
    order = sorted(range(len(chunk_texts)), key=lambda i: scores[i], reverse=True)
    return [(i, scores[i]) for i in order[:k]]


q1 = "How long do refunds take for a domestic order?"
for i, s in cosine_rank(q1, chunks, k=3):
    print(f"{s:.3f}  chunk {i}: {chunks[i][:80]!r}")'''
))

cells.append(md(
"""## \U0001F52E Predict before you run

The next query is **"how do I cancel my subscription?"**. The corpus contains a *near-duplicate*
pair: a "cancel subscription" chunk and an "upgrade subscription" chunk. Both are about
subscriptions and embed very close together.

**Predict:** will plain vector search put the *cancel* chunk strictly above the *upgrade*
chunk? Write down your guess, then run the cell."""
))

cells.append(code(
'''q2 = "how do I cancel my subscription?"
ranked = cosine_rank(q2, chunks, k=4)
for i, s in ranked:
    label = "<-- cancel" if "Cancel a subscription" in chunks[i] else ("<-- upgrade" if "Upgrade a subscription" in chunks[i] else "")
    print(f"{s:.3f}  chunk {i}: {chunks[i][:70]!r} {label}")

print("\\nWhat you just saw: 'cancel' and 'upgrade' score almost identically because they are")
print("topically near-identical. Semantic match != relevance -- this gap is why rerankers exist.")'''
))

cells.append(md(
"""## 5. Hybrid search: add BM25, fuse with RRF

Embeddings are bad at exactly what keyword search is good at: identifiers, error codes, SKUs.
A query for `ERR_QUOTA_42` should match the one chunk containing that literal string, but its
embedding is nearly meaningless. **Hybrid search** runs BM25 keyword scoring *and* vector
similarity, then merges the ranked lists with **reciprocal rank fusion (RRF)** — which
rewards a chunk that ranks well on *either* list without needing the scores to be comparable."""
))

cells.append(code(
'''def _tokenize(s):
    return [w for w in s.lower().replace("\\n", " ").replace("_", " ").split() if w.strip(".,:;!?()[]")]


def _mock_bm25_rank(query, chunk_texts, k):
    """Tiny BM25-ish lexical scorer (term frequency with IDF). Offline."""
    docs = [_tokenize(c) for c in chunk_texts]
    N = len(docs)
    df = {}
    for d in docs:
        for w in set(d):
            df[w] = df.get(w, 0) + 1
    qtoks = _tokenize(query)
    scores = []
    for d in docs:
        s = 0.0
        for w in qtoks:
            if w in d:
                idf = math.log(1 + (N - df.get(w, 0) + 0.5) / (df.get(w, 0) + 0.5))
                s += idf * (d.count(w) / (len(d) or 1))
        scores.append(s)
    order = sorted(range(N), key=lambda i: scores[i], reverse=True)
    return [(i, scores[i]) for i in order[:k]]


if MOCK:
    bm25_rank = _mock_bm25_rank
else:
    from rank_bm25 import BM25Okapi  # extra dep: declared in this cell + PLAN

    def bm25_rank(query, chunk_texts, k):
        bm = BM25Okapi([_tokenize(c) for c in chunk_texts])
        scores = bm.get_scores(_tokenize(query))
        order = sorted(range(len(chunk_texts)), key=lambda i: scores[i], reverse=True)
        return [(i, float(scores[i])) for i in order[:k]]


def rrf_fuse(query, chunk_texts, k=6, c=60):
    """Reciprocal rank fusion of vector + BM25 rankings."""
    vec = [i for i, _ in cosine_rank(query, chunk_texts, k=len(chunk_texts))]
    kw = [i for i, _ in bm25_rank(query, chunk_texts, k=len(chunk_texts))]
    fused = {}
    for ranking in (vec, kw):
        for rank, idx in enumerate(ranking):
            fused[idx] = fused.get(idx, 0.0) + 1.0 / (c + rank + 1)
    order = sorted(fused, key=lambda i: fused[i], reverse=True)
    return [(i, fused[i]) for i in order[:k]]


q3 = "what does ERR_QUOTA_42 mean?"
print("Vector only:")
for i, s in cosine_rank(q3, chunks, k=3):
    print(f"  {s:.3f}  chunk {i}: {chunks[i][:60]!r}")
print("Hybrid (RRF):")
for i, s in rrf_fuse(q3, chunks, k=3):
    hit = "<-- the literal match" if "ERR_QUOTA_42" in chunks[i] else ""
    print(f"  {s:.4f}  chunk {i}: {chunks[i][:60]!r} {hit}")'''
))

cells.append(md(
"""## 6. Rerank the candidates with a cross-encoder

Bi-encoder retrieval (embed query and chunks separately) is fast but coarse. A
**cross-encoder reranker** reads the query and a candidate *together* and scores actual
relevance — far more accurate, far too slow to run over the whole corpus. So you stage them:
retrieve a generous candidate set cheaply, rerank, keep the top few for the model.

In `MOCK` mode we simulate the cross-encoder with a token-overlap relevance score that
prefers the chunk literally answering the query; with `MOCK=0` it's the book's
`BAAI/bge-reranker-base`."""
))

cells.append(code(
'''def _mock_rerank(query, candidates):
    """Stand-in cross-encoder: relevance from query-token coverage. Deterministic."""
    qset = set(_tokenize(query))
    scored = []
    for text in candidates:
        toks = set(_tokenize(text))
        overlap = len(qset & toks) / (len(qset) or 1)
        scored.append(overlap)
    return scored


if MOCK:
    def rerank(query, candidate_texts):
        return _mock_rerank(query, candidate_texts)
else:
    from sentence_transformers import CrossEncoder
    _RERANKER = CrossEncoder("BAAI/bge-reranker-base")  # book §13.5

    def rerank(query, candidate_texts):
        return list(_RERANKER.predict([(query, t) for t in candidate_texts]))


# Stage it: take a generous candidate set from hybrid search, then rerank -> keep top 3.
q4 = "how do I cancel my subscription?"
cand_idx = [i for i, _ in rrf_fuse(q4, chunks, k=min(6, len(chunks)))]
cand_texts = [chunks[i] for i in cand_idx]

print("BEFORE rerank (hybrid order):")
for i in cand_idx:
    print(f"  chunk {i}: {chunks[i][:70]!r}")

scores = rerank(q4, cand_texts)
reranked = sorted(zip(scores, cand_idx), reverse=True)[:3]
print("\\nAFTER cross-encoder rerank (top 3 the LLM would see):")
for s, i in reranked:
    print(f"  {s:.3f}  chunk {i}: {chunks[i][:70]!r}")'''
))

cells.append(md(
"""## \U0001F3AF Senior lens

Apply these upgrades in **cost-effectiveness order**, and add one only when a metric demands it:

1. **Hybrid search** first — cheap, structural, and the single highest-value upgrade for
   technical corpora full of identifiers and codes.
2. **Reranking** second — one extra model call over ~30–50 candidates, large precision gain.
3. **Query transformation** third — it adds latency and an LLM dependency to *every* query,
   so earn it with an eval, not a hunch.

It is common for one of the three to carry your domain and another to do nothing. A RAG
system is not a trophy case of techniques; it is the smallest pipeline that passes your evals
(Notebook 13-03)."""
))

cells.append(md(
"""## Recap

- A RAG pipeline is two halves: **offline** (parse → chunk → embed → index) and **online**
  (embed query → search → rerank → generate). Most quality lives on the offline + retrieval side.
- The book's paragraph-aware `chunk()` keeps meaning boundaries intact; a fixed-size splitter
  severs them. **Always read a random sample of real chunks.**
- Cosine similarity on normalized vectors is a dot product. **Semantic match is not relevance**
  — the cancel/upgrade near-duplicate proves it.
- **Hybrid search (BM25 + vector via RRF)** rescues literal identifiers like `ERR_QUOTA_42`.
- A **cross-encoder reranker** re-orders a cheap candidate set into what the model actually sees."""
))

cells.append(md(
"""## Exercises

Each exercise *changes* something and asks you to predict the effect before running.

1. **Chunk size.** Re-run `chunk()` with `max_tokens=30` then `max_tokens=200`. Predict, then
   check: how does the number of chunks and the top hit for `q1` change?
2. **Kill the reranker.** For `q4`, compare the top-3 from `rrf_fuse` alone vs. after rerank.
   Which chunk moves, and why?
3. **Identifier query.** Add a new query for `WIDGET-PRO-128` and show vector-only vs. hybrid.
   Predict which one surfaces the SKU chunk first.
4. **Live mode (optional).** Set `COMPANION_MOCK=0`, install `sentence-transformers` and
   `rank-bm25`, and re-run. Do the rankings agree with the mock on the easy queries?"""
))

cells.append(code('''# Exercise 1: chunk-size sweep
'''))
cells.append(code('''# Exercise 2: rerank vs. no-rerank top-3 for q4
'''))
cells.append(code('''# Exercise 3: identifier query, vector vs. hybrid
'''))
cells.append(code('''# Exercise 4 (optional): set COMPANION_MOCK=0 and compare
'''))

cells.append(md(
"""## Next

You built the toy retriever stage by stage. Next, **Notebook 13-02** wraps this behind a
clean `Retriever` protocol, indexes into Chroma, and generates a **grounded, cited** answer
that declines when the sources don't cover the question.

- Next notebook: [`13-02-grounded-answer-with-citations.ipynb`](./13-02-grounded-answer-with-citations.ipynb)
- Production version (hybrid + rerank + query transform + caching): [`blueprints/rag-pipeline/`](../../../blueprints/rag-pipeline/)
- Capstone module this feeds: [`capstone/rag/`](../../../capstone/rag/)"""
))

nb = {"cells": cells,
      "metadata": {"kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
                   "language_info": {"name": "python"}},
      "nbformat": 4, "nbformat_minor": 5}

with open(OUT, "w", encoding="utf-8") as f:
    json.dump(nb, f, ensure_ascii=False, indent=1)
print("wrote", OUT)
