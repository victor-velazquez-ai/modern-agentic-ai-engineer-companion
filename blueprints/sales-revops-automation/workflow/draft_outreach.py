"""Draft outreach: a grounded, *unsent* follow-up the rep reviews (composes rag-pipeline + agent-loop).

This is where the PLAN's two non-negotiables live in code:

* **Grounded in what has worked.** The draft is not invented. The winning-messaging playbook
  (``data/playbook.md``) is ingested -> chunked -> embedded -> indexed and retrieved with the
  **``rag-pipeline``** blueprint (hybrid search + rerank), so the follow-up reuses the messaging
  that actually closed past deals (Ch 13). Hybrid search matters here: keyword-y tokens like
  "SOC2", "data residency", or a buyer's stated deadline are exactly what the keyword channel
  rescues when the dense channel smears them.
* **A human sends, not the agent.** The drafting runs on the **``agent-loop``** blueprint, but the
  output is a :class:`DraftEmail` whose ``status`` is :attr:`SendStatus.DRAFT` — *never sent*.
  Outbound under an agent's name unsupervised is brand risk (PLAN; Ch 20 human-on-send gate). The
  data model makes the rep the sender by construction: there is no ``send()`` here.

And the guardrail the PLAN calls out explicitly (Ch 22/41): a **wrong-recipient check**. Before a
draft is allowed to leave the workflow it must be addressed to a contact that belongs to *this*
account (matching domain / known contact). A draft to the wrong contact is held, not produced — a
mis-sent email is a confidentiality and brand incident, the most expensive failure mode here.

MOCK by default: the RAG mock embedder/reranker and a scripted ``agent-loop`` model mean drafting
is deterministic and free. Swap in a gateway-backed ``ModelPort`` (``COMPANION_MOCK=0``) for live
generation; the retrieval, the guardrail, and the human-on-send gate are unchanged.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Mapping

from revops.compose import data_dir, ensure_on_path

ensure_on_path()

from agent_loop import (  # noqa: E402
    AgentLoop,
    MockModel,
    ToolCall,
    ToolRegistry,
    assistant,
    tool as tool_decorator,
)
from rag_pipeline import (  # noqa: E402
    Document,
    HybridRetriever,
    InMemoryVectorStore,
    MockReranker,
    chunk_documents,
    embed_chunks,
)

try:  # observability is optional at runtime; degrade to a no-op if the sibling is absent.
    from observability_stack import SpanKind, Tracer  # noqa: E402

    _HAVE_OBS = True
except Exception:  # pragma: no cover - exercised only when the sibling is missing
    _HAVE_OBS = False

_PLAYBOOK_PATH = data_dir() / "playbook.md"


class SendStatus(str, Enum):
    """The disposition of a draft — it never reaches a terminal "sent" state inside this workflow.

    The agent only ever produces :attr:`DRAFT`. :attr:`HELD` means a guardrail (wrong recipient)
    refused to even hand the rep a draft. Sending is a human action outside this module, on purpose.
    """

    DRAFT = "draft"   # ready for a human to review and send
    HELD = "held"     # a guardrail fired; not handed to the rep as-is

    def __str__(self) -> str:
        return self.value


@dataclass(frozen=True, slots=True)
class GroundingSource:
    """One retrieved playbook snippet behind a draft — the citation the rep can audit."""

    chunk_id: str
    text: str
    title: str = ""
    score: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "chunk_id": self.chunk_id,
            "title": self.title,
            "text": self.text,
            "score": round(self.score, 4),
        }


@dataclass(frozen=True, slots=True)
class DraftEmail:
    """A drafted, **unsent** follow-up email plus its grounding and guardrail verdict.

    There is deliberately no ``send`` method. A UI renders ``to``/``subject``/``body`` + the
    ``sources`` for the rep, who edits and sends from their own mail client. ``status`` is
    :attr:`SendStatus.DRAFT` for a clean draft and :attr:`SendStatus.HELD` when the wrong-recipient
    guardrail refused it (``hold_reason`` says why).
    """

    account_id: str
    to: str
    subject: str
    body: str
    sources: tuple[GroundingSource, ...] = field(default_factory=tuple)
    status: SendStatus = SendStatus.DRAFT
    hold_reason: str = ""

    @property
    def grounded(self) -> bool:
        """A draft must cite at least one playbook source — an uncited draft is a bug."""
        return bool(self.sources)

    @property
    def held(self) -> bool:
        return self.status is SendStatus.HELD

    def source_ids(self) -> list[str]:
        return [s.chunk_id for s in self.sources]

    def to_dict(self) -> dict[str, Any]:
        return {
            "account_id": self.account_id,
            "to": self.to,
            "subject": self.subject,
            "body": self.body,
            "status": str(self.status),
            "hold_reason": self.hold_reason,
            "sources": [s.to_dict() for s in self.sources],
        }


# --- grounding: retrieve winning messaging via the rag-pipeline blueprint ----------------------


def build_messaging_index(playbook_path: Path | None = None) -> HybridRetriever:
    """Ingest the winning-messaging playbook into a ``rag-pipeline`` retriever (offline, free).

    Each ``##`` section of the playbook becomes one :class:`~rag_pipeline.Document`, so a retrieved
    chunk maps back to a named play. Uses the in-memory store + mock embedder by default — the same
    composition the rag-pipeline demo uses, no fork.
    """
    path = playbook_path or _PLAYBOOK_PATH
    text = path.read_text(encoding="utf-8")

    documents: list[Document] = []
    section_id = 0
    for block in text.split("\n## "):
        block = block.strip()
        if not block or block.startswith("# "):
            continue  # skip the title / preamble block
        # The section heading is the first line; carry it as metadata so a retrieved chunk knows
        # which named play it belongs to (chunking flattens newlines, so we can't recover it later).
        heading = block.splitlines()[0].strip()
        documents.append(
            Document(id=f"play-{section_id}", text=block, metadata={"title": heading})
        )
        section_id += 1

    store = InMemoryVectorStore()
    store.add(embed_chunks(chunk_documents(documents)))
    return HybridRetriever(store)


def retrieve_grounding(
    retriever: HybridRetriever, query: str, *, k: int = 3
) -> list[GroundingSource]:
    """Hybrid-retrieve the top playbook snippets for ``query`` and rerank them (rag-pipeline)."""
    hits = retriever.retrieve(query, k=max(k * 2, 4))
    reranked = MockReranker().rerank(query, hits, top_n=k)
    return [
        GroundingSource(
            chunk_id=s.chunk.id,
            text=s.chunk.text,
            title=str(s.chunk.metadata.get("title", "")),
            score=s.score,
        )
        for s in reranked
    ]


# --- the wrong-recipient guardrail (Ch 22/41) --------------------------------------------------


def recipient_is_valid(account: Mapping[str, Any], to_email: str) -> tuple[bool, str]:
    """Return ``(ok, reason)`` — is ``to_email`` a legitimate contact for *this* account?

    The expensive failure here is a draft addressed to the wrong person (a different account's
    contact, or a free-text address that slipped in). Two cheap, deterministic checks gate it:

    * the address must be one of the account's **known contacts** (the primary contact today; a
      real CRM has a contacts list), **or**
    * its **domain must match the account's domain** (same company).

    Anything else is held. In production you would also block external/personal domains for
    confidential content; the contract here is the same — deny unless the recipient provably
    belongs to the account.
    """
    to_email = (to_email or "").strip().lower()
    if "@" not in to_email:
        return False, f"recipient {to_email!r} is not a valid email address"

    known = {
        str(account.get("primary_contact", {}).get("email", "")).strip().lower()
    }
    known.discard("")
    if to_email in known:
        return True, "recipient is a known account contact"

    account_domain = str(account.get("domain", "")).strip().lower()
    recipient_domain = to_email.split("@", 1)[1]
    if account_domain and recipient_domain == account_domain:
        return True, "recipient domain matches the account domain"

    return (
        False,
        f"recipient {to_email!r} (domain {recipient_domain!r}) does not belong to account "
        f"{account.get('account_id')!r} (domain {account_domain!r}); held to prevent mis-send",
    )


# --- the drafting agent (agent-loop) -----------------------------------------------------------


@tool_decorator(
    "compose_followup",
    "Compose a follow-up email grounded in the retrieved winning-messaging snippets. "
    "Call exactly once with a subject and a body under ~150 words.",
    {
        "type": "object",
        "properties": {
            "subject": {"type": "string", "description": "The email subject line."},
            "body": {"type": "string", "description": "The email body (<= ~150 words)."},
        },
        "required": ["subject", "body"],
    },
)
def _compose_followup(subject: str, body: str) -> str:
    """The agent-loop tool: a typed channel for the draft. We keep the *arguments* (the draft);
    the return value is just a confirmation the loop reads to end its turn."""
    return f"draft composed (subject {len(subject)} chars, body {len(body)} chars)"


def _drafting_model(account: Mapping[str, Any], sources: list[GroundingSource]) -> MockModel:
    """Script a deterministic 'brain' that composes a grounded follow-up from the sources.

    This stands in for a generation model (Ch 20). The body is assembled from the account context
    and the top retrieved play, so the draft is visibly *grounded* — and reproducible/free. On the
    live path you inject a gateway-backed ``ModelPort`` here; the loop, the tool, the guardrail, and
    the human-on-send gate do not change.
    """
    contact = account.get("primary_contact", {})
    contact_name = str(contact.get("name", "there")).split()[0] if contact.get("name") else "there"
    next_step = str(account.get("next_step") or "the agreed next step")
    close_date = account.get("close_date")
    # The named play behind the draft (its heading, carried as chunk metadata) — the audit trail to
    # *which* winning message we reused, without dumping the whole snippet into the subject line.
    play_title = (sources[0].title if sources and sources[0].title else "your evaluation").strip()

    timeline = f" To keep us on track for {close_date}, " if close_date else " "
    body = (
        f"Hi {contact_name},\n\n"
        f"Thanks for the time on our last call. Following up on {next_step.lower()} - "
        f"this is the path that has worked best for accounts like yours "
        f"({play_title.lower()}).{timeline}"
        f"I'll get that over to you and keep things moving. Let me know if anything's missing.\n\n"
        f"Best,\n{str(account.get('owner', 'your rep')).split('@')[0].capitalize()}"
    )
    subject = f"Follow-up: {play_title}"

    return MockModel(
        [
            assistant(
                text="Drafting a grounded follow-up from the retrieved winning messaging.",
                tool_calls=(
                    ToolCall(
                        id="d1",
                        name="compose_followup",
                        arguments={"subject": subject, "body": body},
                    ),
                ),
            ),
            lambda _hist: assistant(text="Draft ready for the rep to review and send."),
        ]
    )


def _extract_draft(result: Any) -> tuple[str, str]:
    """Read the ``compose_followup`` arguments back off the loop's transcript (subject, body)."""
    transcript = getattr(result, "transcript", None)
    if transcript is None:
        return "", ""
    for msg in transcript:
        for call in getattr(msg, "tool_calls", ()):
            if call.name == "compose_followup":
                args = call.arguments or {}
                return str(args.get("subject", "")), str(args.get("body", ""))
    return "", ""


