# Changelog

All notable changes to the companion repository. Releases are tagged to book editions
(see [`docs/BOOK-INTEGRATION.md`](docs/BOOK-INTEGRATION.md) §3).

## [Unreleased] — Phase 2: assets built + verified (2026-06-21)

### Added
- **All companion assets implemented** from their Phase-1 plans: 113 notebooks (every
  chapter), 8 pattern + 12 solution blueprints, 11 templates, and the complete
  `capstone/agentic-platform` reference. Notebooks default to MOCK mode (free, offline,
  no API key).
- **Execution verification**: `scripts/check_notebooks.py` (static — valid JSON + every
  code cell compiles) and `scripts/verify_notebooks.py` (executes every notebook in MOCK
  mode), plus `scripts/requirements-verify.txt` and a `notebooks` GitHub Actions workflow
  that runs both on every push. **Result: 113/113 notebooks execute green.**

### Fixed
- Notebook bugs surfaced by the first execution pass: top-level `asyncio.run()` (illegal in
  a Jupyter kernel) → top-level `await` (10 notebooks); a FastAPI `Request` param that
  read as a query field (422); a git-bisect drill that depended on pytest + stale bytecode;
  and an LLM-gateway fallback that mis-keyed on a `@backup` backend name.

## [Unreleased] — Phase 1: planning skeleton (2026-06-20)

### Added
- Full repository structure mirroring the book: `learn/` (13 parts, 54 chapters), plus
  `blueprints/`, `templates/`, and a dedicated `capstone/`.
- A `PLAN.md` in every chapter and asset folder describing exactly what Phase 2 will build.
- Standards & guides: `REPO-PLAN.md` (master plan), `BOOK-INTEGRATION.md` (2nd-edition
  republish plan), `HOW-TO-USE.md`, `SETUP.md`, `NOTEBOOK-STANDARDS.md`, `CONVENTIONS.md`.
- Scaffolding: `README`, `LICENSE` (MIT), `.gitignore`, `.env.example`, `requirements.txt`.

### Notes
- This is a **plan, not an implementation** — no notebooks/code yet by design. Phase 2 builds
  the assets; Phase 3 ships the book's 2nd (master) edition referencing this repo.

<!--
Future releases:
## [2.0.0] — book 2nd edition (master)
  - Phase 2 assets implemented and CI-green; first edition to reference the companion.
-->
