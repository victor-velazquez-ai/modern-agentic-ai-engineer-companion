"""Generator for 14-02-long-term-memory-recall-reflection.ipynb."""
import os

from _nbgen import Q3, code, md, write_nb

HERE = os.path.dirname(os.path.abspath(__file__))
cells = []

cells.append(md(r"""
# 🔧 Build: a layered memory module (recall × write)

> 📓 *Companion to* **Modern Agentic AI Engineer** *· Ch 14 §14.5, §14.6, §14.9, §14.14 · type: walkthrough*

**The promise:** build the book's `Memory` — a budgeted short-term buffer plus a long-term vector store with **ranked recall** (relevance × recency × importance) and **reflective writes** — and see, concretely, why bare top-k recall is not enough. This is the chapter's 🔧 Build; it becomes the capstone's `memory/` module.
"""))

cells.append(md(r"""
## 🧠 Why this matters — and the 🎯 senior insight up front

Long-term **semantic memory and RAG are the same machinery**. "Remembering facts about a user" and "retrieving relevant documents" are both: *embed, store, pull back by similarity.* So we don't invent a new subsystem — we lift Ch 13's retriever and put a memory-shaped interface on it.

That reuse is the senior move here: **treat memory as a retrieval problem** and an entire subsystem you'd otherwise design (and operate) simply disappears. What memory *adds* on top of RAG is two disciplines RAG usually skips: **ranking** recall by more than similarity, and **writing** deliberately instead of storing everything.
"""))

cells.append(md(r"""
## Objectives & prereqs

**By the end you can:**
- write to memory with a **reflection** step that extracts durable facts and dedupes near-copies;
- recall by a **weighted blend** of relevance × recency × importance, not bare top-k;
- **consolidate** episodic exchanges into durable semantic facts;
- assemble the book's `Memory` class the capstone uses.

**Prereqs:** [`14-01`](./14-01-context-budget-window-compaction.ipynb) (short-term compaction) · **Ch 13** (the vector store / retriever memory reuses) · Ch 12 (tools, for the MemGPT aside).

**Run first:** nothing — offline-first, runs free in `MOCK=1` (the default). Uses a tiny committed fixture in `data/`.
"""))

cells.append(code(rf"""
# --- Setup ---------------------------------------------------------------
# Offline-first: a local embedding + an in-memory vector store stand in for the
# Ch 13 stack, so this runs free with NO API key and NO model download.
import json
import math
import os
import random
import time
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

# MOCK=1 (default): canned reflection/consolidation (deterministic, no network).
# MOCK=0: live extraction calls (Ch 11). Cost: a few short completions.
MOCK = os.getenv("COMPANION_MOCK", "1") == "1"

random.seed(14)

DATA = Path("data")

# Embeddings: use sentence-transformers if installed; else a deterministic local
# character-3-gram hash embedding. The fallback is crude but STABLE and offline
# (and gives nonzero similarity for partial word overlap), so the recall lesson
# reproduces anywhere. In production this is your Ch 13 model.
_DIM = 512
try:
    from sentence_transformers import SentenceTransformer

    _model = SentenceTransformer("all-MiniLM-L6-v2")

    def embed(text: str):
        return _model.encode(text, normalize_embeddings=True).tolist()

    _EMBED = "sentence-transformers/all-MiniLM-L6-v2"
except Exception:
    def embed(text: str):
        {Q3}Deterministic char-3-gram hash embedding (offline fallback).{Q3}
        t = "".join(ch if ch.isalnum() else " " for ch in text.lower())
        vec = [0.0] * _DIM
        for word in t.split():
            padded = f" {{word}} "
            for i in range(len(padded) - 2):  # character trigrams
                vec[hash(padded[i:i + 3]) % _DIM] += 1.0
        norm = math.sqrt(sum(v * v for v in vec)) or 1.0
        return [v / norm for v in vec]

    _EMBED = "local char-3-gram hash (offline fallback)"

print(f"MOCK     = {{MOCK}}")
print(f"embed    = {{_EMBED}}")
"""))

cells.append(md(r"""
## A minimal vector store (the Ch 13 retriever, in miniature)

To keep the focus on *memory* rather than infrastructure, we stand up a tiny in-memory vector store with the same shape as the Ch 13 stack: `upsert(text, metadata)` and `search(query, k)` returning hits with a cosine similarity. Swap this for Chroma/Pinecone and nothing downstream changes — that is the whole point of treating memory as retrieval.
"""))

