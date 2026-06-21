"""The composition seam — import the pattern blueprints *without forking them*.

A solution blueprint earns its keep by **reusing** the pattern blueprints, so this module is
the one place that knows where the siblings live. It puts each sibling's ``src/`` directory on
``sys.path`` (exactly the convention every blueprint ``demo.py`` already uses) and re-exports the
handful of symbols this pipeline composes. Import from here, never from a copy:

    from .compose import (
        AgentLoop, MockModel, ToolRegistry, assistant,   # agent-loop
        Document, HybridRetriever, InMemoryVectorStore,  # rag-pipeline
        MockReranker, chunk_documents, embed_chunks,
        Tracer, ConsoleExporter, SpanKind, summarize,    # observability-stack
        LLMJudge, ExactMatch, Contains, run_grouped,     # eval-harness
    )

Why ``sys.path`` and not a package install? These blueprints are *study-and-adapt* sources, not
published wheels; each ships under ``<blueprint>/src/<pkg>/`` and is meant to be read in place.
Wiring the paths here keeps the demo runnable straight from a clone with zero install step, and
keeps every composing module importing the **same** blueprint code (no vendored divergence).

The live path: nothing here spends money. Under ``COMPANION_MOCK=0`` the model seam in
:mod:`pipeline.stages` is where an ``llm-gateway``-backed port is injected; this module only
makes the blueprints importable.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

# blueprints/content-production-pipeline/pipeline/compose.py -> blueprints/
_BLUEPRINTS = Path(__file__).resolve().parents[2]

# The sibling pattern blueprints this solution composes, in dependency order. Each exposes a
# top-level package under ``<name>/src/``. We add the *src* dirs (not the blueprint roots) so
# ``import agent_loop`` resolves to the real, unforked source.
_COMPOSED = (
    "agent-loop",
    "rag-pipeline",
    "eval-harness",
    "observability-stack",
    "llm-gateway",
)


def _wire_paths() -> list[str]:
    """Put each composed blueprint's ``src/`` on ``sys.path`` (idempotent).

    Returns the list of paths added (for diagnostics / the README's "what got wired" note).
    Missing siblings are skipped quietly: the MOCK demo only needs the four offline blueprints,
    and ``llm-gateway`` is solely the live-path door — a clone without it still runs.
    """
    added: list[str] = []
    for name in _COMPOSED:
        src = _BLUEPRINTS / name / "src"
        if not src.is_dir():
            continue
        s = str(src)
        if s not in sys.path:
            sys.path.insert(0, s)
            added.append(s)
    return added


_wire_paths()

# --- agent-loop: the per-stage draft + reflection/critique loop (Ch 16) -----------------
from agent_loop import (  # noqa: E402  (after the sys.path wiring above, on purpose)
    AgentLoop,
    MockModel,
    ModelPort,
    ToolRegistry,
    assistant,
)

# --- rag-pipeline: brand + product-facts retrieval (Ch 13) ------------------------------
from rag_pipeline import (  # noqa: E402
    Document,
    HybridRetriever,
    InMemoryVectorStore,
    MockReranker,
    chunk_documents,
    embed_chunks,
)

# --- observability-stack: a span per stage -> one auditable trace (Ch 23) ---------------
from observability_stack import (  # noqa: E402
    ConsoleExporter,
    SpanKind,
    Tracer,
    summarize,
)

# --- eval-harness: brand-adherence + factual-accuracy evals + gate (Ch 22) --------------
from eval_harness import (  # noqa: E402
    Contains,
    ExactMatch,
    LLMJudge,
    load_jsonl,
)
from eval_harness.runner import run_grouped  # noqa: E402

MOCK = os.getenv("COMPANION_MOCK", "1") != "0"

__all__ = [
    "MOCK",
    # agent-loop
    "AgentLoop",
    "MockModel",
    "ModelPort",
    "ToolRegistry",
    "assistant",
    # rag-pipeline
    "Document",
    "HybridRetriever",
    "InMemoryVectorStore",
    "MockReranker",
    "chunk_documents",
    "embed_chunks",
    # observability-stack
    "ConsoleExporter",
    "SpanKind",
    "Tracer",
    "summarize",
    # eval-harness
    "Contains",
    "ExactMatch",
    "LLMJudge",
    "load_jsonl",
    "run_grouped",
]
