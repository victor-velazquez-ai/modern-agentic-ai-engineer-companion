"""The staged pipeline (Ch 31) — brief -> research -> draft -> critique -> variants ->
guardrails -> review, wired from the pattern blueprints.

This is the spine of the solution. Each stage is a small, inspectable step that emits one
:class:`~pipeline.artifacts.Artifact`, and the whole run is wrapped in
``observability-stack`` spans so it is a single auditable trace. The stages **compose** the
pattern blueprints — they do not re-implement them:

* **research** retrieves brand voice + product facts with ``rag-pipeline``
  (``HybridRetriever`` + ``MockReranker``), so drafts are grounded and don't fabricate claims;
* **draft** + **critique** use the ``agent-loop`` model seam (a ``MockModel`` in MOCK mode,
  an ``llm-gateway`` port on the live path) for the reflection/critique pass (Ch 16);
* **guardrails** runs the brand/compliance checks (Ch 41) and decides what a human must see;
* every stage is a span via ``observability-stack`` (Ch 23);
* the run **stops at review** — ``review_ready=True``, ``published=False``. Humans publish.

Free and offline by default (``COMPANION_MOCK=1``). Live path: inject a gateway-backed
``ModelPort`` into :class:`ContentPipeline`; nothing else changes.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Sequence

from .artifacts import Artifact, PipelineRun, Stage
from .compose import (
    Document,
    HybridRetriever,
    InMemoryVectorStore,
    MockModel,
    MockReranker,
    ModelPort,
    SpanKind,
    Tracer,
    assistant,
    chunk_documents,
    embed_chunks,
)
from .critique import CritiqueLoop
from .guardrails import DEFAULT_RULES, GuardrailRules, check_brand_compliance


# --- the brief: the pipeline's input ------------------------------------------------------
@dataclass(frozen=True, slots=True)
class Brief:
    """A content brief — what marketing hands the pipeline."""

    id: str
    topic: str
    channels: tuple[str, ...] = ("blog", "email", "social")
    audience: str = "prospective customers"
    keywords: tuple[str, ...] = field(default_factory=tuple)

    @classmethod
    def from_dict(cls, obj: dict) -> "Brief":
        return cls(
            id=str(obj["id"]),
            topic=str(obj["topic"]),
            channels=tuple(obj.get("channels", ("blog", "email", "social"))),
            audience=str(obj.get("audience", "prospective customers")),
            keywords=tuple(obj.get("keywords", ())),
        )


# --- the brand context: the rag-pipeline grounding corpus ---------------------------------
@dataclass(slots=True)
class BrandContext:
    """The retrieval side of the pipeline: brand voice + product facts indexed for grounding.

    Wraps a ``rag-pipeline`` store + retriever + reranker. ``ground(query)`` returns the top
    grounding snippets (and their ids) a stage should write from — the line that keeps drafts
    on-message and stops fabricated claims.
    """

    retriever: HybridRetriever
    reranker: MockReranker = field(default_factory=MockReranker)
    chunk_count: int = 0

    def ground(self, query: str, *, k: int = 3) -> list[tuple[str, str]]:
        """Return up to ``k`` ``(chunk_id, text)`` grounding snippets for ``query``."""
        hits = self.retriever.retrieve(query, k=k)
        reranked = self.reranker.rerank(query, hits, top_n=k)
        return [(s.chunk.id, s.chunk.text) for s in reranked]


def build_brand_context(documents: Sequence[Document]) -> BrandContext:
    """Index a brand/product corpus into a ``rag-pipeline`` retriever (offline, deterministic).

    Adapt step: replace ``documents`` with your brand voice + product-truth corpus. The chunking,
    embedding, store, and hybrid retriever are all the unforked ``rag-pipeline`` blueprint.
    """
    chunks = chunk_documents(documents, chunk_size=60, overlap=12)
    store = InMemoryVectorStore()
    store.add(embed_chunks(chunks))
    return BrandContext(retriever=HybridRetriever(store), chunk_count=len(store))


# --- the result -------------------------------------------------------------------------
@dataclass(slots=True)
class PipelineResult:
    """Everything a run produced: the artifact ledger, the trace, and the review verdict."""

    run: PipelineRun
    tracer: Tracer

    @property
    def review_ready(self) -> bool:
        return self.run.review_ready

    def variants(self) -> dict[str, str]:
        art = self.run.get(Stage.VARIANTS)
        return dict(art.content) if art and isinstance(art.content, dict) else {}


# --- the pipeline ------------------------------------------------------------------------
class ContentPipeline:
    """Run a brief through every stage and stop at human review.

    Parameters
    ----------
    brand:
        The :class:`BrandContext` (a ``rag-pipeline`` retriever) to ground drafts on.
    model:
        Optional ``agent-loop`` :class:`ModelPort`. ``None`` (default) -> the offline MOCK draft
        model + MOCK critic, free and deterministic. Inject a gateway-backed port for the live
        path; the stages don't change.
    rules:
        The brand/compliance :class:`GuardrailRules`. Defaults to the illustrative
        :data:`~pipeline.guardrails.DEFAULT_RULES`; swap for your brand.
    critique:
        The reflection/critique loop (Ch 16). Defaults to one over the same ``model`` seam.
    """

    def __init__(
        self,
        brand: BrandContext,
        *,
        model: ModelPort | None = None,
        rules: GuardrailRules = DEFAULT_RULES,
        critique: CritiqueLoop | None = None,
    ) -> None:
        self.brand = brand
        self.model = model
        self.rules = rules
        self.critique = critique or CritiqueLoop(model=model)

    def run(self, brief: Brief) -> PipelineResult:
        """Execute every stage for ``brief``, fully traced, stopping review-ready."""
        tracer = Tracer(run_id=f"cpp-{brief.id}")
        run = PipelineRun(run_id=tracer.run_id, brief_id=brief.id)

        with tracer.run("content-pipeline", attributes={"brief.id": brief.id}):
            grounding = self._research(brief, run, tracer)
            draft = self._draft(brief, grounding, run, tracer)
            revised = self._critique_stage(draft, run, tracer)
            variants = self._variants(brief, revised, run, tracer)
            self._guardrails(variants, grounding, run, tracer)
            self._review(run, tracer)

        return PipelineResult(run=run, tracer=tracer)

    # -- stages ---------------------------------------------------------------------------
    def _research(self, brief: Brief, run: PipelineRun, tracer: Tracer) -> list[tuple[str, str]]:
        """Stage: retrieve brand voice + product facts to ground the draft (rag-pipeline)."""
        query = " ".join((brief.topic, *brief.keywords))
        with tracer.span("research", SpanKind.RETRIEVAL, attributes={"query": query}):
            grounding = self.brand.ground(query, k=3)
        run.add(
            Artifact(
                stage=Stage.RESEARCH,
                content=[text for _, text in grounding],
                sources=tuple(cid for cid, _ in grounding),
                meta={"query": query, "k": len(grounding)},
            )
        )
        return grounding

    def _draft(
        self,
        brief: Brief,
        grounding: list[tuple[str, str]],
        run: PipelineRun,
        tracer: Tracer,
    ) -> str:
        """Stage: write the first draft, grounded on the research artifact (agent-loop seam)."""
        facts = "\n".join(f"- {text}" for _, text in grounding)
        prompt = (
            f"Write a short {brief.channels[0]} draft about '{brief.topic}' for "
            f"{brief.audience}. Use only these facts:\n{facts}"
        )
        with tracer.model_span(
            "draft", model="mock-model", input_tokens=0, output_tokens=0
        ) as span:
            text = self._complete(prompt, grounding=grounding, kind="draft")
            span.set_attribute("draft.chars", len(text))
        run.add(
            Artifact(
                stage=Stage.DRAFT,
                content=text,
                sources=tuple(cid for cid, _ in grounding),
                meta={"channel": brief.channels[0]},
            )
        )
        return text

    def _critique_stage(self, draft: str, run: PipelineRun, tracer: Tracer) -> str:
        """Stage: reflect-then-revise before a human sees it (Ch 16, agent-loop seam)."""
        with tracer.span("critique", SpanKind.CHAIN) as span:
            result = self.critique.run(draft)
            span.set_attribute("critique.changed", result.changed)
        run.add(
            Artifact(
                stage=Stage.CRITIQUE,
                content=result.critique,
                meta={"changed": result.changed},
            )
        )
        run.add(Artifact(stage=Stage.REVISE, content=result.revised))
        return result.revised

    def _variants(
        self, brief: Brief, revised: str, run: PipelineRun, tracer: Tracer
    ) -> dict[str, str]:
        """Stage: adapt the revised draft to each channel (one variant per channel)."""
        variants: dict[str, str] = {}
        with tracer.span("variants", SpanKind.CHAIN) as span:
            for channel in brief.channels:
                variants[channel] = self._adapt(revised, channel)
            span.set_attribute("variants.count", len(variants))
        run.add(
            Artifact(
                stage=Stage.VARIANTS,
                content=variants,
                sources=run.require(Stage.DRAFT).sources,
                meta={"channels": list(brief.channels)},
            )
        )
        return variants

    def _guardrails(
        self,
        variants: dict[str, str],
        grounding: list[tuple[str, str]],
        run: PipelineRun,
        tracer: Tracer,
    ) -> None:
        """Stage: brand + compliance checks on every variant (Ch 41)."""
        sources = tuple(cid for cid, _ in grounding)
        reports: dict[str, dict] = {}
        any_blocked = False
        with tracer.span("guardrails", SpanKind.CHAIN) as span:
            for channel, text in variants.items():
                report = check_brand_compliance(text, rules=self.rules, sources=sources)
                any_blocked = any_blocked or report.blocked
                reports[channel] = {
                    "blocked": report.blocked,
                    "flagged": report.flagged,
                    "findings": [f.render() for f in report.findings],
                }
            span.set_attribute("guardrails.blocked", any_blocked)
        run.add(
            Artifact(
                stage=Stage.GUARDRAILS,
                content=reports,
                meta={"blocked": any_blocked},
            )
        )

    def _review(self, run: PipelineRun, tracer: Tracer) -> None:
        """Stage: package for the human editor. Never auto-publishes.

        review_ready is True unless guardrails hard-blocked a variant. ``published`` stays False
        on purpose — the approval gate is a human, by design (Appendix G / Ch 20/38).
        """
        guard = run.require(Stage.GUARDRAILS)
        blocked = bool(guard.meta.get("blocked"))
        with tracer.span("review", SpanKind.CHAIN) as span:
            run.review_ready = not blocked
            span.set_attribute("review.ready", run.review_ready)
            span.set_attribute("review.published", run.published)
        run.add(
            Artifact(
                stage=Stage.REVIEW,
                content={"review_ready": run.review_ready, "published": run.published},
                meta={"blocked": blocked},
            )
        )

    # -- the model seam (MOCK by default; gateway port on the live path) ------------------
    def _complete(
        self, prompt: str, *, grounding: list[tuple[str, str]], kind: str
    ) -> str:
        """One draft model turn. MOCK mode synthesizes a grounded draft with no spend."""
        if self.model is None:
            return _mock_draft(prompt, grounding)
        from agent_loop import user  # local import: live path only

        return self.model.complete([user(prompt)], []).message.text

    def _adapt(self, text: str, channel: str) -> str:
        """Channel adaptation. MOCK mode applies cheap, deterministic per-channel shaping."""
        if self.model is None:
            return _mock_channel_variant(text, channel)
        from agent_loop import user  # local import: live path only

        prompt = f"Rewrite this for the '{channel}' channel, keeping every fact:\n{text}"
        return self.model.complete([user(prompt)], []).message.text


# --- the offline (MOCK) content synthesizers --------------------------------------------
# These stand in for model turns so the whole pipeline runs free and deterministically. A live
# build replaces them by injecting a gateway-backed ModelPort into ContentPipeline.
def _mock_draft(prompt: str, grounding: list[tuple[str, str]]) -> str:
    """Compose a short, *grounded* draft from the retrieved facts — no model, no spend.

    It only uses the retrieved snippets, so the MOCK draft can't fabricate a claim that isn't in
    the corpus — which is the very property the rag grounding is there to enforce.
    """
    facts = [text for _, text in grounding]
    lead = facts[0] if facts else "Here is what you need to know."
    body = " ".join(facts[1:]) if len(facts) > 1 else ""
    return (f"{lead} {body}".strip() + " Learn more about how this helps your team.").strip()


def _mock_channel_variant(text: str, channel: str) -> str:
    """Deterministic per-channel shaping of the revised draft (no model)."""
    if channel == "email":
        return f"Subject: {text.split('.')[0].strip()}\n\nHi there,\n\n{text}\n\nThanks,\nThe Team"
    if channel == "social":
        first = text.split(".")[0].strip()
        return f"{first}. Read more on the blog."
    # default / blog: the long form as-is
    return text


def build_mock_draft_model(script_text: str) -> MockModel:
    """Convenience for tests/demo: a one-shot ``agent-loop`` MockModel that returns fixed text.

    Shows the *live seam* explicitly — a real :class:`ModelPort` plugs in exactly here — while
    staying offline. Not used by the default MOCK path (which needs no model at all).
    """
    return MockModel([assistant(text=script_text)])
