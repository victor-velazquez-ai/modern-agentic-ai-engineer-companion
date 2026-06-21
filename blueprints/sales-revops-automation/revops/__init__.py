"""revops — Sales & RevOps automation, a *solution* blueprint that composes patterns.

This package wires together five **pattern blueprints** — without forking any of them — into the
revenue-motion busywork remover the PLAN describes:

* ``agent-loop``          — the tool-using loop the call->CRM extraction runs on (Ch 12).
* ``mcp-server``          — the clean, guarded tool boundary to the (mock) CRM and enrichment.
* ``rag-pipeline``        — retrieval over past winning messaging for grounded drafting (Ch 13).
* ``eval-harness``        — extraction-accuracy evals + a wrong-recipient guardrail (Ch 22/41).
* ``observability-stack`` — traces the nightly hygiene / enrichment jobs (Ch 23).

Everything runs **MOCK by default** (``COMPANION_MOCK=1``): no network, no API keys, no spend.
The composition is by *relative import* of each sibling blueprint's ``src/`` (see
:mod:`revops.compose`), so this package adds glue, never a copy.

Design stance (the PLAN's locked decisions):

* It is a **workflow**, not a chatbot.
* **Drafts go to a human to send** — outbound under an agent's name unsupervised is brand risk.
* CRM writes are **conservative**: low-confidence fields are *flagged*, not written, because bad
  data in the forecast is worse than missing data.
"""

from __future__ import annotations

__version__ = "0.1.0"
