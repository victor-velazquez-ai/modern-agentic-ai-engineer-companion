"""Generator for 13-03-rag-eval-golden-set.ipynb (run once, then delete)."""
import json, os

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "13-03-rag-eval-golden-set.ipynb")


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
"""# Measuring RAG: the scorecard on a golden set

> \U0001F4D3 *Companion to* **Modern Agentic AI Engineer** *· Ch 13 §13.8 (Evaluating RAG) · type: concept-lab*

Build a small **golden set**, compute the retrieval metrics from set arithmetic (instant, free,
deterministic), then *gate* the expensive LLM-judged generation metrics behind them — and add
the operational family so "faithful but slow and costly" registers as a failure too."""
))

cells.append(md(
"""## \U0001F9E0 Why this matters

RAG has **two coupled subsystems**, and they fail in opposite ways. A bad answer over *perfect*
retrieval is a prompting/model problem; a perfect-sounding answer over *bad* retrieval is a
retrieval problem — and the fixes are nothing alike. So you **never collapse them to one score**.
The discipline that makes a scorecard you'll actually maintain: lead with the near-free retrieval
metrics on every change, and only spend LLM-judge calls when retrieval held."""
))

cells.append(md(
"""## Objectives & prereqs

**By the end you can:**
- Define a tiny golden set (questions + gold chunk ids + reference answers).
- Compute **Hit Rate, Recall@k, Precision@k, MRR, nDCG@k** directly from retrieved vs. gold ids.
- Gate **generation** metrics (faithfulness, answer relevance) behind retrieval health, scored
  with a *fixed* LLM judge + rubric.
- Track the **operational** family (p95 latency, cost/query, index staleness) alongside quality.

**Prereqs:** Notebook 13-02 (a working retriever to score). Retrieval metrics are fully offline;
the LLM judge is `MOCK=1` canned (deterministic) by default."""
))

cells.append(code(
'''# --- Setup -------------------------------------------------------------------
import os
import json
import math
import random
from pathlib import Path
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()

# MOCK=1 (default): offline retriever + canned, deterministic LLM judge -> FREE, no key.
# MOCK=0: real generation + a real LLM judge (a handful of short judge calls per question).
MOCK = os.getenv("COMPANION_MOCK", "1") == "1"

random.seed(13)
JUDGE_MODEL = "claude-sonnet-4-5"  # fixed judge: same model + rubric every run
DATA = Path("data")
print(f"MOCK mode: {MOCK}  ·  judge model (live): {JUDGE_MODEL}")'''
))

cells.append(md(
"""## 1. Load the golden set and a retriever to score

The golden set lives in `data/golden_set.jsonl`: each row is a question, the **gold chunk
id(s)** that answer it, and a tiny reference answer. We rebuild the offline retriever from
13-02 (same corpus, same `Hit`) so the whole notebook stays free and deterministic."""
))

cells.append(code(
'''@dataclass
class Hit:
    id: str
    text: str
    source: str
    score: float


def _normalize(v):
    n = math.sqrt(sum(x * x for x in v)) or 1.0
    return [x / n for x in v]


def _embed(texts):
    """Deterministic offline embedding (matches 13-01/13-02)."""
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


CORPUS = [json.loads(l) for l in (DATA / "corpus.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
_VECS = {d["id"]: _embed([d["text"]])[0] for d in CORPUS}


def retrieve(query, k=5, use_reranker=True):
    """Tiny retriever returning Hits with ids, so we can score against gold ids."""
    q = _embed([query])[0]
    scored = [Hit(id=d["id"], text=d["text"], source=d["source"],
                  score=sum(a * b for a, b in zip(q, _VECS[d["id"]]))) for d in CORPUS]
    scored.sort(key=lambda h: h.score, reverse=True)
    top = scored[:k]
    if use_reranker:  # cheap token-overlap rerank, like 13-01's mock cross-encoder
        qset = {w.strip(".,:;!?") for w in query.lower().split() if len(w) > 2}
        top.sort(key=lambda h: len(qset & {w.strip(".,:;!?") for w in h.text.lower().split()}),
                 reverse=True)
    return top


GOLD = [json.loads(l) for l in (DATA / "golden_set.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
print(f"{len(GOLD)} golden questions, {len(CORPUS)} corpus chunks")
print("example:", GOLD[0]["question"], "-> gold", GOLD[0]["gold_ids"])'''
))

