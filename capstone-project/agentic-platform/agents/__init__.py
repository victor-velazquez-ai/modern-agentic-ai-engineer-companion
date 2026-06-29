"""The platform's reasoning engines (Appendix C · ``agents/``).

This package is the capstone's *assembled* agent subsystem — the integrated counterpart to
the ``agent-loop`` and ``multi-agent-supervisor`` blueprints. Where a blueprint shows one
mechanism in isolation, this is how those mechanisms wire into the wider platform: the same
framework-free loop everything grows around, three interchangeable framework variants over one
toolset, a multi-agent supervisor that owns the goal and budget, and the human-in-the-loop
approval gate that fronts risky tools.

Layout (matches Appendix C)
---------------------------
``tools/``        tool schemas + safe executors — the typed ledger, registry, and dispatch.
``raw/``          the no-framework loop (Ch 12): observe → decide → act → observe.
``graph/``        the LangGraph variant (Ch 18): the same agent expressed as a state graph.
``pydantic_ai/``  the Pydantic AI variant (Ch 18): the same agent via a typed agent object.
``supervisor.py`` the multi-agent supervisor (Ch 17): plan → delegate → aggregate → done.
``approvals.py``  the approval gate (Ch 20): risk-tier table → human-in-the-loop hold/resume.

Everything is MOCK-runnable: with ``COMPANION_MOCK=1`` (the default) the whole subsystem runs
offline, deterministically, with zero API keys and zero spend. The single seam to a real model
is the :class:`~agents.tools.model.ModelPort`; inject an ``llm/gateway.py`` client there for the
live path. Secrets are read from the environment only.
"""

from __future__ import annotations

__all__ = ["__version__"]

__version__ = "0.1.0"
