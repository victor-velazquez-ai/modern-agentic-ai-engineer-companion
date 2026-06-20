# Developer gates. `make check` runs everything CI should run.
# All targets assume `uv` is installed: https://docs.astral.sh/uv/
#
#   make install   create the venv and install deps (incl. dev)
#   make fmt       auto-format (ruff format + import sort)
#   make lint      lint (ruff check)
#   make type      type-check (mypy)
#   make test      run tests (pytest) — passes in MOCK mode with NO key
#   make check     fmt-check + lint + type + test (the full gate)
#   make run       run the agent loop on a sample prompt (MOCK mode)

.DEFAULT_GOAL := check
.PHONY: install fmt lint type test check run clean

install:
	uv sync --extra dev

fmt:
	uv run ruff format src tests
	uv run ruff check --fix src tests

lint:
	uv run ruff format --check src tests
	uv run ruff check src tests

type:
	uv run mypy

test:
	uv run pytest

check: lint type test

run:
	uv run agent "What is 21 + 21?"

clean:
	rm -rf .venv .pytest_cache .ruff_cache .mypy_cache
	find . -type d -name __pycache__ -prune -exec rm -rf {} +
