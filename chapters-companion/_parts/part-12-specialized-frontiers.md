# Part XII — Specialized Frontiers (Ch 45–49)

> 📓 Companion to **Modern Agentic AI Engineer** · Part XII · `learn/part-12-specialized-frontiers/`
> Status: 📋 planned (Phase 1) — these folders hold `PLAN.md` files; notebooks land in Phase 2.

## What this part adds to the book

Part XII takes the agent loop you've built all book and pushes it to the edges of what an agent
can perceive, do, and become — **multimodal** input, **voice/realtime** interaction,
**computer-use** of any screen, **customizing** the model itself, and finally a system for
**staying current** as the frontier moves. The through-line is the one the chapters keep
making: *these are new adapters and harnesses around an unchanged core, not new cores.* Vision
is an input type, voice is a transport wrapper, computer-use is a screen in the same loop,
fine-tuning is a portfolio decision — and the durable engineering value lives in the parts you
build around the model (the verification gate, the latency budget, the sandbox, the eval), not
in the model call providers ship.

So this part is deliberately **mock-first and safety-first**, more than any other:

- **Multimodal (45)** — you don't read "models can see"; you build a document-extraction
  **pipeline with a verification gate** and catch the model's confident-but-wrong digit yourself.
- **Voice (46)** — a kernel can't carry a phone call, so you drive a **mocked realtime stream**
  and implement endpointing + barge-in + a per-stage latency budget — the skills that actually
  decide whether a voice agent feels alive.
- **Computer-use (47)** — the highest-blast-radius capability in the book, so it is **sandboxed
  and dry-run by default**: the loop runs against a mock display, every irreversible action is
  human-gated, and the lesson is *the harness is the product*.
- **Customizing models (48)** — leads with a runnable **triage** (prompt vs RAG vs fine-tune,
  decided on a measured plateau); the LoRA fine-tune is **clearly optional and heavy** ⚠️ with a
  fully-mocked default, and DPO/distillation/agentic-RL stay conceptual.
- **The frontier (49)** — **reference + worksheet, no notebook**: a system for reading papers and
  tracking the field, where a notebook would be theatre.

Everything runs **offline and free** by default (`MOCK=1`); live APIs, real audio, a real
browser, and GPU training are all **opt-in, ⚠️-flagged, and skipped in CI**.

## ⚠️ This is the "name it when the medium fights the artifact" part

Following the repo's rule (also seen in Part IX): completeness means the **right asset per
chapter, not a forced notebook everywhere**. Three chapters here bend that way deliberately —

- **Ch 49 ships no notebook at all.** Reading papers and tracking the ecosystem aren't kernel
  work; the honest artifacts are a curated `REFERENCE.md` and a fill-in `tracking-system.worksheet.md`.
- **Ch 46's real-audio path and Ch 48's real LoRA fit are opt-in heavy paths.** The default
  notebooks teach the runnable, language-agnostic core (the session/turn-taking model; the
  triage and what LoRA changes) and gate the expensive part behind a clearly-flagged `MOCK=0`.
- **Ch 47 never touches your real browser or the open web.** The harness — sandbox, allowlist,
  set-of-marks grounding, per-step verification, confirmation gates — is the teaching surface,
  built against a mock display.

## Chapters in this part

| Ch | Title | Companion emphasis | Notebooks | Plan |
|---|---|---|---|---|
| 45 | Multimodal Agents | Concept-lab — every modality as a "context-in / tool-out" adapter on the unchanged loop; then a 🔧 **document-extraction pipeline with a verification gate** (schema + arithmetic cross-check + human-queue routing, injection-aware) and a field-level accuracy eval | 2 | [PLAN](45-multimodal-agents/PLAN.md) |
| 46 | Voice & Realtime Agents | Concept-lab — cascaded vs speech-to-speech + the latency budget; then a 🔧 **realtime session loop on a mocked stream** (endpointing, barge-in = cancel generation *and* playback, per-stage latency). Real audio optional ⚠️ | 2 | [PLAN](46-voice-and-realtime-agents/PLAN.md) |
| 47 | Computer-Use & Browser Agents | Walkthrough — a 🔧 **sandboxed, dry-run computer-use loop** (allowlist, caps, audit trail, human-gated irreversible actions) + a concept-lab on the **grounding ladder** (set-of-marks, verify-and-replan) and a frozen task-success harness. **Sandboxed/dry-run by default** ⚠️ | 2 | [PLAN](47-computer-use-and-browser-agents/PLAN.md) |
| 48 | Customizing Models | Concept-lab — a runnable **prompt-vs-RAG-vs-fine-tune triage**; then an **optional/heavy** ⚠️ LoRA/PEFT walkthrough on a small/local model (mock-first), with DPO, distillation, and the agent-training ladder kept **conceptual** | 2 | [PLAN](48-customizing-models/PLAN.md) |
| 49 | The Frontier & Staying Current | **Reference + worksheet — no notebook (by design).** A curated `REFERENCE.md` (paper-reading method, hype filter, durable directions) + a `tracking-system.worksheet.md` you fill in for your own stack | 0 | [PLAN](49-frontier-and-staying-current/PLAN.md) |

## Feeds at a glance

- **Blueprints / Templates / Capstone:** *none owned by this part.* Part XII is the frontier
  layer — its assets are adapters and harnesses on the core the earlier parts already built. The
  notebooks point back to the existing [`blueprints/agent-loop/`](../../blueprints/agent-loop/)
  (the brain that voice wraps and computer-use extends) and reuse the
  [`blueprints/eval-harness/`](../../blueprints/eval-harness/) discipline for extraction accuracy
  (45), computer-use task-success (47), and the eval that gates every customization (48). Where a
  frontier capability would land in the capstone — a vision/extraction tool, a realtime transport,
  a computer-use tool behind a human gate — each PLAN names the `capstone-project/agents/tools/` (or
  serving) seam rather than adding a new module.

## Suggested path

These chapters are **independent frontiers** — read the one your work needs; there's no
compounding chain as in Part IV. All of them assume the **agent core** (Ch 12 tool loop, Ch 14
memory, Ch 20 human-in-the-loop, Ch 22 evals, Ch 41 safety) is already in place, since every
chapter here is a wrapper around it. If you read just one: **45** is the most broadly useful
(extraction-with-verification is a pattern you'll reach for constantly), and **49** is the one to
end on — it reframes the whole book as "fundamentals depreciate slowly; look up the fast layer."

See [`docs/REPO-PLAN.md`](../../docs/REPO-PLAN.md) for the full chapter→asset map and
[`docs/CONVENTIONS.md`](../../docs/CONVENTIONS.md) for the `PLAN.md` template these follow.
