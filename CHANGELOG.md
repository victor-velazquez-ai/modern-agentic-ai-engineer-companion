# Changelog

All notable changes to the companion repository. Releases are tagged to book editions
(see [`docs/BOOK-INTEGRATION.md`](docs/BOOK-INTEGRATION.md) §3).

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
