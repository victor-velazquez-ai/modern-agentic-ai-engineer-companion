# Blueprint — Agent Loop  (pattern)

> Realizes book Ch 12, 16 · mirrors capstone `agents/raw/` · Status: 📋 planned (Phase 1)

## What it is
A framework-free, **tool-using agent loop** you can read top to bottom: the `observe → decide →
act → observe` cycle implemented directly against a model client, with no orchestration library
hiding the control flow. It owns the message ledger, the tool-call dispatch, the stop conditions,
and the failure handling that every higher-level agent reuses.

## Why a blueprint (not a notebook)
- The Ch 12 notebook builds a *toy* loop to teach the cycle; this is the **hardened version** a
  senior would actually ship — and four later chapters (20/25/46/47) reuse its hardening.
- It must be **importable** by other blueprints and the capstone (`multi-agent-supervisor`'s
  workers are agent loops), so it has to be a real package with a stable surface, not cells.
- The interesting parts — turn caps, tool-error recovery, parallel tool calls, cancellation —
  only make sense as tested code, not narrated snippets.

## Planned structure
```text
agent-loop/
├── README.md                  # what it is, the loop diagram, trade-offs, how to adapt
├── pyproject.toml             # installable package; pinned to repo requirements
├── src/agent_loop/
│   ├── __init__.py
│   ├── loop.py                #   the core run loop (turn cap, stop conditions)
│   ├── messages.py            #   typed message/turn ledger (system/user/assistant/tool)
│   ├── tools.py               #   Tool protocol: schema + safe executor + dispatch
│   ├── errors.py              #   tool-error recovery, retries, malformed-call repair
│   └── model.py               #   thin model port (impl provided by llm-gateway; MOCK default)
├── tests/
│   ├── test_loop.py           #   single-turn, multi-turn, max-turns guard
│   ├── test_tools.py          #   dispatch, bad args, parallel calls
│   └── test_recovery.py       #   model emits invalid tool call → loop recovers
└── demo.py                    # runnable: a 2-tool agent (calculator + clock) in MOCK mode
```

## Composes / depends on
- **`llm-gateway`** — supplies the model port (`model.py` is the seam; `agent-loop` ships a mock
  so it runs standalone, and accepts a real gateway client by injection).
- Otherwise **foundational** — the lowest-level pattern; most other blueprints build on it.

## Maps to the book
- **Ch 12 — Tool Use & Function Calling:** the tool schema, the call/result protocol, the loop.
  Makes §12's 🔧 Build sections real.
- **Ch 16 — Agent Reasoning Patterns:** ReAct / plan-execute / reflection are *strategies layered
  on this loop*; the blueprint is the substrate those patterns drive.
- **`learn/` walkthrough:** [`../../learn/part-04-building-blocks-of-agents/12-tool-use-and-function-calling/`](../../learn/part-04-building-blocks-of-agents/12-tool-use-and-function-calling/)
  builds the toy loop and **ends by pointing here** for the production version.

## Maps to the capstone
Standalone version of capstone **`agents/raw/`** — the no-framework agent loop (Ch 12). The
capstone wires it to real tools and the gateway; this blueprint is the same core, isolated.

## Phase-2 definition of done
- [ ] `pytest tests/` passes; loop, dispatch, and recovery all covered.
- [ ] `python demo.py` runs end to end in **`MOCK=1`** (no API spend), shows a multi-tool turn.
- [ ] README explains the trade-offs: when raw-loop beats a framework, turn-cap tuning, the
      tool-error-recovery policy, and the `model.py` injection seam.
- [ ] Relative cross-links (to `llm-gateway`, the Ch 12 walkthrough, capstone `agents/raw/`) resolve.