cells.append(md(
"""## 2. Retrieval metrics from set arithmetic

These are classic information-retrieval numbers. They need only the golden set, run in
milliseconds, and tell you whether the right evidence arrived — so you run them on **every**
change, first.

- **Hit Rate** — did *any* gold chunk appear in the top-k? The coarsest floor.
- **Recall@k** — of the gold chunks, what fraction made the top-k? *Low recall is the dominant
  cause of wrong answers.*
- **Precision@k** — of the top-k, what fraction is gold? Low precision dilutes context and cost.
- **MRR** — how high the *first* gold hit lands (1/rank).
- **nDCG@k** — rank quality, discounting relevant hits by position."""
))

cells.append(code(
'''def hit_rate(retrieved_ids, gold_ids):
    return 1.0 if set(retrieved_ids) & set(gold_ids) else 0.0


def recall_at_k(retrieved_ids, gold_ids):
    gold = set(gold_ids)
    return len(set(retrieved_ids) & gold) / (len(gold) or 1)


def precision_at_k(retrieved_ids, gold_ids):
    gold = set(gold_ids)
    return len([i for i in retrieved_ids if i in gold]) / (len(retrieved_ids) or 1)


def mrr(retrieved_ids, gold_ids):
    gold = set(gold_ids)
    for rank, i in enumerate(retrieved_ids, start=1):
        if i in gold:
            return 1.0 / rank
    return 0.0


def ndcg_at_k(retrieved_ids, gold_ids):
    gold = set(gold_ids)
    dcg = sum((1.0 / math.log2(rank + 1)) for rank, i in enumerate(retrieved_ids, start=1) if i in gold)
    ideal = sum((1.0 / math.log2(rank + 1)) for rank in range(1, min(len(gold), len(retrieved_ids)) + 1))
    return dcg / ideal if ideal else 0.0


def retrieval_scorecard(k=5, use_reranker=True):
    rows = []
    for ex in GOLD:
        rid = [h.id for h in retrieve(ex["question"], k=k, use_reranker=use_reranker)]
        rows.append({
            "hit": hit_rate(rid, ex["gold_ids"]),
            "recall": recall_at_k(rid, ex["gold_ids"]),
            "precision": precision_at_k(rid, ex["gold_ids"]),
            "mrr": mrr(rid, ex["gold_ids"]),
            "ndcg": ndcg_at_k(rid, ex["gold_ids"]),
        })
    return {m: sum(r[m] for r in rows) / len(rows) for m in rows[0]}


base = retrieval_scorecard(k=5)
print("Retrieval scorecard (k=5), mean over golden set:")
for m, v in base.items():
    print(f"  {m:<10} {v:.3f}")'''
))

cells.append(md(
"""## \U0001F52E Predict before you run

We'll degrade retrieval two ways: (a) **drop the reranker**, and (b) **shrink k to 2** (a proxy
for smaller chunks / a tighter budget).

**Predict:** which retrieval metric moves *most*? Is it precision, or recall? Recall is the
dominant cause of *wrong answers* — write your guess, then run."""
))

cells.append(code(
'''import copy

variants = {
    "baseline (k=5, rerank)": retrieval_scorecard(k=5, use_reranker=True),
    "no reranker (k=5)":      retrieval_scorecard(k=5, use_reranker=False),
    "tiny k=2 (rerank)":      retrieval_scorecard(k=2, use_reranker=True),
}
cols = ["hit", "recall", "precision", "mrr", "ndcg"]
print(f"{'variant':<24}" + "".join(f"{c:>11}" for c in cols))
for name, sc in variants.items():
    print(f"{name:<24}" + "".join(f"{sc[c]:>11.3f}" for c in cols))

print("\\nWhat you just saw: cutting k slashes RECALL (gold chunks fall out of the top-k),")
print("which is exactly what makes answers wrong. Precision can even rise as k shrinks --")
print("never read it alone.")'''
))

cells.append(md(
"""## 3. Generation metrics — *gated* behind retrieval

Generation metrics judge what the model did with the evidence and need an LLM judge. They are
expensive, so **only run them when retrieval held** — if the gold chunk never arrived, a
generation score measures nothing useful. We score **faithfulness** (is every claim supported by
the retrieved context?) and **answer relevance** (does it address the question?) with the *same*
judge and rubric every time. In `MOCK` mode the judge is a deterministic stand-in."""
))

