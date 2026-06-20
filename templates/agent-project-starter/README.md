# agent-project-starter — copy me

A minimal, properly-structured Python **agent / LLM project** you copy into your job so a
new project starts **typed, linted, and tested from commit one** — instead of a blank
folder and a `pip install` you reconstruct from memory.

> **This is a template. Copy it, fill the TODOs, then delete this README** (or replace it
> with your project's own). Search the tree for `TODO` and `▢` — every placeholder is one
> of those. There is **no business logic here**: you still write the agent; the template
> just gives you the project shell that lints, types, tests, and runs from the start.

What you get:

- **`uv` + `src/` layout** — one `pyproject.toml`, no `setup.py`, editable via `uv sync`.
- **One LLM door** (`src/app/llm.py`) — every model call goes through `complete()`, with a
  **MOCK switch** so a fresh clone runs **free and offline**.
- **One example tool** (`src/app/tools/example_tool.py`) — a safe calculator + its schema,
  registered so the agent loop can dispatch it.
- **A tool-loop entrypoint stub** (`src/app/agent.py`) — runs end-to-end today; the real
  loop is a clearly-marked `TODO` for you.
- **Tests** (`tests/`) that pass with **no API key**, and a **`Makefile`** (`make check`)
  wiring lint + type + test into one gate.

Maps to the book: **Ch 4** (production Python: `src/`, typing, packaging), **Ch 11**
(working with model APIs: the one door), **Ch 12** (tool use & function calling: the
`agent.py` + `tools/` scaffold you build the loop into).

---

## Quickstart

You need [`uv`](https://docs.astral.sh/uv/) installed. Then:

```bash
# 1. Copy the scaffold into your project (you own it now — not a submodule).
cp -r templates/agent-project-starter ~/work/my-agent && cd ~/work/my-agent

# 2. Install (creates .venv, installs deps + dev tools).
make install            # == uv sync --extra dev

# 3. Run it. MOCK mode is the default — no key, no spend.
make run                # runs the agent on a sample prompt, prints a canned reply
uv run agent "What is 21 + 21?"

# 4. Run the gate. Passes with NO API key.
make check              # lint + type-check + test
```

### Go live (optional)

```bash
cp .env.example .env    # .env is git-ignored — never commit it
# edit .env: set COMPANION_MOCK=0 and ANTHROPIC_API_KEY=sk-...
uv run agent "Summarize the plot of Hamlet in two sentences."
```

The default model is **`claude-opus-4-8`** (one constant, `MODEL`, in `src/app/llm.py`).

---

## What to fill in

Search for `TODO` / `▢`. The main ones:

| File | Fill in |
|---|---|
| `pyproject.toml` | project `name`, `description`, `authors` |
| `.env.example` | any environment variables your app needs |
| `src/app/config.py` | a typed field for each new setting (fail-fast on startup) |
| `src/app/agent.py` | **your tool-use loop** (the stub returns a single completion) |
| `src/app/tools/` | your own tools (keep, replace, or extend the calculator) |

```bash
grep -rn "TODO" .       # or search TODO / ▢ in your editor
```

---

## Layout

```text
.
├── pyproject.toml          # uv-managed; ruff + mypy + pytest configured
├── .python-version         # pinned interpreter (3.12)
├── .env.example            # copy to .env; MOCK mode needs nothing here
├── .gitignore              # .env, .venv, caches
├── Makefile                # install · fmt · lint · type · test · check · run
├── src/app/
│   ├── config.py           # typed settings from env (fail-fast); add your fields
│   ├── llm.py              # one LLM door; MOCK switch + MODEL constant
│   ├── agent.py            # TODO: your tool-use loop (stub today)
│   ├── tools/
│   │   ├── __init__.py     # tool registry
│   │   └── example_tool.py # a safe example tool (calculator) + schema
│   └── main.py             # CLI: load_dotenv() → run agent on a prompt
└── tests/
    ├── test_config.py
    ├── test_example_tool.py
    └── test_agent_mock.py  # the loop runs end-to-end in MOCK mode (no spend)
```

---

## Definition of done (for your copy)

- [ ] `make install && make check` passes with **no key** (lint + type + test).
- [ ] `make run` prints a canned result in MOCK mode, **no API spend**.
- [ ] Every `TODO` / `▢` is filled; no placeholder text remains.
- [ ] `.env.example` lists every variable; **no real secret** is committed anywhere.
