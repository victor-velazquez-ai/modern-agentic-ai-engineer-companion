"""The in-app copilot — a stateless, per-request agent behind the gateway (Ch 12/25/39/41/43).

This is the module the PLAN's ``copilot_api.py`` names: the request handler an in-app copilot
sits behind. One call to :meth:`Copilot.answer` (or :meth:`Copilot.stream`) is one stateless
turn — everything it needs is passed in (the :class:`~tenancy.Session` and the user's message),
nothing is retained between requests. Statelessness is what lets a public copilot scale
horizontally and what keeps one user's turn from ever bleeding into another's.

The request path composes **five pattern blueprints**, in the order a public surface demands:

1. **Front door** (``app.guardrails`` → ``llm_gateway.Guard`` + a per-user rate limit) — abuse
   resistance *before* any spend. A blocked turn never reaches the model.
2. **Scoped retrieval** (``tenancy`` → ``rag_pipeline``) — evidence pulled from *only this
   tenant's* index, so the prompt is physically incapable of carrying another tenant's data.
3. **Agent loop** (``agent_loop``) — the observe→decide→act cycle, driven by a model port that
   routes generation through the gateway and can call **session-scoped tools** (``app.session_tools``)
   that act only as the signed-in user.
4. **Gateway** (``llm_gateway.Gateway``) — every model call goes through routing + fallback +
   **exact/semantic cache** + **per-user metering**, with the cache/cost *labelled by (tenant,
   user)*. On a public surface, caching and per-user cost are the product (margin), not an
   afterthought.
5. **Observability** (``observability_stack``) — the whole turn is one trace: a run span with
   guard / retrieval / agent / model children, so latency, cost-per-user, and abuse signals are
   inspectable.

Runs **offline, deterministically, $0** under ``COMPANION_MOCK=1`` (the default): the gateway's
``MockProvider`` answers, the mock embedder retrieves, and a deterministic "brain" decides when
to call a tool. Set ``COMPANION_MOCK=0`` + ``ANTHROPIC_API_KEY`` to use the live gateway — the
seams do not change.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from typing import Any, Iterator

from . import _compose  # noqa: F401  (side effect: pattern blueprints on sys.path)

from agent_loop import (  # type: ignore  # noqa: E402
    AgentLoop,
    Message,
    ModelResponse,
    ToolCall,
    ToolRegistry,
    ToolSpec,
    assistant,
)
from llm_gateway import ChatRequest, Gateway  # type: ignore  # noqa: E402
from observability_stack import SpanKind, Tracer  # type: ignore  # noqa: E402

from tenancy import Session, TenantStores  # type: ignore  # noqa: E402

from .guardrails import FrontDoor, FrontDoorVerdict
from .session_tools import UserDataStore, build_session_tools


# A short, in-context system prompt for the copilot persona. The retrieved product-doc evidence
# is woven in per turn (see _CopilotModel), so the model answers grounded in *this tenant's* docs.
SYSTEM_PROMPT = (
    "You are an in-app product copilot. Help the signed-in user get value from the product: "
    "answer using the provided product documentation, use a tool when the user asks about their "
    "own account or orders, and never reveal another customer's data."
)

# How many scoped chunks to retrieve and weave into the prompt as grounding evidence.
DEFAULT_RETRIEVAL_K = 4

# Keywords that route a turn to a session tool in MOCK mode. In the live path the model itself
# decides via function calling; this deterministic "brain" keeps the demo reproducible and $0.
_ORDER_LIST_RE = re.compile(r"\b(my orders|list .*orders|all .*orders)\b", re.I)
_ORDER_STATUS_RE = re.compile(r"\border\s+([A-Za-z]+-?\d+)\b", re.I)
_NOTIF_ON_RE = re.compile(r"\b(enable|turn on|subscribe).{0,30}notif", re.I)
_NOTIF_OFF_RE = re.compile(r"\b(disable|turn off|stop|unsubscribe).{0,30}notif", re.I)


@dataclass(frozen=True)
class Citation:
    """A grounding source behind a copilot answer (so answers are checkable, not hallucinated)."""

    doc_id: str
    title: str
    score: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {"doc_id": self.doc_id, "title": self.title, "score": round(self.score, 4)}


@dataclass(frozen=True)
class CopilotReply:
    """The structured result of one copilot turn — the API/UI/eval/audit shape.

    Exactly one turn produces one reply: the ``text`` the user sees, the ``citations`` it was
    grounded in, the ``tool`` it invoked (if any), whether it was ``blocked`` at the front door,
    and the **cost** + **cache** facts for this user's request (margin is a product metric here).
    """

    text: str
    blocked: bool = False
    block_reason: str = ""
    citations: tuple[Citation, ...] = field(default_factory=tuple)
    tool: str | None = None
    tool_args: dict[str, Any] = field(default_factory=dict)
    cost_usd: float = 0.0
    cached: bool = False
    model: str = ""
    label: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "text": self.text,
            "blocked": self.blocked,
            "block_reason": self.block_reason,
            "citations": [c.to_dict() for c in self.citations],
            "tool": self.tool,
            "tool_args": self.tool_args,
            "cost_usd": round(self.cost_usd, 8),
            "cached": self.cached,
            "model": self.model,
            "label": self.label,
        }


class _CopilotModel:
    """The agent's :class:`~agent_loop.ModelPort`, backed by the gateway and the scoped evidence.

    The ``agent_loop`` talks to a model only through ``complete(transcript, tools)``. This adapter
    is that seam for the copilot:

    * On the **first** turn it decides — deterministically in MOCK mode — whether the user's
      message calls for a **session tool** (their orders/account) and, if so, returns an assistant
      turn with the matching :class:`~agent_loop.ToolCall`. The tools themselves are session-bound
      (see :mod:`app.session_tools`), so the model never names an identity.
    * Otherwise (or after a tool result) it generates a **final answer** by routing the prompt —
      with the retrieved product-doc evidence prepended — through the :class:`~llm_gateway.Gateway`.
      That single call carries the per-*(tenant, user)* ``label`` so the gateway's **cache** and
      **cost meter** are scoped to this user (no cross-user cache hits, exact cost attribution).

    The gateway result of the final generation is stashed on ``last_route`` so the caller can read
    cost/cache/model facts for the reply without re-calling anything.
    """

    def __init__(
        self,
        gateway: Gateway,
        *,
        evidence: str,
        top_evidence: str,
        tool_names: set[str],
        label: str,
        system: str = SYSTEM_PROMPT,
    ) -> None:
        self._gateway = gateway
        self._evidence = evidence
        self._top_evidence = top_evidence
        self._tool_names = tool_names
        self._label = label
        self._system = system
        # MOCK mode (repo default): the gateway's MockProvider returns an opaque canned string,
        # so for a *grounded* answer we surface the retrieved evidence extractively while STILL
        # routing the call through the gateway (real cache / cost / routing / metering). Live
        # mode returns the model's own generated text.
        self._mock = os.getenv("COMPANION_MOCK", "1") != "0"
        self.last_result: Any = None  # the GatewayResult of the final generation
        self._tool_dispatched = False

    def _maybe_tool_call(self, user_text: str) -> Message | None:
        """Deterministic tool routing for MOCK mode (the live path lets the model decide)."""
        if "get_order_status" in self._tool_names:
            m = _ORDER_STATUS_RE.search(user_text)
            if m:
                return assistant(
                    text="Let me check that order.",
                    tool_calls=(ToolCall(id="t1", name="get_order_status",
                                         arguments={"order_id": m.group(1)}),),
                )
        if "get_my_orders" in self._tool_names and _ORDER_LIST_RE.search(user_text):
            return assistant(
                text="Pulling up your orders.",
                tool_calls=(ToolCall(id="t1", name="get_my_orders", arguments={}),),
            )
        if "set_notifications" in self._tool_names:
            if _NOTIF_OFF_RE.search(user_text):
                return assistant(
                    text="Updating your notification settings.",
                    tool_calls=(ToolCall(id="t1", name="set_notifications",
                                         arguments={"enabled": False}),),
                )
            if _NOTIF_ON_RE.search(user_text):
                return assistant(
                    text="Updating your notification settings.",
                    tool_calls=(ToolCall(id="t1", name="set_notifications",
                                         arguments={"enabled": True}),),
                )
        return None

    def complete(self, transcript: list[Message], tools: list[ToolSpec]) -> ModelResponse:
        last_user = next((m for m in reversed(transcript) if m.role == "user"), None)
        last_tool = next((m for m in reversed(transcript) if m.role == "tool"), None)
        user_text = last_user.text if last_user else ""

        # 1) First pass with no tool result yet: maybe call a session tool.
        if last_tool is None and not self._tool_dispatched:
            tool_turn = self._maybe_tool_call(user_text)
            if tool_turn is not None:
                self._tool_dispatched = True
                return ModelResponse(tool_turn, usage={"input_tokens": 0, "output_tokens": 0})

        # 2) Generate the final answer through the gateway.
        if last_tool is not None:
            # Phrase a confirmation around the tool's result (no extra model spend needed; the
            # tool already produced the user-facing text). Routed as a 'general' turn.
            return ModelResponse(assistant(text=last_tool.text),
                                 usage={"input_tokens": 0, "output_tokens": 0})

        prompt = self._build_prompt(user_text)
        result = self._gateway.complete(
            prompt,
            task="general",
            system=self._system,
            label=self._label,  # per-(tenant,user): scopes cache + cost attribution
        )
        self.last_result = result
        usage = result.response.usage
        # In MOCK mode the answer is grounded extractively in the top scoped chunk (deterministic,
        # checkable, and never able to contain another tenant's evidence because retrieval was
        # tenant-isolated). In live mode we return the model's own grounded generation.
        text = self._grounded_answer() if self._mock else result.response.text
        return ModelResponse(
            assistant(text=text),
            usage={"input_tokens": usage.input_tokens, "output_tokens": usage.output_tokens},
        )

    def _build_prompt(self, user_text: str) -> str:
        if self._evidence:
            return (
                "Use the following product documentation to answer the question.\n\n"
                f"{self._evidence}\n\nQuestion: {user_text}"
            )
        return user_text

    def _grounded_answer(self) -> str:
        """A deterministic, extractive answer from the top scoped chunk (MOCK mode).

        Returns the highest-ranked retrieved chunk's text — the evidence the answer is grounded
        in — so the MOCK demo is reproducible and the eval can check the answer contains the
        expected fact. Because retrieval was scoped to one tenant's index, this text can only ever
        come from that tenant's (or shared) docs; cross-tenant content is impossible by
        construction, which is what the isolation eval asserts.
        """
        if not self._top_evidence:
            return (
                "I couldn't find anything about that in your product documentation. "
                "Try rephrasing, or contact support."
            )
        return self._top_evidence


@dataclass
class Copilot:
    """A stateless, multi-tenant in-app copilot composed from the pattern blueprints.

    Construct it once at process start with the shared, isolated :class:`~tenancy.TenantStores`,
    a :class:`~llm_gateway.Gateway`, a :class:`~app.session_tools.UserDataStore`, and the
    :class:`~app.guardrails.FrontDoor`. Then serve any number of requests: each
    :meth:`answer` / :meth:`stream` call is independent and scoped entirely by the
    :class:`~tenancy.Session` passed in.
    """

    stores: TenantStores
    user_data: UserDataStore
    gateway: Gateway = field(default_factory=Gateway)
    front_door: FrontDoor = field(default_factory=FrontDoor)
    max_turns: int = 4
    retrieval_k: int = DEFAULT_RETRIEVAL_K

    # -- the request path ----------------------------------------------------------------
    def answer(
        self, session: Session, message: str, *, tracer: Tracer | None = None
    ) -> CopilotReply:
        """Handle one in-app turn for ``session`` and return a structured :class:`CopilotReply`.

        The whole turn is wrapped in one observability run span (a fresh tracer per request keeps
        traces independent for a stateless surface). The path is: front door → scoped retrieval →
        agent loop (gateway-backed model + session tools) → structured reply with cost/cache.
        """
        tracer = tracer or Tracer()
        with tracer.run("copilot.turn", attributes={"tenant": session.tenant_id,
                                                     "user": session.user_id}):
            # 1) Front door: abuse bound + content guard, before any spend.
            with tracer.span("front_door", SpanKind.CHAIN):
                verdict: FrontDoorVerdict = self.front_door.check(session.label, message)
            if verdict.blocked:
                return CopilotReply(
                    text="Sorry, I can't help with that request.",
                    blocked=True,
                    block_reason=verdict.reason,
                    label=session.label,
                )
            safe_message = verdict.guard.text  # PII-redacted prompt to forward downstream

            # 2) Scoped retrieval: evidence from ONLY this tenant's index.
            with tracer.retrieval_span(query=safe_message, k=self.retrieval_k):
                hits = self.stores.retrieve(session, safe_message, k=self.retrieval_k)
            evidence, top_evidence, citations = self._format_evidence(hits)

            # 3) Agent loop: gateway-backed model + session-scoped tools.
            tools: ToolRegistry = build_session_tools(session, self.user_data)
            model = _CopilotModel(
                self.gateway,
                evidence=evidence,
                top_evidence=top_evidence,
                tool_names=set(tools.names()),
                label=session.label,
            )
            with tracer.span("agent", SpanKind.CHAIN):
                loop = AgentLoop(model=model, tools=tools, max_turns=self.max_turns)
                result = loop.run(message, system_prompt=SYSTEM_PROMPT)

            # 4) Assemble the structured reply (cost/cache come from the gateway result).
            return self._reply_from(session, result, model, citations, tracer)

    def stream(self, session: Session, message: str) -> Iterator[str]:
        """Stream the answer text token-by-token (the PLAN's "streaming SSE" surface).

        Latency is a product feature on a public copilot, so the surface streams. For a tool turn
        (which has no incremental model generation in MOCK mode) we yield the final text in one
        chunk; for a generated answer we stream the gateway's deltas. Front-door blocks short-
        circuit to a single refusal chunk — never start a stream you shouldn't have started.
        """
        verdict = self.front_door.check(session.label, message)
        if verdict.blocked:
            yield "Sorry, I can't help with that request."
            return
        safe_message = verdict.guard.text
        hits = self.stores.retrieve(session, safe_message, k=self.retrieval_k)
        evidence, top_evidence, _ = self._format_evidence(hits)

        tools = build_session_tools(session, self.user_data)
        model = _CopilotModel(
            self.gateway,
            evidence=evidence,
            top_evidence=top_evidence,
            tool_names=set(tools.names()),
            label=session.label,
        )
        tool_turn = model._maybe_tool_call(safe_message)
        if tool_turn is not None:
            # A tool turn: run the (non-streaming) loop and yield its final text once.
            reply = self.answer(session, message)
            yield reply.text
            return

        # A generated answer. In MOCK mode the answer is the grounded extractive text (kept
        # consistent with answer()), chunked word-by-word to mimic token streaming. In live mode
        # we stream the gateway client's real deltas for true incremental UX.
        mock = os.getenv("COMPANION_MOCK", "1") != "0"
        if mock:
            words = (model._grounded_answer()).split(" ")
            for i, word in enumerate(words):
                yield word if i == 0 else " " + word
            return
        prompt = model._build_prompt(safe_message)
        request = ChatRequest.of(
            self.gateway.default_model, prompt, system=SYSTEM_PROMPT
        )
        yield from self.gateway.client.stream_text(request)

    # -- helpers -------------------------------------------------------------------------
    def _format_evidence(
        self, hits: list[Any]
    ) -> tuple[str, str, tuple[Citation, ...]]:
        """Turn retrieval hits into (evidence block, top-chunk text, citation tuple)."""
        lines: list[str] = []
        citations: list[Citation] = []
        top_text = ""
        for i, h in enumerate(hits):
            meta = h.chunk.metadata
            title = str(meta.get("title", h.chunk.doc_id))
            lines.append(f"[{h.chunk.doc_id}] {title}: {h.chunk.text}")
            citations.append(Citation(doc_id=h.chunk.doc_id, title=title, score=h.score))
            if i == 0:
                top_text = h.chunk.text
        return "\n".join(lines), top_text, tuple(citations)

    def _reply_from(
        self,
        session: Session,
        result: Any,
        model: _CopilotModel,
        citations: tuple[Citation, ...],
        tracer: Tracer,
    ) -> CopilotReply:
        """Build the structured reply from the agent result + the gateway's cost/cache facts."""
        transcript = result.transcript
        tool_msg = next(
            (m for m in transcript if m.role == "tool" and m.tool_result is not None), None
        )
        tool_name = tool_msg.tool_result.name if tool_msg is not None else None
        # Recover the args the assistant sent for that tool (for the audit/UI shape).
        tool_args: dict[str, Any] = {}
        if tool_msg is not None:
            for m in transcript:
                if m.role == "assistant" and m.has_tool_calls:
                    for call in m.tool_calls:
                        if call.name == tool_name:
                            tool_args = dict(call.arguments)

        cost = 0.0
        cached = False
        model_name = ""
        if model.last_result is not None:  # a generated (non-tool) answer hit the gateway
            cost = model.last_result.record.cost_usd
            cached = model.last_result.cached
            model_name = model.last_result.response.model
            # Record the model usage on the active trace for cost-per-user roll-ups.
            usage = model.last_result.response.usage
            with tracer.model_span(
                "generate", model=model_name,
                input_tokens=usage.input_tokens, output_tokens=usage.output_tokens,
                provider=model.last_result.response.provider,
            ):
                pass

        # A tool turn doesn't cite product docs; a grounded answer does.
        cited = () if tool_name is not None else citations
        return CopilotReply(
            text=result.output or (tool_msg.text if tool_msg is not None else ""),
            citations=cited,
            tool=tool_name,
            tool_args=tool_args,
            cost_usd=cost,
            cached=cached,
            model=model_name,
            label=session.label,
        )


__all__ = [
    "Copilot",
    "CopilotReply",
    "Citation",
    "SYSTEM_PROMPT",
]