cells.append(code(rf"""
def cosine(a, b):
    return sum(x * y for x, y in zip(a, b))  # vectors are normalized


class VectorStore:
    {Q3}A miniature stand-in for the Ch 13 vector store. Same interface, no deps.{Q3}

    def __init__(self):
        self.items = []  # each: {{"text", "vec", "meta"}}

    def upsert(self, text, metadata=None, dedupe_threshold=0.92):
        {Q3}Insert text; if a near-duplicate exists, UPDATE it instead of adding.{Q3}
        vec = embed(text)
        for item in self.items:
            if cosine(vec, item["vec"]) >= dedupe_threshold:
                item["text"] = text                       # refresh the wording
                item["meta"].update(metadata or {{}})
                item["meta"]["last_seen"] = time.time()
                return "updated"
        self.items.append({{"text": text, "vec": vec,
                           "meta": {{"last_seen": time.time(), **(metadata or {{}})}}}})
        return "inserted"

    def search(self, query, k=5):
        {Q3}Top-k by cosine similarity. Returns (text, meta, similarity).{Q3}
        qv = embed(query)
        scored = [(cosine(qv, it["vec"]), it) for it in self.items]
        scored.sort(key=lambda x: x[0], reverse=True)
        return [(it["text"], it["meta"], sim) for sim, it in scored[:k]]

    def __len__(self):
        return len(self.items)


print("VectorStore ready — this is the Ch 13 retriever with a memory-shaped interface.")
"""))

cells.append(md(r"""
## Reflective **write**: extract durable facts, don't store raw turns

Reading is the easy half; **writing** is the neglected half. Naively storing every message produces an expensive, noisy store that *hurts* retrieval. Instead run an **extraction / reflection** step (§14.9) that distills durable facts from a conversation and writes only those — then **dedupe/update** so "the user's manager is Ana" doesn't accumulate ten near-copies.

We reflect over the tiny committed conversation in `data/sample_conversation.json`.
"""))

cells.append(code(rf"""
conversation = json.loads((DATA / "sample_conversation.json").read_text(encoding="utf-8"))
print(f"loaded {{len(conversation)}} turns from data/sample_conversation.json")


def render(history):
    return "\n".join(f"{{m['role']}}: {{m['content']}}" for m in history)


def _mock_extract(history):
    {Q3}Deterministic stand-in for the LLM extraction step.

    A real model reads the transcript and returns durable facts as JSON. Here we
    return a fixed, realistic list (with importance scores) so the lesson is
    reproducible offline. Note what is OMITTED: greetings, weather, 'noted'.
    {Q3}
    return [
        {{"text": "User's name is Maria; runs support ops at Northwind (fintech).",
         "importance": 6}},
        {{"text": "User is severely allergic to penicillin.", "importance": 10}},
        {{"text": "User's manager is Ana Restrepo.", "importance": 5}},
        {{"text": "Team ships releases on Fridays.", "importance": 7}},
        {{"text": "User dislikes Monday standups.", "importance": 4}},
        {{"text": "User prefers metric units and a terse style.", "importance": 6}},
    ]


async def extract_facts(history):
    if MOCK:
        return _mock_extract(history)
    from anthropic import Anthropic

    client = Anthropic()
    resp = client.messages.create(
        model="claude-sonnet-4-5",
        max_tokens=512,
        messages=[{{"role": "user", "content":
            "Extract durable facts about the user or task worth remembering "
            "long-term (preferences, decisions, stable details). Return a JSON list "
            "of objects with 'text' and an integer 'importance' 1-10. Skip anything "
            "transient or obvious.\n\n" + render(history)}}],
    )
    return json.loads(resp.content[0].text)


async def reflect_and_store(conversation, memory):
    {Q3}Extract durable facts worth remembering, then upsert them (deduped).{Q3}
    facts = await extract_facts(conversation)
    results = []
    for fact in facts:
        action = memory.upsert(
            text=fact["text"],
            metadata={{"kind": "semantic", "importance": fact["importance"]}},
        )
        results.append((action, fact["text"]))
    return results


store = VectorStore()
results = await reflect_and_store(conversation, store)
for action, text in results:
    print(f"  {{action:8}} {{text}}")
print(f"\nstore now holds {{len(store)}} facts (the small talk was dropped).")
"""))

