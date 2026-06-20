# Part I — The Agentic Landscape & Mindset

> Companion to **Modern Agentic AI Engineer**, Part I · book chapters 1–3
> Status: 📋 planned (Phase 1)

## Companion emphasis

Part I is **orientation, not construction.** Its job is to install the mental models the rest
of the book (and this repo) hangs on — so the companion here stays deliberately light: two
short, fully-offline **concept labs** that make the big ideas *tangible*, plus the
reference/worksheet material that explains how to drive the book and this repo together. No
API keys, no cost, no framework — just enough running code to *feel* the difference between a
model that talks and a system that acts, and to see one request flow through the four planes.

These chapters set up two through-lines the whole repo honors:

- **Agent = model + loop + tools + guardrails.** Ch 1's tiny loop is the seed that grows into
  `blueprints/agent-loop/` and `capstone/agents/`.
- **Build the capstone yourself.** Ch 2 carries the pedagogy guardrail: the labs and the
  `capstone/` answer key exist to help you *build and understand*, never to skip the work.

## Chapters

| Ch | Title | Companion note | Plan |
|---|---|---|---|
| 1 | Why Agentic AI, and Why Now | Concept lab — talker-vs-doer: wrap a frozen model in a minimal reason→act→observe loop and score it against the four agentic properties (offline). | [`01-why-agentic-ai/PLAN.md`](01-why-agentic-ai/PLAN.md) |
| 2 | How to Use This Book | Reference/worksheet-only — how to use *this repo* alongside the book (book↔repo map, reading paths, the `MOCK` covenant) + an optional self-assessment worksheet. No notebook by design. | [`02-how-to-use-this-book/PLAN.md`](02-how-to-use-this-book/PLAN.md) |
| 3 | The Mental Model of a Modern AI System | Concept lab — trace one request through the four planes (model · orchestration · data · infrastructure) and name the force traded at each hop (offline). | [`03-mental-model/PLAN.md`](03-mental-model/PLAN.md) |

## Run order

`01-01-talker-vs-doer` → `03-01-four-planes-traced` are the two recommended **first
notebooks** in the entire repo (both run with no key, no services). Ch 2 is read-alongside
orientation; do its self-assessment worksheet first if you want a personalized reading plan
before you start.