def draft_followup(
    account: Mapping[str, Any],
    *,
    to: str | None = None,
    retriever: HybridRetriever | None = None,
    tracer: "Tracer | None" = None,
) -> DraftEmail:
    """Produce a grounded, **unsent** follow-up draft for one account.

    Pipeline (each step traced when an observability tracer is active):

    1. **retrieve** winning-messaging snippets for this account's situation (``rag-pipeline``);
    2. **guard** the recipient — if ``to`` doesn't belong to the account, return a HELD draft and
       never compose to the wrong person;
    3. **draft** the email on the ``agent-loop`` (scripted, offline) using the retrieved grounding;
    4. return a :attr:`SendStatus.DRAFT` — *the rep sends it*, this workflow does not.

    ``to`` defaults to the account's primary contact. Pass an explicit address to exercise the
    wrong-recipient guardrail.
    """
    account_id = str(account.get("account_id", ""))
    to_email = (to or str(account.get("primary_contact", {}).get("email", ""))).strip()

    # --- 1. retrieve grounding -----------------------------------------------------------------
    retriever = retriever or build_messaging_index()
    query = " ".join(
        str(account.get(k, "")) for k in ("next_step", "industry", "notes")
    ).strip() or "follow up after a sales call"

    def _do_retrieve() -> list[GroundingSource]:
        return retrieve_grounding(retriever, query, k=3)

    if tracer is not None and _HAVE_OBS:
        with tracer.retrieval_span("retrieve_messaging", query=query, k=3):
            sources = _do_retrieve()
    else:
        sources = _do_retrieve()

    # --- 2. wrong-recipient guardrail (before we ever compose) ---------------------------------
    ok, reason = recipient_is_valid(account, to_email)
    if not ok:
        return DraftEmail(
            account_id=account_id,
            to=to_email,
            subject="",
            body="",
            sources=tuple(sources),
            status=SendStatus.HELD,
            hold_reason=reason,
        )

    # --- 3. draft on the agent-loop ------------------------------------------------------------
    registry = ToolRegistry([_compose_followup])
    loop = AgentLoop(model=_drafting_model(account, sources), tools=registry, max_turns=4)
    system_prompt = (
        "You are a RevOps outreach assistant. You DRAFT follow-ups grounded in the provided "
        "winning-messaging snippets; a human reviews and sends. Reference one specific thing from "
        "the call, state the single next step, keep it under ~150 words, and never invent facts "
        "or claims not supported by the grounding."
    )
    task = (
        f"Account: {account.get('name')} ({account_id}).\n"
        f"Next step: {account.get('next_step')!r}. Close date: {account.get('close_date')!r}.\n\n"
        f"Grounding (winning messaging that has worked before):\n"
        + "\n---\n".join(s.text for s in sources)
        + "\n\nDraft a grounded follow-up email for the rep to review and send."
    )

    def _do_draft() -> Any:
        return loop.run(task, system_prompt=system_prompt)

    if tracer is not None and _HAVE_OBS:
        with tracer.span(f"draft:{account_id}", SpanKind.CHAIN):
            result = _do_draft()
    else:
        result = _do_draft()

    subject, body = _extract_draft(result)
    return DraftEmail(
        account_id=account_id,
        to=to_email,
        subject=subject,
        body=body,
        sources=tuple(sources),
        status=SendStatus.DRAFT,
    )
