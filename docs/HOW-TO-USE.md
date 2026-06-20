# How to Use This Companion

A short guide to getting the most out of the repo without falling into the trap the book
warns about: **consuming instead of building.**

---

## The one rule

> **Build first. Compare second.** When a chapter has a 🔧 *Build* section, do it yourself
> in your own repo. Use the notebook here to *understand* the idea, the blueprint to see a
> production version, and the capstone checkpoint to *check* your work — never to skip it.
> Typing and debugging is where the skill forms.

---

## The four pillars — when to reach for each

- **📓 `learn/` notebooks** — when you want to *understand* a concept by running it. Open the
  chapter you're reading, run the notebook cell by cell, and do the 🔮 predict prompts before
  each output. Then change something and rerun.
- **🧩 `blueprints/`** — when you're *building something real* and want a senior-grade
  reference for a pattern (RAG, evals, MCP, memory, observability). Read it, understand the
  trade-offs, adapt it. Don't paste it blind.
- **🛠️ `templates/`** — when you're *starting a new project* (often at work) and want a sane
  scaffold in minutes. Copy the folder, follow the TODOs.
- **🏗️ `capstone/`** — when you want to see how *all* of it fits together, or you're stuck on
  a Build section and need a known-good checkpoint to diff against.

---

## Reading paths (mirror the book)

- **Cover-to-cover (zero → master):** read the chapter, run its `learn/` notebooks, do the
  Build in your own repo, diff against the checkpoint. Repeat. Parts I → XIII.
- **Already strong in SWE:** skim Part II's notebooks as drills; go deep from Part III.
- **Already strong in agents:** jump to Parts VII–XI; lean on `blueprints/` and `templates/`
  for backend/cloud/architecture.
- **Just need a reference:** ignore the order — go straight to the blueprint or template you
  need. That's a valid use too.

---

## Cost-free by default

Every notebook runs in **`MOCK=1`** mode out of the box: model calls return realistic canned
responses, so notebooks execute free, offline, and deterministically. Set `MOCK=0` (and add
your API key to `.env`) only when you want real model output — each such notebook documents
its approximate token cost in the setup cell. See [`SETUP.md`](SETUP.md).

---

## How this maps to your copy of the book

The book prints a 📓 *Companion* pointer at each Build section and major concept, naming the
exact notebook/blueprint/checkpoint. The repo is **pinned by release tag** to your edition —
the front matter tells you which tag (`git checkout vX.Y.Z`) matches the code in your book,
while `main` has the latest.
