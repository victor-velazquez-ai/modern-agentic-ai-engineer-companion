"""Escalation policy — the *should-I-not-proceed?* gate (Ch 20 HITL, Ch 41 gating actions).

The single most important judgment in a support agent is **knowing when to stop**. Deflecting a
known question is cheap to get right; the expensive failures are the ones where the agent should
have handed off and didn't — it argued with an angry customer, approved an out-of-policy refund,
or acted on a request it didn't actually understand. This module is where those stop conditions
live, in code, as a small ordered set of triggers checked *before* the agent is allowed to act.

Design choices a senior would defend:

* **Deny-by-default for actions.** An action proceeds only if it is in-policy *and* nothing
  here fired. The autonomy dial (PLAN.md) starts at answer-only; you enable action types one at
  a time as the eval set shows the agent matches human decisions.
* **Triggers are data, not scattered ``if``\\s.** Each trigger has a name, a predicate, and a
  reason string — so a new rule is one entry, the eval set can target a trigger by name, and an
  audit log can say *which* rule escalated a ticket.
* **Cheap, deterministic signals.** Keyword/intent heuristics here, on purpose: they run for
  free in MOCK mode and are the obvious first line. In production you'd back the *same* trigger
  contract with a classifier or a gateway guard (Ch 41) — the call site does not change.

Nothing here calls a model or the network. Replace the keyword sets with *your* refund/abuse
rules; keep the deny-by-default shape.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Callable

# --- Tunable thresholds / rules (edit these to your domain) --------------------------------

# Refunds at or below this amount may be issued by the agent when nothing else escalates.
# Above it, money leaves the building only with a human's sign-off (an irreversible action).
REFUND_AUTO_APPROVE_LIMIT_USD = 50.0

# A retrieval confidence floor for answer-only turns. Below it, the agent does not guess — a
# weak grounding signal is itself an escalation trigger (don't hallucinate a policy answer).
MIN_GROUNDING_CONFIDENCE = 0.15

# Phrases that signal an angry / churn-risk customer who should reach a person quickly.
_ANGER_TERMS = (
    "furious", "ridiculous", "unacceptable", "lawyer", "sue", "cancel my account",
    "worst", "scam", "terrible", "speak to a human", "speak to a manager", "fed up",
)

# Phrases that signal abuse of the refund path (serial refunder, threats, coercion).
_REFUND_ABUSE_TERMS = (
    "refund again", "every month", "chargeback", "or i'll", "or i will", "dispute it",
    "third refund", "always broken",
)

# Intents that are irreversible or out-of-policy for an autonomous agent to perform.
_OUT_OF_POLICY_TERMS = (
    "delete my account", "delete all", "wipe", "gdpr erase", "close the company account",
    "transfer ownership", "change the owner", "legal hold",
)

_MONEY_RE = re.compile(r"\$?\s*(\d+(?:\.\d{1,2})?)")


@dataclass(frozen=True)
class TicketContext:
    """Everything a policy check needs about one ticket, in one bag.

    Kept separate from :class:`~app.decision.Decision` because policy is evaluated *before* a
    decision exists — these are the inputs to the stop/proceed gate.

    Attributes
    ----------
    text:
        The customer's message (lower-cased comparisons are done internally).
    intent:
        A coarse intent label the agent assigned (e.g. ``"refund"``, ``"password_reset"``,
        ``"order_status"``, ``"faq"``). Used to scope money/abuse rules to the relevant tickets.
    amount_usd:
        For refund-type tickets, the requested amount (``None`` if not applicable/unknown).
    grounding_confidence:
        Retrieval/rerank confidence for an answer-only turn, in ``[0, 1]``.
    """

    text: str
    intent: str = "faq"
    amount_usd: float | None = None
    grounding_confidence: float = 1.0

    def lower(self) -> str:
        return self.text.lower()


@dataclass(frozen=True)
class EscalationTrigger:
    """A named reason to hand a ticket to a human.

    ``predicate(ctx) -> bool``: fired or not. ``reason`` is the human-readable explanation that
    rides into :meth:`~app.decision.Decision.escalate` and the audit log.
    """

    name: str
    reason: str
    predicate: Callable[[TicketContext], bool]


def _contains_any(text: str, terms: tuple[str, ...]) -> bool:
    return any(term in text for term in terms)


def _angry_customer(ctx: TicketContext) -> bool:
    return _contains_any(ctx.lower(), _ANGER_TERMS)


def _refund_abuse(ctx: TicketContext) -> bool:
    return _contains_any(ctx.lower(), _REFUND_ABUSE_TERMS)


def _out_of_policy(ctx: TicketContext) -> bool:
    return _contains_any(ctx.lower(), _OUT_OF_POLICY_TERMS)


def _refund_over_limit(ctx: TicketContext) -> bool:
    if ctx.intent != "refund":
        return False
    amount = ctx.amount_usd
    if amount is None:  # fall back to any $-amount mentioned in the message
        m = _MONEY_RE.search(ctx.text)
        amount = float(m.group(1)) if m else None
    return amount is not None and amount > REFUND_AUTO_APPROVE_LIMIT_USD


def _low_grounding(ctx: TicketContext) -> bool:
    # Only an answer-only ("faq") turn escalates on weak grounding; action intents have their
    # own gates. Don't guess a policy answer the corpus doesn't support.
    return ctx.intent == "faq" and ctx.grounding_confidence < MIN_GROUNDING_CONFIDENCE


# The ordered policy. First match wins, so put the most serious / most specific rules first.
DEFAULT_TRIGGERS: tuple[EscalationTrigger, ...] = (
    EscalationTrigger(
        "out_of_policy",
        "request is irreversible or out of policy for an autonomous agent",
        _out_of_policy,
    ),
    EscalationTrigger(
        "refund_abuse",
        "pattern consistent with refund abuse / coercion",
        _refund_abuse,
    ),
    EscalationTrigger(
        "angry_customer",
        "customer appears angry or a churn/legal risk; a human should respond",
        _angry_customer,
    ),
    EscalationTrigger(
        "refund_over_limit",
        f"refund exceeds the ${REFUND_AUTO_APPROVE_LIMIT_USD:g} auto-approve limit",
        _refund_over_limit,
    ),
    EscalationTrigger(
        "low_grounding",
        "retrieval confidence too low to answer safely; not guessing a policy answer",
        _low_grounding,
    ),
)


@dataclass(frozen=True)
class EscalationPolicy:
    """An ordered set of triggers; :meth:`evaluate` returns the first that fires (or ``None``).

    Construct with your own triggers to localise refund/abuse rules. The default is
    :data:`DEFAULT_TRIGGERS`.
    """

    triggers: tuple[EscalationTrigger, ...] = DEFAULT_TRIGGERS

    def evaluate(self, ctx: TicketContext) -> EscalationTrigger | None:
        """Return the first trigger that fires for ``ctx``, or ``None`` to allow the turn."""
        for trigger in self.triggers:
            if trigger.predicate(ctx):
                return trigger
        return None

    def should_escalate(self, ctx: TicketContext) -> bool:
        return self.evaluate(ctx) is not None


def default_policy() -> EscalationPolicy:
    """The blueprint's default escalation policy (deny-by-default for risky turns)."""
    return EscalationPolicy()