cells.append(md(r"""
## Bare top-k recall — and why it's not enough

Now query the store the naive way: pure cosine top-k. Watch what wins when the query is loosely worded.
"""))

cells.append(code(rf"""
# Seed each memory with a plausible age + last_seen so recency means something.
now = time.time()
HOUR = 3600
ages_hours = {{
    "User's name is Maria; runs support ops at Northwind (fintech).": 200,
    "User is severely allergic to penicillin.": 240,   # OLD but critical
    "User's manager is Ana Restrepo.": 50,
    "Team ships releases on Fridays.": 5,               # fresh + chatty
    "User dislikes Monday standups.": 3,                # fresh trivia
    "User prefers metric units and a terse style.": 10,
}}
for it in store.items:
    it["meta"]["last_seen"] = now - ages_hours.get(it["text"], 100) * HOUR

query = "Any medical considerations before we draft the patient-claims email?"
topk = store.search(query, k=3)
print("bare top-k (similarity only):")
for text, meta, sim in topk:
    print(f"  sim={{sim:.3f}}  imp={{meta['importance']:>2}}  {{text}}")
"""))

cells.append(md(r"""
🔮 **Predict — then run the next cell.** We will re-rank with relevance × recency × importance. The "allergic to penicillin" fact is **old** (240h) but **critical** (importance 10); "ships on Fridays" is **fresh** (5h) but **chatty** (importance 7). Under bare top-k vs the weighted blend — which one surfaces first for a *medical* query? Write your guess.
"""))

cells.append(code(rf"""
def rank(candidates, sims, now, w=(1.0, 1.0, 1.0), half_life=72 * 3600):
    {Q3}Re-rank vector hits by relevance x recency x importance.{Q3}
    scored = []
    for mem, relevance in zip(candidates, sims):
        recency = 0.5 ** ((now - mem["last_seen"]) / half_life)
        importance = mem.get("importance", 5) / 10
        s = w[0] * relevance + w[1] * recency + w[2] * importance
        scored.append((s, mem))
    scored.sort(key=lambda x: x[0], reverse=True)
    return [m for _, m in scored]


# Two-stage recall: over-fetch from the store, then re-rank and keep the top few.
over_fetched = store.search(query, k=len(store))               # over-fetch
cands = [{{"text": t, **m}} for t, m, _ in over_fetched]
sims = [s for _, _, s in over_fetched]

ranked = rank(cands, sims, now=now, w=(1.0, 0.5, 1.5))          # weight importance
print("weighted recall (relevance x recency x importance):")
for mem in ranked[:3]:
    print(f"  imp={{mem['importance']:>2}}  {{mem['text']}}")

print("\nThe penicillin allergy now outranks the fresh-but-chatty Friday fact — "
      "exactly the failure bare top-k would have caused in a medical context.")
"""))

cells.append(md(r"""
## ⚠️ Pitfall: store-everything memory *hurts* recall

It is tempting to dump every turn into long-term memory "just in case." Don't. Noise crowds out signal, retrieval degrades, and you accumulate stale facts and PII you now have to govern. Watch recall quality drop when we flood the store with chatty near-duplicates.
"""))

cells.append(code(rf"""
noisy = VectorStore()
for action, text in results:
    noisy.upsert(text, metadata={{"kind": "semantic", "importance": 5}})

# Flood with low-value, loosely-related chatter (the 'store everything' habit).
for i in range(40):
    noisy.upsert(f"User said thanks and chatted about the weather (note {{i}}).",
                 metadata={{"kind": "episodic", "importance": 1}}, dedupe_threshold=2.0)

clean_hits = [t for t, _, _ in store.search(query, k=5)]
noisy_hits = [t for t, _, _ in noisy.search(query, k=5)]
noise_in_topk = sum("weather" in t for t in noisy_hits)
print(f"clean store: {{len(store)}} items, top-5 are all real facts")
print(f"noisy store: {{len(noisy)}} items, {{noise_in_topk}}/5 of top-5 are pure noise")
print("\nUnbounded growth is a retrieval bug. Extract, dedupe, timestamp, and forget on purpose.")
"""))

