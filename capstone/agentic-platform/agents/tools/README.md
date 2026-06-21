# `agents/tools/` — schemas, risk tiers, safe executors, and the model seam

The shared foundation every agent variant (`raw/`, `graph/`, `pydantic_ai/`) and the supervisor
build on. If `agents/` has one "library," it is this package. Built across Ch 12 (the loop's tools
and ledger), Ch 19 (tools exposed to/from MCP), and Ch 20 (risk tiers).

## What's here

| Module | Responsibility |
|---|---|
| `messages.py` | The typed, provider-neutral, append-only **transcript** — the substrate every runner shares. |
| `schemas.py` | `ToolSpec` (the model-facing schema), `RiskTier`, `Tool`, and the `ToolRegistry` dispatch table — the **safe executor**: a bad call becomes a model-readable error result, never a crash. |
| `executors.py` | The platform's **concrete tools**: `calculator` (a safe AST evaluator, *never* `eval`), `clock`, `search_docs` (the seam to `rag/`), `create_ticket` (`WRITE`), `send_email` (`EXTERNAL`, gated). |
| `model.py` | The one **`ModelPort`** seam every call goes through; `MockModel` is the deterministic offline default. |
| `errors.py` | Malformed-tool-call **repair** and the consecutive-failure **retry policy** (pure, unit-testable). |

## The two design rules

- **A tool is schema + function + risk.** The risk tier lives next to the schema (in `schemas.py` /
  on each executor), so "how dangerous is this tool" is a reviewable property of the tool, not a
  policy scattered across the codebase. `approvals.py` reads `registry.risk_of(name)` and decides.
- **Fail soft at run time, fail fast at construction.** Duplicate tool names raise on registry
  build (a programming error). A bad *call* from the model — unknown tool, missing args, a tool
  that raised — returns an error `ToolResult` the model can read and retry from. Deeper input
  policy belongs to the `llm/gateway.py` guards and `security/`; a raw loop fails soft.

## Safe executors

`calculator` is the worked example of "never hand model output to `eval`": it parses an AST and
permits only numeric literals and `+ - * / % **`, so a prompt-injected `__import__('os')` cannot
ride in through a math tool. `search_docs` is read-only and decoupled from `rag/` behind a
`Retriever` callable (offline canned hits by default; inject the real retriever for the live
corpus). `create_ticket` and `send_email` demonstrate the `WRITE` and `EXTERNAL` tiers the
approval gate enforces.

## Mirrors the blueprint

This package duplicates (not imports) the shape of
[`blueprints/agent-loop`](../../../../blueprints/agent-loop/)'s `messages.py` / `tools.py` /
`model.py` / `errors.py`, extended with `RiskTier` and the concrete executors. The capstone is a
self-contained deliverable; comparing this package against the blueprint *is* the lesson.
