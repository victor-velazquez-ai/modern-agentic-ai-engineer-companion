"""The support agent — where the pattern blueprints are wired into one decision (Appendix G #1).

This is the composition point the PLAN describes. One ticket goes in; one structured
:class:`~app.decision.Decision` (resolve / act / escalate) comes out. The agent does only what a
front-line human would on the easy cases and *stops cleanly* on the rest:

    ticket ─► [escalation policy gate] ──fires──► ESCALATE
                     │ allows
                     ▼
              [classify intent]
                     │
       ┌─────────────┼───────────────────────────┐
       ▼ faq         ▼ action (reset/plan/order…) │
   [rag-pipeline] [mcp scoped tool] ──fails──► ESCALATE
       │ grounded?     │ acted
       ▼               ▼
    RESOLVE           ACT

Which pattern blueprint does which job (all imported, none forked — see :mod:`app._paths`):

* ``rag-pipeline``        — ingest the help center, hybrid-retrieve + rerank for grounded,
  *cited* answers (the *deflect* path).
* ``mcp-server``          — the scoped, least-privilege tools the agent *acts* through
  (the *act* path); reached only via the safe client's allow-list + validation.
* ``agent-loop``          — the tool-use loop substrate (its ``ModelPort`` is the seam a real
  model drops into; here a deterministic mock keeps the demo free). Exposed via
  :meth:`SupportAgent.build_action_loop` for the live wiring.
* ``observability-stack`` — optional tracing: pass a ``Tracer`` and each ticket becomes a span
  tree you can read (retrieval span, tool span, decision).
* ``eval-harness``        — not used at *serve* time; it grades this agent offline
  (see ``evals/`` and ``demo.py``). Resolution, not deflection, is the headline metric.

MOCK by default: retrieval uses the deterministic mock embedder/reranker, tools run in-process,
and no model is called on the answer-only path. The *answering* model (turning retrieved chunks
into prose) is the one live-path seam; in MOCK we synthesise a grounded answer from the top
chunk so the whole thing runs with zero spend and zero keys.
"""

from __future__ import annotations

# Wire the sibling pattern blueprints onto sys.path (side effect) before importing them.
from . import _paths  # noqa: F401

import re
from dataclasses import dataclass, field
from typing import Any, Callable

# --- pattern blueprints (imported, not forked) ---------------------------------------------
from rag_pipeline import (
    Document,
    HybridRetriever,
    InMemoryVectorStore,
    MockReranker,
    chunk_documents,
    embed_chunks,
)

# --- this solution's own modules -----------------------------------------------------------
from .decision import Action, Citation, Decision
from .policies import EscalationPolicy, TicketContext, default_policy

# ``observability_stack`` is optional at serve time; import lazily/defensively so the agent
# runs even if that sibling blueprint is absent.
try:  # pragma: no cover - exercised when the sibling is present (it is, in this repo)
    from observability_stack import SpanKind, Tracer  # type: ignore
except Exception:  # pragma: no cover
    Tracer = None  # type: ignore[assignment,misc]
    SpanKind = None  # type: ignore[assignment,misc]


# --- Intent classification (cheap, deterministic; a classifier swaps in on the live path) --

# Each intent maps to (keyword triggers, the scoped MCP tool it would call or None for FAQ).
_INTENT_RULES: tuple[tuple[str, tuple[str, ...], str | None], ...] = (
    ("password_reset", ("reset", "password", "log in", "locked out", "can't sign in"), "reset_password"),
    ("refund", ("refund", "money back", "reimburse", "charge back"), "issue_refund"),
    ("plan_change", ("upgrade", "downgrade", "change plan", "switch to", "pricing tier"), "change_plan"),
    ("order_status", ("order", "shipped", "tracking", "delivery", "where is my"), "order_status"),
)

_CUSTOMER_ID_RE = re.compile(r"\bcus_[0-9a-z]+\b", re.IGNORECASE)
_ORDER_ID_RE = re.compile(r"\bord_[0-9a-z]+\b", re.IGNORECASE)
_MONEY_RE = re.compile(r"\$\s*(\d+(?:\.\d{1,2})?)")
_PLAN_RE = re.compile(r"\b(starter|pro|enterprise)\b", re.IGNORECASE)


