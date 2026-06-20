# 🧩 Blueprints — reference implementations

Production-grade, self-contained implementations of the **recurring patterns** the book
returns to. Unlike the `learn/` notebooks (which teach a concept in isolation), a blueprint is
a real package — modules, `tests/`, a README that explains the trade-offs, and a tiny runnable
demo — structured the way a senior engineer actually would.

> **The rule: study & adapt, not copy-paste.** The book's promise is that *you build the
> capstone yourself*; typing and assembling is what creates understanding. Blueprints are the
> "how a senior would structure this" reference you **lift ideas from and adapt** to your own
> system — not an answer key to clone. Every blueprint runs **free and offline in `MOCK=1`** (no
> API spend), so you can read it *by running it*. (See [`../docs/REPO-PLAN.md`](../docs/REPO-PLAN.md)
> §1, the pedagogy guardrail.)

---

## Two tiers

The catalog has two layers, and the second rests on the first:

- **Pattern blueprints** — the reusable *mechanisms*. Each isolates one capability (an agent
  loop, a retrieval pipeline, an eval harness) cleanly enough to drop into any project. These
  are the parts.
- **Solution blueprints** — the twelve **Appendix-G** use cases companies actually pay for.
  Each is a recipe (*Solves · Approach · Build · Pitfalls*) made runnable by **composing pattern
  blueprints** — retrieval + tools + memory + evals + guardrails recombined for a specific job.
  These are the products. *(Owned by a sibling Phase-1 plan; folders land alongside the patterns.)*

```text
                        ┌─────────────────── SOLUTION blueprints (Appendix G) ───────────────────┐
   customer-support · internal-knowledge · document-extraction · contract-review · text-to-sql ·
   sales-revops · incident-response · research-due-diligence · software-engineering · content-
   production · product-copilot · compliance-monitoring
                        └───────────────────────────── compose ▼ ──────────────────────────────┘
   agent-loop · llm-gateway · rag-pipeline · memory-module · multi-agent-supervisor ·
   mcp-server · eval-harness · observability-stack
                        └──────────────────── PATTERN blueprints (the parts) ───────────────────┘
```

---

## Pattern blueprints (the parts)

The eight reusable mechanisms. These names are **canonical** — chapter and notebook plans link
to exactly these slugs.

| Blueprint | What it is | Realizes (Ch) | Mirrors capstone |
|---|---|---|---|
| [`agent-loop/`](agent-loop/PLAN.md) | Framework-free tool-using agent loop you can read end to end | 12, 16 | `agents/raw/` |
| [`llm-gateway/`](llm-gateway/PLAN.md) | The model-access layer: thin SDK client **plus** routing, fallbacks, caching, cost-metering, guards | 11, 39–41 | `llm/` |
| [`rag-pipeline/`](rag-pipeline/PLAN.md) | chunk → embed → retrieve → rerank hybrid retrieval | 13 | `rag/` |
| [`memory-module/`](memory-module/PLAN.md) | Layered short/long-term memory + persistence | 14 | `memory/` |
| [`multi-agent-supervisor/`](multi-agent-supervisor/PLAN.md) | Supervisor that plans and delegates to specialist workers | 17 | `agents/` |
| [`mcp-server/`](mcp-server/PLAN.md) | An MCP server exposing tools/resources + safe consumption | 19 | `mcp/` |
| [`eval-harness/`](eval-harness/PLAN.md) | Golden sets + graders + LLM-judge + CI quality gate | 22 | `evals/` |
| [`observability-stack/`](observability-stack/PLAN.md) | OTel tracing of agent runs + cost/token accounting | 23 | `observability/` |

> **Naming note — `llm-client` → `llm-gateway`.** Earlier chapter/notebook plans referenced a
> `blueprints/llm-client/`. That name is **superseded by `llm-gateway`**, which is the same
> blueprint scoped to its full job: the **base client** is the Ch 11 layer (one door to the SDK:
> retries, streaming, usage); the **gateway** wraps it with the Ch 39–41 layers (routing,
> fallbacks, exact + semantic cache, cost-metering, guardrails). Treat any `llm-client` link as
> pointing here. *(Orchestrator: this is the one slug to reconcile across pillars.)*

---

## Solution blueprints (the products — Appendix G)

Twelve high-value agentic solutions, each **composing** the pattern blueprints above. Slugs and
ownership come from [`../learn/appendices/PLAN.md`](../learn/appendices/PLAN.md) (the Appendix-G
map); these folders are authored by the **sibling solution-blueprints plan**.

