# Template — Agent Project Starter
> Realizes book Ch 4, 11, 12 · Status: 📋 planned (Phase 1)

## What it scaffolds
A minimal but properly-structured Python agent project — `pyproject.toml`, a `src/` package,
a thin LLM-access module, **one** example tool, a tool-loop entrypoint stub, tests, and a
`Makefile` — so a new agent/LLM project starts typed, linted, and tested from commit one.

## When to copy it
You're starting *any* new Python project that talks to an LLM or runs an agent loop, and you
want a clean, modern base (uv + `src/` + ruff + mypy + pytest) instead of a blank folder and
a `pip install` you reconstruct from memory.

## Planned file tree
```text
agent-project-starter/
├── README.md                  # what this is + "copy me" usage; delete after copying
├── pyproject.toml             # uv-managed; ruff + mypy + pytest configured; ▢ name/desc
├── .python-version            # pinned interpreter
├── .env.example               # ANTHROPIC_API_KEY= ; COMPANION_MOCK=1 ; ▢ your vars
├── .gitignore                 # .env, .venv, __pycache__, caches
├── Makefile                   # install · fmt · lint · type · test · check · run
├── src/
│   └── app/
│       ├── __init__.py
│       ├── config.py          # Settings from env (Pydantic Settings); fail-fast; ▢ fields
│       ├── llm.py             # one LLM client door; MOCK switch returns canned reply
│       ├── agent.py           # # TODO: your tool-use loop — stub returns a placeholder
│       ├── tools/
│       │   ├── __init__.py    # tool registry
│       │   └── example_tool.py # a single, safe example tool (e.g. calculator) + schema
│       └── main.py            # CLI entrypoint: load_dotenv() → run agent on a prompt
└── tests/
    ├── test_config.py         # settings load from env; missing-key message is friendly
    ├── test_example_tool.py   # the example tool's contract
    └── test_agent_mock.py     # agent loop runs end-to-end in MOCK mode (no API spend)
```

## Defaults baked in
- **Packaging:** `uv` + `src/` layout + editable install; one `pyproject.toml`, no `setup.py`.
- **Typing:** `mypy` strict-ish; `from __future__ import annotations`; typed public functions.
- **Lint/format:** `ruff` (lint + import sort) and `ruff format`; `make check` runs all gates.
- **Config:** Pydantic Settings; **secrets only from `.env`**; missing required key fails fast
  with a readable message (mirrors the capstone's `core/settings`).
- **Mock-first:** `COMPANION_MOCK=1` default → `llm.py` returns a canned reply so `make test`
  and a fresh clone run **free and offline**; `MOCK=0` hits the live API (Anthropic-first).
- **Tests:** `pytest`; the agent test exercises the loop in mock mode so CI never spends.
- **Model default:** latest, most capable Claude model id in `llm.py`, set via one constant.

## Maps to the book
- **Ch 4 — Production Python:** the `src/` layout, typing, packaging the chapter argues for.
- **Ch 11 — Working with Model APIs:** `llm.py` is the "one door to the SDK" (retries/usage).
- **Ch 12 — Tool Use & Function Calling:** `agent.py` + `tools/` are the scaffold for the
  tool-use loop the chapter has you build (🔧 Build).
- **Blueprint:** the hardened version of `agent.py` lives in
  [`../../blueprints/agent-loop/`](../../blueprints/agent-loop/PLAN.md) — start here, graduate
  there. **Capstone:** this is the empty-project shape of the platform root (see
  [`../../../chapters/92-appendix-capstone.typ`](../../../chapters/92-appendix-capstone.typ)).

## Phase-2 definition of done
- [ ] `make install && make check` passes on a fresh copy (lint + type + test) with **no key**.
- [ ] `make run` executes the agent loop in `MOCK=1` and prints a canned result, no API spend.
- [ ] Every placeholder is a literal `TODO`/`▢`; no business logic shipped; `README` says "copy me."
- [ ] `.env.example` lists every var; **no real secret** is committed anywhere.
