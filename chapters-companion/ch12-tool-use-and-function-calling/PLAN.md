# Ch 12 — Tool Use & Function Calling

> Companion plan · Part IV · book file `chapters/12-tool-use-and-function-calling.typ`
> Status: 📋 planned (Phase 1)

## Role in the companion
This is the chapter where an LLM stops being a text generator and starts *acting*. The
notebooks make the tool-use loop concrete: the reader builds a working agent loop **with no
framework**, sees exactly where the model decides, where *their* code runs, and how the two
take turns. It's the first taste of the capstone's `agents/raw/` and the foundation every
later chapter (RAG, memory, multi-agent, MCP) builds on.

## Planned notebooks

### 12-01 · `12-01-anatomy-of-a-tool-call.ipynb` — The tool-use loop, traced
- **Type:** concept-lab
- **Maps to:** §12.1 (🧠 the tool-use loop), §12.2 (designing good tools)
- **Objective:** read a single round-trip of a tool call and name every part (tool schema,
  model's tool-use request, your executor, the tool-result message back to the model).
- **Prereqs:** Ch 11 (model APIs); `learn/part-03-llm-substrate/11-*`.
- **Cell arc:**
  - 🧠 mental model: model ↔ tools ↔ environment as a turn-based loop (diagram).
  - Define one tiny tool schema (a calculator) and inspect its JSON shape.
  - Send a prompt; 🔮 *predict* whether the model answers or asks to call the tool.
  - Dissect the `tool_use` block the model returns.
  - Run the tool by hand; feed the `tool_result` back; get the final answer.
  - ⚠️ pitfall: vague tool descriptions → wrong/no tool calls (show a bad vs good schema).
- **Datasets/fixtures:** none (a pure-function calculator tool).
- **APIs & cost:** mockable (`MOCK=1` returns a canned tool-use block); live ≈ 2 short calls.
- **You'll be able to:** explain the loop and read a raw tool-use response without a framework.

### 12-02 · `12-02-tool-loop-from-scratch.ipynb` — 🔧 Build a tool-using agent (no framework)
- **Type:** walkthrough  *(this is the chapter's 🔧 Build)*
- **Maps to:** §12.4 (🔧 Build: first tool-using agent from scratch), §12.3 (safe execution)
- **Objective:** build a reusable `while`-loop agent that registers tools, routes the model's
  requests to executors, loops until the model is done, and stops safely.
- **Prereqs:** 12-01.
- **Cell arc:**
  - A `Tool` abstraction: schema + a validated Python callable.
  - A registry and a dispatcher (name → executor) with argument validation (Pydantic).
  - The agent loop: call model → if tool_use, execute, append result, repeat → else return.
  - 🔧 add two real tools (a safe web-fetch stub + a file reader over `data/`).
  - ⚠️ safety: timeouts, input validation, and an explicit **max-steps** guard (termination).
  - 🔮 *predict* what happens with a bad argument, then watch validation catch it.
  - 🎯 senior lens: idempotency & side effects — which tools are safe to retry.
- **Datasets/fixtures:** a couple of small text files in `data/`.
- **APIs & cost:** mockable; live ≈ a short multi-step run (a handful of calls).
- **You'll be able to:** build a framework-free agent loop you fully understand — the thing
  every framework later hides from you.

### 12-03 · `12-03-parallel-tools-and-recovery.ipynb` — Parallel calls, errors, partial failure
- **Type:** walkthrough
- **Maps to:** §12.5 (parallel tool calls, error recovery, partial failures)
- **Objective:** handle multiple tool calls in one turn, run independent ones concurrently,
  and recover gracefully when one fails.
- **Prereqs:** 12-02; async basics from Ch 4 (`learn/part-02-.../04-*`).
- **Cell arc:**
  - Model returns *several* tool_use blocks in one turn — inspect them.
  - Execute independent tools concurrently (`asyncio.gather`); preserve call IDs.
  - ⚠️ pitfall: one tool throws — return a structured error result, don't crash the loop.
  - 🔮 *predict* how the model reacts to a tool error, then see it retry/adapt.
  - 🎯 senior lens: when parallelism helps vs when ordering/consistency forbids it.
- **Datasets/fixtures:** reuse `data/`; one tool deliberately fails.
- **APIs & cost:** mockable; live ≈ one multi-tool run.
- **You'll be able to:** run tools in parallel and keep an agent alive through partial failure.

## Feeds (cross-pillar)
- **Blueprint(s):** [`blueprints/agent-loop/`](../../blueprints/agent-loop/) — the
  production-grade version of 12-02 (typed tools, retries, telemetry hooks). Each notebook
  ends by pointing here.
- **Template(s):** contributes the tool-definition pattern used by
  [`templates/agent-project-starter/`](../../templates/agent-project-starter/).
- **Capstone:** advances `capstone-project/agents/raw/` and `capstone-project/agents/tools/`; checkpoint
  `checkpoints/ch12-tool-loop`.

## Dependencies
- Ch 11 (model APIs, SDK shapes) · Ch 4 (async) · Ch 15 will revisit validation/reliability.

## Phase-2 definition of done
- [ ] All three notebooks run top-to-bottom in `MOCK=1` with no errors.
- [ ] Tool schemas, the loop shape, and the max-steps guard match the book's §12 code.
- [ ] Each notebook ends with recap + exercises and a link to `blueprints/agent-loop/`.
- [ ] Secrets from env only; canned mock responses are realistic tool-use blocks.