| # | Use case (Appendix G) | Core pattern | Blueprint | Composes (patterns) |
|---|---|---|---|---|
| 1 | Customer-support agent | RAG + tools + HITL escalation | [`customer-support-agent/`](customer-support-agent/) | rag-pipeline · agent-loop · eval-harness |
| 2 | Internal knowledge assistant | Permissioned RAG | [`internal-knowledge-assistant/`](internal-knowledge-assistant/) | rag-pipeline · agent-loop · observability-stack |
| 3 | Intelligent document processing | Extraction + schema validation | [`document-extraction-pipeline/`](document-extraction-pipeline/) | llm-gateway · eval-harness |
| 4 | Contract & legal review | Extraction + RAG + HITL redline | [`contract-review-assistant/`](contract-review-assistant/) | rag-pipeline · agent-loop · eval-harness |
| 5 | Talk-to-your-data analytics | Text-to-SQL over a warehouse | [`text-to-sql-analytics/`](text-to-sql-analytics/) | agent-loop · eval-harness · observability-stack |
| 6 | Sales & RevOps automation | Tool use + summarization | [`sales-revops-automation/`](sales-revops-automation/) | agent-loop · mcp-server |
| 7 | Ops & incident-response copilot | RAG runbooks + scoped tools + HITL | [`incident-response-copilot/`](incident-response-copilot/) | rag-pipeline · agent-loop · observability-stack |
| 8 | Research & due-diligence agent | Multi-agent + cited RAG | [`research-due-diligence-agent/`](research-due-diligence-agent/) | multi-agent-supervisor · rag-pipeline |
| 9 | Software-engineering agents | Tool use + multi-agent + CI gates | [`software-engineering-agent/`](software-engineering-agent/) | multi-agent-supervisor · agent-loop · eval-harness |
| 10 | Content production pipeline | Workflow + brand guardrails | [`content-production-pipeline/`](content-production-pipeline/) | agent-loop · eval-harness · llm-gateway |
| 11 | Customer-facing product copilot | In-app RAG + scoped tools | [`product-copilot/`](product-copilot/) | rag-pipeline · agent-loop · observability-stack |
| 12 | Compliance & monitoring agent | Classification + audit trail + HITL | [`compliance-monitoring-agent/`](compliance-monitoring-agent/) | llm-gateway · eval-harness · observability-stack |

*(Compose columns are the expected dependencies; the sibling plan owns the final wiring.)*

---

## Pattern → where it comes from in the book

Each pattern blueprint is the standalone, hardened version of a capstone module. Its `learn/`
walkthrough builds a *toy* of the same mechanism and then points here for "the real one."

| Pattern blueprint | Primary chapter(s) | `learn/` walkthrough that points here | Capstone dir it standalone-izes |
|---|---|---|---|
| `agent-loop` | Ch 12 (built), Ch 16 (reasoning) | `learn/part-04-…/12-tool-use-and-function-calling/` | `agents/raw/` |
| `llm-gateway` | Ch 11 (base client), Ch 39–41 (gateway) | `learn/part-03-…/11-working-with-model-apis/` | `llm/` |
| `rag-pipeline` | Ch 13 | `learn/part-04-…/13-retrieval-augmented-generation/` | `rag/` |
| `memory-module` | Ch 14 | `learn/part-04-…/14-memory-and-state/` | `memory/` |
| `multi-agent-supervisor` | Ch 17 | `learn/part-05-…/17-multi-agent-systems/` | `agents/` (`supervisor.py`) |
| `mcp-server` | Ch 19 | `learn/part-05-…/19-mcp-and-tool-ecosystems/` | `mcp/` |
| `eval-harness` | Ch 22 (reused 41/43/45/47/48) | `learn/part-06-…/22-evaluation-and-quality/` | `evals/` |
| `observability-stack` | Ch 23 | `learn/part-06-…/23-observability-for-agents/` | `observability/` |

**Reuse beyond the home chapter.** The hardening in `agent-loop` is reused by the multimodal,
voice, and computer-use chapters (20/25/46/47). `eval-harness` is the quality gate other
chapters import (41/43/45/47/48). The book's reference-architectures chapter (Ch 43) and the
Appendix-G playbook cross-link these blueprints rather than re-explaining the parts.

---

## Status

📋 **Phase 1 — planning.** Each pattern folder currently holds a `PLAN.md` only. Phase 2 fills
in modules, `tests/`, demos, and READMEs (built early, since the `learn/` walkthroughs and the
solution blueprints import from them). See [`../docs/REPO-PLAN.md`](../docs/REPO-PLAN.md) §5.