@dataclass(frozen=True, slots=True)
class Intent:
    """The coarse intent the agent assigned to a ticket, plus extracted slots."""

    name: str
    tool: str | None
    slots: dict[str, Any] = field(default_factory=dict)

    @property
    def is_action(self) -> bool:
        return self.tool is not None


def classify_intent(text: str) -> Intent:
    """Assign a coarse intent and pull out the slots an action tool would need.

    Deterministic keyword routing — free in MOCK, and the obvious first line. On the live path
    you'd back the *same* :class:`Intent` contract with a classifier or a gateway call; the call
    site in :meth:`SupportAgent.handle` does not change.
    """
    low = text.lower()
    slots: dict[str, Any] = {}
    if (m := _CUSTOMER_ID_RE.search(text)):
        slots["customer_id"] = m.group(0).lower()
    if (m := _ORDER_ID_RE.search(text)):
        slots["order_id"] = m.group(0).lower()
    if (m := _MONEY_RE.search(text)):
        slots["amount_usd"] = float(m.group(1))
    if (m := _PLAN_RE.search(text)):
        slots["new_plan"] = m.group(1).lower()

    for name, triggers, tool in _INTENT_RULES:
        if any(t in low for t in triggers):
            return Intent(name=name, tool=tool, slots=slots)
    return Intent(name="faq", tool=None, slots=slots)


# --- The agent -----------------------------------------------------------------------------

# A callable that performs one scoped tool call: ``call(name, args) -> result``. This is exactly
# ``mcp_server.SafeMCPClient.call`` — so the agent depends on the *guarded* boundary, never on a
# raw tool. Injected (not constructed here) to keep the agent free of transport concerns.
ToolCaller = Callable[[str, dict[str, Any]], Any]