cells.append(md(r"""
## Consolidation: fold episodes into one durable fact

Recall improves when the store is well-organized, and organization is *active*. **Consolidation** (§14.6.1) sweeps related episodic memories and distills them into fewer, more durable semantic facts — the reflection step run over memories instead of a conversation. Ten logged exchanges about deadlines collapse into one standing fact. The store shrinks; recall improves.
"""))

cells.append(code(rf"""
episodic = VectorStore()
for i in range(10):
    episodic.upsert(
        f"On day {{i}}, the user shipped the release on Friday afternoon.",
        metadata={{"kind": "episodic", "importance": 3}}, dedupe_threshold=2.0,
    )
print(f"before consolidation: {{len(episodic)}} episodic memories")


def _mock_consolidate(memories):
    {Q3}Deterministic stand-in: distil many episodes into one semantic fact.{Q3}
    return {{"text": "User consistently ships releases on Fridays (standing pattern).",
            "importance": 7}}


async def consolidate_episodes(src_store, dst_store):
    memories = [it["text"] for it in src_store.items]
    if MOCK:
        fact = _mock_consolidate(memories)
    else:
        from anthropic import Anthropic

        client = Anthropic()
        resp = client.messages.create(
            model="claude-sonnet-4-5", max_tokens=256,
            messages=[{{"role": "user", "content":
                "Distil these related memories into ONE durable fact. Return JSON "
                "with 'text' and integer 'importance' 1-10.\n\n" + "\n".join(memories)}}],
        )
        fact = json.loads(resp.content[0].text)
    dst_store.upsert(fact["text"],
                     metadata={{"kind": "semantic", "importance": fact["importance"]}})
    return fact


fact = await consolidate_episodes(episodic, store)
print(f"after consolidation : 1 durable fact -> '{{fact['text']}}'")
print(f"store grew by one clean semantic fact; the 10 raw episodes can now be aged out.")
"""))

cells.append(md(r"""
## Assemble the book's `Memory` class

Now wire the pieces into the layered `Memory` from §14.14: a budgeted short-term **buffer** the model sees every turn (with threshold compaction, reused from 14-01), a long-term **store** it queries on demand, and a **consolidate** step that decides what's worth keeping. This is the class the capstone's `memory/` module becomes.
"""))

cells.append(code(rf"""
def count_tokens(text: str) -> int:
    return max(1, (len(text) + 3) // 4)  # deterministic offline counter (see 14-01)


async def _summarize(history):
    salient = [m["content"] for m in history if len(m["content"]) > 30]
    return "Brief: " + " | ".join(salient[:3]) if salient else "Brief: (routine)"


async def compact(history, keep_recent=6):
    old, recent = history[:-keep_recent], history[-keep_recent:]
    if not old:
        return history
    brief = await _summarize(old)
    return [{{"role": "system", "content": brief}}, *recent]


class Memory:
    {Q3}Layered memory: short-term buffer + long-term ranked store (§14.14).{Q3}

    def __init__(self, vectors, count_tokens, budget=6000):
        self.vectors = vectors
        self.count_tokens, self.budget = count_tokens, budget
        self.buffer: list[dict] = []          # short-term

    async def remember_turn(self, role, content):
        self.buffer.append({{"role": role, "content": content}})
        if self._tokens() > self.budget * 0.7:
            self.buffer = await compact(self.buffer)

    async def recall(self, query, k=5, w=(1.0, 0.5, 1.5)):
        {Q3}Long-term semantic recall: over-fetch, then rank by the blend.{Q3}
        hits = self.vectors.search(query, k=max(k * 4, k))
        cands = [{{"text": t, **m}} for t, m, _ in hits]
        sims = [s for _, _, s in hits]
        return rank(cands, sims, now=time.time(), w=w)[:k]

    async def consolidate(self, episodic_store):
        await consolidate_episodes(episodic_store, self.vectors)

    def _tokens(self):
        return sum(self.count_tokens(m["content"]) for m in self.buffer)


mem = Memory(store, count_tokens, budget=200)
for turn in conversation:
    await mem.remember_turn(turn["role"], turn["content"])
recalled = await mem.recall("medical considerations for the claims email", k=2)
print("buffer turns held:", len(mem.buffer))
print("top recall:", recalled[0]["text"])
"""))