cells.append(code(
'''def _mock_answer(question, hits):
    """Canned grounded answer (same contract as 13-02): use top hit or decline."""
    qtoks = {w.strip(".,:;!?") for w in question.lower().split() if len(w) > 3}
    best = max(hits, key=lambda h: len(qtoks & {w.strip(".,:;!?") for w in h.text.lower().split()}), default=None)
    if best is None:
        return "The sources do not contain the answer."
    return best.text.split(". ")[0] + "."


def _mock_judge(question, answer_text, context_texts, reference):
    """Deterministic faithfulness + answer-relevance judge. Returns 0..1 each."""
    ctx = " ".join(context_texts).lower()
    ans_tokens = [w.strip(".,:;!?") for w in answer_text.lower().split() if len(w) > 3]
    supported = sum(1 for w in ans_tokens if w in ctx)
    faithfulness = supported / (len(ans_tokens) or 1)
    qtoks = {w.strip(".,:;!?") for w in question.lower().split() if len(w) > 3}
    rel = len(qtoks & set(ans_tokens)) / (len(qtoks) or 1)
    return {"faithfulness": round(faithfulness, 3), "answer_relevance": round(min(1.0, rel + 0.3), 3)}


def _live_judge(question, answer_text, context_texts, reference):
    from anthropic import Anthropic
    client = Anthropic()
    rubric = ("Score 0..1. faithfulness = fraction of answer claims supported by the context. "
              "answer_relevance = does the answer address the question. "
              'Reply as JSON: {"faithfulness": x, "answer_relevance": y}.')
    msg = client.messages.create(
        model=JUDGE_MODEL, max_tokens=200, system=rubric,
        messages=[{"role": "user", "content":
                   f"Question: {question}\\nContext:\\n{chr(10).join(context_texts)}\\nAnswer: {answer_text}"}],
    )
    text = next((b.text for b in msg.content if b.type == "text"), "{}")
    return json.loads(text)


judge = _mock_judge if MOCK else _live_judge


def generation_scorecard(k=5, recall_gate=0.5):
    scored, skipped = [], 0
    for ex in GOLD:
        hits = retrieve(ex["question"], k=k)
        rid = [h.id for h in hits]
        if recall_at_k(rid, ex["gold_ids"]) < recall_gate:
            skipped += 1          # retrieval failed -> generation score is meaningless
            continue
        ans = _mock_answer(ex["question"], hits)
        scored.append(judge(ex["question"], ans, [h.text for h in hits], ex["reference_answer"]))
    agg = {m: sum(s[m] for s in scored) / (len(scored) or 1) for m in ("faithfulness", "answer_relevance")}
    return agg, len(scored), skipped


agg, n_scored, n_skipped = generation_scorecard()
print(f"Generation metrics over {n_scored} questions where retrieval held "
      f"({n_skipped} gated out):")
for m, v in agg.items():
    print(f"  {m:<18} {v:.3f}")'''
))

cells.append(md(
"""## 4. The operational family

A system that is faithful and accurate but answers in four seconds at a dollar a query has
**failed just as surely** as one that hallucinates. Track at least one operational number:
p95 latency, cost per query, and index staleness. (Latencies here are simulated and seeded so
the notebook stays deterministic and offline.)"""
))

cells.append(code(
'''def _simulated_latency_ms():
    # Embed + search + rerank, in ms. Seeded for determinism.
    return random.gauss(45, 12) + random.gauss(30, 10)  # retrieval + rerank


def operational_scorecard():
    lat = sorted(max(1.0, _simulated_latency_ms()) for _ in GOLD)
    p95 = lat[int(0.95 * (len(lat) - 1))]
    # Cost model: embeddings are local (free); a generation call ~ $0.0007 here.
    cost_per_query = 0.0007
    index_staleness_min = 12  # minutes since last re-index of a changed doc
    return {"p95_latency_ms": round(p95, 1),
            "cost_per_query_usd": cost_per_query,
            "index_staleness_min": index_staleness_min}


ops = operational_scorecard()
print("Operational family:")
for m, v in ops.items():
    print(f"  {m:<22} {v}")'''
))