@dataclass
class SupportAgent:
    """A front-line support agent: deflect, act, or escalate — one structured decision per ticket.

    Parameters
    ----------
    retriever / reranker:
        The ``rag-pipeline`` grounding stack (built by :meth:`from_help_center`).
    policy:
        The ``policies.EscalationPolicy`` stop-gate. Deny-by-default for risky turns.
    tool_caller:
        The guarded MCP call surface for the *act* path (``SafeMCPClient.call``). ``None``
        disables actions (answer-only autonomy rung) — an action intent then escalates.
    top_k / rerank_top_n:
        Retrieval shortlist size and post-rerank cut.
    """

    retriever: HybridRetriever
    reranker: MockReranker = field(default_factory=MockReranker)
    policy: EscalationPolicy = field(default_factory=default_policy)
    tool_caller: ToolCaller | None = None
    top_k: int = 4
    rerank_top_n: int = 3
    _doc_titles: dict[str, str] = field(default_factory=dict, repr=False)

    # --- construction ----------------------------------------------------------------------
    @classmethod
    def from_help_center(
        cls,
        docs: list[Document],
        *,
        tool_caller: ToolCaller | None = None,
        policy: EscalationPolicy | None = None,
    ) -> "SupportAgent":
        """Ingest a help-center corpus through ``rag-pipeline`` and return a ready agent.

        chunk → embed → store → (hybrid retrieve + rerank at serve time). All offline/mock by
        default; the embedder is the env-selected one (mock unless ``COMPANION_MOCK=0`` + gateway).
        """
        store = InMemoryVectorStore()
        chunks = chunk_documents(docs, structure_aware=True)
        store.add(embed_chunks(chunks))
        retriever = HybridRetriever(store)
        titles = {d.id: str(d.metadata.get("title", d.id)) for d in docs}
        return cls(
            retriever=retriever,
            policy=policy or default_policy(),
            tool_caller=tool_caller,
            _doc_titles=titles,
        )

    # --- the one entry point ---------------------------------------------------------------
    def handle(self, ticket: str, *, tracer: "Any | None" = None) -> Decision:
        """Resolve one ticket to a structured :class:`Decision`.

        Order of operations (the safety-first shape):

        1. **Policy gate first.** If any escalation trigger fires, stop — never act, never guess.
        2. **Classify intent.** FAQ → deflect; an action intent → act through a scoped tool.
        3. **Deflect (RAG)** or **Act (MCP tool)**, escalating on weak grounding or a tool failure.

        Pass a ``observability_stack.Tracer`` as ``tracer`` to emit a span tree for the ticket.
        """
        if tracer is not None and Tracer is not None:
            with tracer.span("handle_ticket", SpanKind.CHAIN, attributes={"ticket": ticket[:120]}):
                return self._handle(ticket, tracer)
        return self._handle(ticket, None)

    # --- internals -------------------------------------------------------------------------
    def _handle(self, ticket: str, tracer: "Any | None") -> Decision:
        intent = classify_intent(ticket)

        # 1) Escalation policy gate — evaluated BEFORE any action or answer.
        ctx = TicketContext(
            text=ticket,
            intent="refund" if intent.name == "refund" else ("faq" if not intent.is_action else intent.name),
            amount_usd=intent.slots.get("amount_usd"),
            grounding_confidence=1.0,  # provisional; the FAQ path recomputes from retrieval
        )
        if intent.is_action:
            fired = self.policy.evaluate(ctx)
            if fired is not None:
                return Decision.escalate(fired.reason, confidence=0.9)
            return self._act(intent, ticket, tracer)

        # 2) FAQ / answer-only path: retrieve, check grounding, then either resolve or escalate.
        return self._deflect(ticket, ctx, tracer)

    def _deflect(self, ticket: str, ctx: TicketContext, tracer: "Any | None") -> Decision:
        hits, top_score = self._retrieve(ticket, tracer)
        ctx = TicketContext(
            text=ctx.text,
            intent="faq",
            amount_usd=ctx.amount_usd,
            grounding_confidence=top_score,
        )
        # Low grounding (or any other trigger) → escalate rather than hallucinate a policy answer.
        fired = self.policy.evaluate(ctx)
        if fired is not None or not hits:
            reason = fired.reason if fired else "no relevant help-center content found"
            return Decision.escalate(reason, confidence=1.0 - top_score)

        top = hits[0]
        citations = tuple(
            Citation(
                doc_id=h.chunk.doc_id,
                title=self._doc_titles.get(h.chunk.doc_id, h.chunk.doc_id),
                score=h.score,
            )
            for h in hits
        )
        answer = self._synthesize_answer(ticket, top.chunk.text)
        return Decision.resolve(answer, citations=citations, confidence=top_score)

    def _act(self, intent: Intent, ticket: str, tracer: "Any | None") -> Decision:
        # Answer-only autonomy rung: no tool wired → hand off rather than pretend to act.
        if self.tool_caller is None or intent.tool is None:
            return Decision.escalate(
                f"action '{intent.name}' requested but actions are disabled (answer-only mode)",
                confidence=0.8,
            )
        args = self._args_for(intent)
        if args is None:
            return Decision.escalate(
                f"could not determine required details for '{intent.name}' (need a customer/order id)",
                confidence=0.7,
            )
        try:
            result = self._call_tool(intent.tool, args, tracer)
        except Exception as exc:  # the guarded boundary refused or the tool failed
            return Decision.escalate(
                f"scoped action '{intent.tool}' could not be completed safely: {exc}",
                confidence=0.6,
            )
        return Decision.act(
            self._confirm_action(intent, result),
            tool=intent.tool,
            tool_args=args,
            tool_result=result,
            confidence=0.9,
        )

    # --- retrieval (rag-pipeline) ----------------------------------------------------------
    def _retrieve(self, query: str, tracer: "Any | None"):
        """Hybrid retrieve + rerank; return ``(scored_chunks, top_score)``.

        ``top_score`` is the reranker's confidence in the best chunk — the grounding signal the
        escalation policy reads. Wrapped in a retrieval span when a tracer is supplied.
        """
        def _do():
            raw = self.retriever.retrieve(query, k=self.top_k)
            reranked = self.reranker.rerank(query, raw, top_n=self.rerank_top_n)
            top_score = reranked[0].score if reranked else 0.0
            return reranked, top_score

        if tracer is not None and Tracer is not None:
            with tracer.retrieval_span("help_center_search", query=query, k=self.top_k):
                return _do()
        return _do()

    def _call_tool(self, name: str, args: dict[str, Any], tracer: "Any | None") -> Any:
        assert self.tool_caller is not None
        if tracer is not None and Tracer is not None:
            with tracer.tool_span(name, attributes={"args": args}):
                return self.tool_caller(name, args)
        return self.tool_caller(name, args)

    # --- slot filling + answer synthesis ---------------------------------------------------
    @staticmethod
    def _args_for(intent: Intent) -> dict[str, Any] | None:
        """Build the tool arguments for an action intent from its extracted slots."""
        s = intent.slots
        if intent.tool in ("reset_password",):
            return {"customer_id": s["customer_id"]} if "customer_id" in s else None
        if intent.tool == "order_status":
            return {"order_id": s["order_id"]} if "order_id" in s else None
        if intent.tool == "change_plan":
            if "customer_id" in s and "new_plan" in s:
                return {"customer_id": s["customer_id"], "new_plan": s["new_plan"]}
            return None
        if intent.tool == "issue_refund":
            if "customer_id" in s and "amount_usd" in s:
                return {"customer_id": s["customer_id"], "amount_usd": s["amount_usd"]}
            return None
        return None

    @staticmethod
    def _synthesize_answer(ticket: str, source_text: str) -> str:
        """MOCK answer synthesis: ground the reply in the top chunk, no model call.

        On the live path this is the one model turn on the deflect path (route it through
        ``llm-gateway``: a cheap model for easy questions, escalate hard ones — PLAN Ch 39–40).
        Here we return the retrieved snippet verbatim with a short lead-in so the answer is
        provably grounded and the demo spends nothing.
        """
        snippet = source_text.strip()
        if len(snippet) > 320:
            snippet = snippet[:317].rstrip() + "…"
        return f"Here's what should help: {snippet}"

    @staticmethod
    def _confirm_action(intent: Intent, result: Any) -> str:
        """A short confirmation message for an ACT decision, from the tool's result."""
        if isinstance(result, dict) and result.get("ok") is False:
            return f"I wasn't able to complete that ({result.get('reason', 'unknown error')})."
        if intent.tool == "reset_password":
            return "I've sent a password-reset email to the address on file."
        if intent.tool == "order_status":
            status = result.get("status") if isinstance(result, dict) else None
            eta = result.get("eta") if isinstance(result, dict) else None
            if status:
                return f"Your order is currently '{status}'" + (f", expected by {eta}." if eta else ".")
            return "I looked up your order; I couldn't find a matching record."
        if intent.tool == "change_plan":
            to = result.get("to") if isinstance(result, dict) else None
            return f"Done — your plan is now '{to}'." if to else "I've updated your plan."
        if intent.tool == "issue_refund":
            amt = result.get("amount_usd") if isinstance(result, dict) else None
            return f"I've issued a refund of ${amt:.2f}." if amt is not None else "I've issued your refund."
        return "Done."

    # --- live-path seam: an agent-loop the model can drive ---------------------------------
    def build_action_loop(self, model: "Any | None" = None, *, max_turns: int = 4):
        """Return an ``agent-loop`` ``AgentLoop`` whose tools are this agent's scoped MCP tools.

        This is the seam to the *live* path: instead of the deterministic intent router above,
        a real model drives the loop, deciding which scoped tool to call. The tools are still the
        guarded MCP callables, so least-privilege holds regardless of who's driving. Imported
        lazily so the answer-only demo doesn't require a model to be constructed.
        """
        from agent_loop import AgentLoop, ToolRegistry, tool as make_tool  # local import

        if self.tool_caller is None:
            raise RuntimeError("no tool_caller wired; actions are disabled (answer-only mode)")

        registry = ToolRegistry()
        # Re-expose each allow-listed scoped tool as an agent-loop Tool. The schemas mirror the
        # MCP tools; the safe client still validates every call.
        registry.add(make_tool(
            "reset_password", "Send a password-reset email to a customer.",
            {"type": "object", "properties": {"customer_id": {"type": "string"}},
             "required": ["customer_id"]},
        )(lambda customer_id: self.tool_caller("reset_password", {"customer_id": customer_id})))  # type: ignore[misc]
        registry.add(make_tool(
            "order_status", "Look up an order's status and ETA.",
            {"type": "object", "properties": {"order_id": {"type": "string"}},
             "required": ["order_id"]},
        )(lambda order_id: self.tool_caller("order_status", {"order_id": order_id})))  # type: ignore[misc]
        return AgentLoop(model=model, tools=registry, max_turns=max_turns)