cells.append(md(r"""
### Aside: the MemGPT / virtual-context dial

We built **pipeline-driven** recall: our code retrieves and injects memories before the model runs — predictable and cheap. The other school is **agent-driven** (MemGPT-style): the model pages memory in and out itself via `memory_search` / `memory_save` tools (Ch 12), keeping only a *handle* in context. It's flexible but costs extra turns and tokens, and a confused agent pages badly. Treat it as a **dial**: default to pipeline-driven recall; add agent-driven paging where the task genuinely needs the model to go hunting.
"""))

cells.append(md(r"""
## 🎯 Senior lens: tune the recall weights to the domain

The weights `w = (relevance, recency, importance)` are a **product decision**, not a constant:

- **Support / chat:** lean on **recency** — the last thing the user said usually dominates intent.
- **Medical / compliance:** weight **importance** hard so a critical fact (an allergy, a legal hold) never decays out of reach, no matter how old.
- **Always over-fetch then re-rank.** Recall is a two-stage problem — retrieve-then-rank, exactly like a search engine. A near-miss that retrieves *nothing* beats one that retrieves the *wrong* fact confidently.

And govern writes as deliberately as reads: timestamp everything, dedupe on write, and forget on purpose (age/relevance decay, user-initiated deletion). Memory you only ever add to is a liability — in cost, in recall quality, and under GDPR.
"""))

cells.append(md(r"""
## Recap

- **Semantic memory == RAG**: reuse the Ch 13 retriever; put a memory interface on it.
- **Write with reflection**: extract durable facts, dedupe/update — never store raw turns.
- **Rank recall** by relevance × recency × importance; over-fetch then re-rank.
- A critical-but-old fact (penicillin allergy) beats a fresh-but-chatty one *only* once you weight importance — bare top-k buries it.
- **Consolidate** episodes into durable facts to shrink the store and sharpen recall.
- The layered `Memory` class = short-term buffer (threshold compaction) + long-term ranked store + consolidation.
"""))

cells.append(md(r"""
## Exercises

(Solutions live in `solutions/`, not inline.)

1. **Re-weight for support.** Set `w = (1.0, 1.5, 0.5)` and re-run recall for a *scheduling* query. Predict whether "dislikes Monday standups" rises above the allergy — then confirm, and explain when each weighting is correct.
2. **Break dedupe.** Upsert "User's manager is Ana." then "Manager: Ana Restrepo." Predict whether the store ends with 1 or 2 entries at `dedupe_threshold=0.92` vs `0.5`. Verify and reason about false merges.
3. **Forgetting policy.** Add an `evict(max_age_hours)` method that drops low-importance memories past an age, but *never* importance ≥ 9. Show the penicillin fact survives a sweep that clears the weather chatter.
4. **Recency half-life.** Change `half_life` from 72h to 6h and re-rank. Predict how aggressively old facts drop; identify a domain where 6h is right and one where it's dangerous.
"""))

cells.append(code(r"""
# Exercise 1 — re-weight recall for a support/scheduling domain.
"""))

cells.append(code(r"""
# Exercise 2 — probe the dedupe threshold with paraphrases.
"""))

cells.append(code(r"""
# Exercise 3 — add evict(max_age_hours) that protects critical facts.
"""))

cells.append(code(r"""
# Exercise 4 — vary the recency half-life and re-rank.
"""))

cells.append(md(r"""
## Next

- **You built the toy; here's the real one:** [`../../../blueprints/memory-module/`](../../../blueprints/memory-module/) — the production layered memory (short-term compaction + long-term ranked recall + reflective writes + consolidation + skill library) behind a clean interface, backed by a real Ch 13 vector store.
- **Next notebook:** [`14-03-durable-state-checkpointing.ipynb`](./14-03-durable-state-checkpointing.ipynb) — *state* (surviving crashes) as a separate concern from *memory* (what the model sees).
- **Capstone:** this is the `capstone/memory/` module — checkpoint `checkpoints/ch14-memory`.
"""))

out = write_nb(os.path.join(HERE, "14-02-long-term-memory-recall-reflection.ipynb"), cells)
print("wrote", out)
