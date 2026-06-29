# Part III — The LLM Substrate

> Companion to **Modern Agentic AI Engineer** · Chapters 8–11
> Status: 📋 planned (Phase 1) — `PLAN.md` per chapter; notebooks land in Phase 2.

Every agent you build in the rest of this book sits on one component: the language model. Part
III is where you stop treating it as magic and start treating it as a *substrate* you can predict,
control, and pay for deliberately — how the model works, how to steer its output, how to write
prompts as engineering artifacts, and how to talk to the API like the external dependency it is.

## Why this part is rich in concept-labs

Part III is the most *intuition-heavy* stretch of the book, so the companion leans into
**concept-labs** (NOTEBOOK-STANDARDS §1) over big builds: small, fast, mostly-offline cells with a
🔮 *predict-then-run* moment, designed to make an abstract idea tangible. You'll watch a tokenizer
split your own text and explain the bill, see two unrelated sentences land close in vector space,
reshape a probability distribution and feel temperature change the draw, and clock TTFT against
decode rate. Chapters 10–11 then turn engineering: prompts become versioned, tested artifacts, and
the chapter 🔧 *Builds* — the `PromptRegistry` and the single-door `LLMClient` — graduate from a
notebook into the repo's `templates/` and `blueprints/`.

Because these notebooks touch real model APIs, every one is **offline-first**: a
`MOCK=1` default (NOTEBOOK-STANDARDS §3) returns canned, realistic responses so the lab runs free
and deterministically, with the live `MOCK=0` path and its token cost documented in the setup cell.
Each `PLAN.md` states exactly what's offline vs live.

## Chapters in this part

| Ch | Title | Companion emphasis | Notebooks | Feeds | Plan |
|---|---|---|---|---|---|
| 08 | How LLMs Actually Work | Concept-labs — tokenizers & the token bill, embeddings/cosine intuition, context window & "lost in the middle" | 3 (concept-lab) | — (foreshadows `rag-pipeline/`) | [PLAN](08-how-llms-work/PLAN.md) |
| 09 | Inference, Sampling & Control | Concept-labs — decoding knobs live, determinism/seeds/replay, streaming + TTFT/decode economics | 3 (concept-lab) | — (foreshadows `llm-client/`) | [PLAN](09-inference-sampling-control/PLAN.md) |
| 10 | Prompt Engineering as Engineering | Walkthroughs — techniques that matter, structured output + repair, 🔧 versioned prompt registry + evals | 3 (walkthrough) | `templates/prompt-template/`; capstone `prompts/` | [PLAN](10-prompt-engineering/PLAN.md) |
| 11 | Working with Model APIs | Walkthroughs — SDK shapes & the response, retries/idempotency, 🔧 caching/batching + the `LLMClient` | 3 (walkthrough) | `blueprints/llm-gateway/`; capstone `llm/` | [PLAN](11-working-with-model-apis/PLAN.md) |

## How to work through it

1. **Read the chapter, then run its notebooks** in order (`08-01` → `08-02` → …). The labs assume
   you've read the matching book sections — they make the chapter's ideas *tangible*, not
   substitute for it.
2. **Predict before you run.** Every 🔮 prompt is the point; guess the output, then check.
3. **Start free.** Leave `MOCK=1` on for the first pass; flip to `MOCK=0` only when you want to see
   the real model, and watch the token cost noted in setup.
4. **Follow the builds onward.** Chapters 10–11 end by pointing at the production version of what you
   built — the prompt template and the `llm-client` blueprint / capstone `llm/`. That's the
   "you built the toy; here's the real one" handoff.

## See also

- [`docs/REPO-PLAN.md`](../../docs/REPO-PLAN.md) — the master plan and the full chapter→asset map.
- [`docs/NOTEBOOK-STANDARDS.md`](../../docs/NOTEBOOK-STANDARDS.md) — the authoring contract every
  notebook follows (skeleton, mock modes, the "would a senior have written this?" checklist).
- [`docs/CONVENTIONS.md`](../../docs/CONVENTIONS.md) — naming, the canonical `PLAN.md` template, and
  the callout grammar mirrored from the book.
- **Next part:** [`part-04-building-blocks-of-agents/`](../part-04-building-blocks-of-agents/) —
  where the substrate becomes an agent (tool use, RAG, memory, structured reliability).
