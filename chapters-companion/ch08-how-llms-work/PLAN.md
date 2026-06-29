# Ch 08 — How Large Language Models Actually Work

> Companion plan · Part III · book file `chapters/08-how-llms-work.typ`
> Status: 📋 planned (Phase 1)

## Role in the companion
This is the substrate chapter, and it is pure intuition-building — so it gets **concept-labs**,
not a build. Reading tells you an LLM is "next-token prediction" and "meaning is geometry";
running lets the reader *watch* a tokenizer split their own text, *see* two unrelated sentences
land close in vector space, and *feel* why mid-context facts get lost. Everything later in the
repo (RAG, memory, agents) is an expansion of one mechanism introduced here; these notebooks make
that mechanism tangible and cheap to poke at.

## Planned notebooks

### 08-01 · `08-01-tokens-and-the-bill.ipynb` — Tokenizers, and why you pay per token
- **Type:** concept-lab
- **Maps to:** book §8.2 (tokens, tokenizers, and why they matter)
- **Objective:** count tokens with the *right* tokenizer and explain a model's letter-counting /
  multilingual-cost quirks from how text is chunked.
- **Prereqs:** none (first runnable notebook in Part III; Ch 8 read).
- **Cell arc:**
  - 🧠 mental model: the model reads token chunks, never characters or words.
  - Encode "unbelievable", "the", a 429-error sentence with `tiktoken` (`o200k_base`); inspect ids
    and the ~4-chars-per-token rule of thumb.
  - 🔮 *predict* the token count of an English vs a non-English sentence, then measure the
    multilingual cost multiplier.
  - Show why "count the r's in strawberry" / reversing a string is hard — only token chunks exist.
  - Note Anthropic exact counts come from `client.messages.count_tokens(...)`, not a local approx.
  - ⚠️ pitfall: estimating tokens by word/char count, or budgeting with one provider's tokenizer
    while calling another's model — overflow or a blown cost forecast.
- **Datasets/fixtures:** a handful of in-notebook strings (English, non-English, code, long number).
- **APIs & cost:** none/offline — `tiktoken` is local; the Anthropic counting endpoint is named but
  gated behind `MOCK=0` (a few free-tier count calls if run live).
- **You'll be able to:** count tokens correctly and trace cost/context limits back to tokenization.

### 08-02 · `08-02-meaning-is-geometry.ipynb` — Embeddings & cosine similarity
- **Type:** concept-lab
- **Maps to:** book §8.3 (embeddings and vector-space intuition)
- **Objective:** see that semantically similar texts land near each other in vector space, measured
  by cosine similarity — the trick that powers search-by-meaning.
- **Prereqs:** 08-01.
- **Cell arc:**
  - 🧠 mental model: training never defines "similar"; it emerges from the prediction objective.
  - Implement `cosine(a, b)` from scratch (dot / norms) on tiny hand-made vectors first.
  - 🔮 *predict* which is closer: "How do I reset my password?" vs "I can't log in" vs an unrelated
    sentence — then embed and check (matches the book's example pair).
  - Rank a small set of sentences against one query by cosine; eyeball the "search by meaning" win
    over keyword overlap.
  - Foreshadow RAG (Ch 13) and memory (Ch 14): every chunk becomes a vector, queries match by
    proximity; a vector DB is "just an index for nearest vectors."
  - ⚠️ pitfall: comparing vectors from *different* embedding models, or forgetting to normalize.
- **Datasets/fixtures:** ~6 short in-memory sentences; no external corpus.
- **APIs & cost:** mockable — `MOCK=1` ships small canned embedding vectors so cosine math runs
  deterministically and free; `MOCK=0` calls a real embeddings endpoint (≈ a few cents of tokens).
- **You'll be able to:** explain why retrieval is geometric and read a cosine score with intuition.

### 08-03 · `08-03-context-and-lost-in-the-middle.ipynb` — Context window & attention pressure
- **Type:** concept-lab
- **Maps to:** book §8.1 (transformers/attention, lightly), §8.5 (context windows, "lost in the
  middle")
- **Objective:** build intuition for why long context costs more and why a fact's *position* in the
  prompt changes whether the model uses it.
- **Prereqs:** 08-01.
- **Cell arc:**
  - 🧠 mental model: attention lets every token look at every prior token; cost grows ~quadratically
    with length, so long contexts leak out as price and latency.
  - A tiny offline simulation: a toy attention-weight matrix over a short sequence to *see* "every
    position attends to every earlier position" (illustrative, not a real transformer).
  - A "needle in a haystack" demo: plant one fact at the start, middle, and end of a long filler
    context; 🔮 *predict* which position is recovered most reliably.
  - Run the retrieval (mock returns a canned position-dependent answer pattern) and read the
    *lost-in-the-middle* effect; discuss why "it fits in the window" ≠ "the model will use it."
  - 🎯 senior lens: curate the relevant ten chunks (Ch 13) and place key facts first/last; treat
    every prompt token as something that must earn its place.
  - ⚠️ pitfall: dumping a whole wiki into a long context and shipping — quality quietly degrades as
    cost and latency triple.
- **Datasets/fixtures:** generated filler text + one planted fact (built by a cell, not committed).
- **APIs & cost:** offline by default (toy attention + mocked needle test); `MOCK=0` optionally runs
  the needle test against a real long-context model (token cost scales with the filler — flagged).
- **You'll be able to:** justify "curated context beats voluminous context" and position facts well.

## Feeds (cross-pillar)
- **Blueprint(s):** — (conceptual). Embeddings intuition here underpins
  [`blueprints/rag-pipeline/`](../../blueprints/rag-pipeline/) later; not built from this chapter.
- **Template(s):** —
- **Capstone:** no code yet. Establishes the substrate the capstone's `llm/` client (Ch 11) and
  `rag/` (Ch 13) assume — model-as-swappable-component and embeddings-as-RAG-backbone.

## Dependencies
- None hard. Recommended first Part III notebooks; Ch 9–11 build directly on this intuition.

## Phase-2 definition of done
- [ ] All three notebooks run top-to-bottom in `MOCK=1` fully offline (tokenizer local; embeddings
      and needle-test responses canned), deterministically.
- [ ] Tokenization, cosine-similarity, and "lost in the middle" terminology match the book's §8.
- [ ] Each notebook ends with recap + 2–3 exercises; secrets (if `MOCK=0`) read from env only.
- [ ] Live paths document approximate token cost; offline vs live is explicit in the setup cell.
