"""Service layer — orchestration between the domain and its adapters (Ch 28).

``services/`` is the application's *use-case* layer. A service method reads like the story of one
operation: load entities through a repository port, apply domain rules, call the agent engine
port, persist the result. It is the only layer that holds a transaction and talks to more than
one collaborator at once; the API routes stay thin by delegating here, and the domain stays pure
because the wiring lives here, not in it.

Contents
--------
``agent_service.py``     the seam to *a* reasoning engine: a MOCK engine (offline, canned) and
                         the adapter that wraps the real capstone ``agents/`` loop.
``run_service.py``       create / fetch / list agent runs; drive the sync + streaming paths.
``chat_service.py``      conversations and their messages.
``document_service.py``  register documents and kick off ingestion.
"""

from __future__ import annotations

__all__: list[str] = []