cells.append(md(
"""## ⚠️ Pitfall: a drifting judge and a single blended score

Two ways an eval lies to you:

1. **A judge whose model or rubric drifts** measures its own mood, not your system. Pin the
   judge model *and* the rubric; change them only deliberately and re-baseline when you do.
2. **A single blended score hides which leg broke.** Average faithfulness, recall, and latency
   into one number and you can no longer tell a retrieval failure from a generation failure —
   which is the entire point of the triad. Keep the families separate."""
))

cells.append(code(
'''# Demonstrate the trap: a blended score that masks a recall collapse.
def blended(retr, gen):
    return 0.34 * retr["recall"] + 0.33 * gen[0]["faithfulness"] + 0.33 * gen[0]["answer_relevance"]


good = (retrieval_scorecard(k=5, use_reranker=True), generation_scorecard(k=5))
bad = (retrieval_scorecard(k=2, use_reranker=False), generation_scorecard(k=2))
print(f"Blended score  good pipeline: {blended(*good):.3f}")
print(f"Blended score  k=2/no-rerank: {blended(*bad):.3f}")
print(f"  ... but recall fell {good[0]['recall']:.2f} -> {bad[0]['recall']:.2f}. "
      "The blend hid a retrieval collapse. Report the families separately.")'''
))

cells.append(md(
"""## \U0001F3AF Senior lens

Lead with the **near-free retrieval metrics on every change** — a chunking or embedding tweak
runs them first and only proceeds to the expensive LLM-judged generation metrics if retrieval
held. This same golden set is what **Chapter 22** wires into CI, so a recall-dropping change
fails a *build*, not a customer. The scorecard isn't a report you generate once; it's a gate you
run on every diff."""
))

cells.append(md(
"""## Recap

- RAG has two coupled subsystems; score them **separately** — opposite failures need opposite fixes.
- **Retrieval metrics** (hit rate, recall@k, precision@k, MRR, nDCG@k) come from set arithmetic:
  instant, free, deterministic. **Recall is the dominant cause of wrong answers.**
- **Gate** the expensive generation metrics (faithfulness, answer relevance) behind retrieval
  health, with a *fixed* judge + rubric.
- Track an **operational** number too — faithful-but-slow-and-costly is still a failure.
- A drifting judge or a single blended score will lie to you. Pin the judge; keep families apart."""
))

cells.append(md(
"""## Exercises

1. **Move the dial.** Re-run `retrieval_scorecard` for `k` in `{1, 3, 5, 8}`. Predict, then plot
   recall vs. precision — where's the knee for this corpus?
2. **Break recall on purpose.** Corrupt one gold id in `golden_set.jsonl` (in a copy) and watch
   exactly which metric drops. Confirm hit rate and recall move while the answer "looks" fine.
3. **Add a multi-gold question.** Question 8 needs *two* chunks — verify recall@k penalizes a
   retriever that finds only one. Add another two-gold question of your own.
4. **Live judge (optional).** Set `COMPANION_MOCK=0` with `ANTHROPIC_API_KEY`. Do the live
   faithfulness scores agree with the mock's ranking of good vs. degraded pipelines?"""
))

cells.append(code('''# Exercise 1: k-sweep, recall vs precision
'''))
cells.append(code('''# Exercise 2: corrupt a gold id (on a COPY) and watch the metrics
'''))
cells.append(code('''# Exercise 3: add a multi-gold question and check recall@k
'''))
cells.append(code('''# Exercise 4 (optional): COMPANION_MOCK=0 live judge
'''))

cells.append(md(
"""## Next

You can now score a RAG change on a scorecard and say *which* subsystem regressed. This golden
set doesn't stay in a notebook — **Chapter 22** builds the full evaluation harness around it and
wires it into CI, so a recall-dropping tweak fails a build instead of a customer.

- Chapter 22 (eval harness in CI): `learn/part-06-evaluation-and-quality/22-*`
- Production pipeline being measured: [`blueprints/rag-pipeline/`](../../../blueprints/rag-pipeline/)
- Capstone eval target: [`capstone/evals/`](../../../capstone/evals/) · checkpoint `checkpoints/ch13-rag`"""
))

nb = {"cells": cells,
      "metadata": {"kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
                   "language_info": {"name": "python"}},
      "nbformat": 4, "nbformat_minor": 5}

with open(OUT, "w", encoding="utf-8") as f:
    json.dump(nb, f, ensure_ascii=False, indent=1)
print("wrote", OUT)
