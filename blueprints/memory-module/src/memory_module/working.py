"""Short-term **working memory**: the live conversation window under a token budget (Ch 14).

The working window is what the agent actually sends to the model each turn. It is finite, so the
central policy here is: **what happens when it overflows?** The wrong answer (and a common bug) is
to silently drop the oldest turns — the agent then "forgets" mid-conversation with no trace. The
right answer is to *compact*: fold the evicted turns into a rolling summary (see
:mod:`memory_module.summarize`) so their information survives in a smaller footprint.

Token counting here is a cheap word/char heuristic so the module has **zero heavy dependencies**.
For production, swap :func:`estimate_tokens` for a real tokenizer (e.g. ``tiktoken``) — the policy
above is unchanged.
"""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass, field
from typing import Any, Literal

from .summarize import MockSummarizer, Summarizer

Role = Literal["system", "user", "assistant", "tool"]


def estimate_tokens(text: str) -> int:
    """Rough token estimate without a tokenizer dependency.

    Heuristic: ~4 characters per token, floored at the word count. Good enough for budgeting and
    deterministic in tests. Replace with ``tiktoken`` in production for exact accounting.
    """
    if not text:
        return 0
    by_chars = math.ceil(len(text) / 4)
    by_words = len(text.split())
    return max(1, by_chars, by_words)


@dataclass(frozen=True, slots=True)
class Message:
    """One turn in the conversation ledger."""

    role: Role
    content: str

    @property
    def tokens(self) -> int:
        return estimate_tokens(self.content)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Message":
        return cls(role=data["role"], content=data["content"])


@dataclass
class WorkingMemory:
    """A bounded conversation window with summarize-on-overflow compaction.

    Parameters
    ----------
    token_budget:
        Soft cap on the live window (system prompt + rolling summary + recent turns). When adding
        a turn would exceed it, the oldest non-system turns are compacted until the window fits.
    summarizer:
        Strategy that produces the rolling summary. Defaults to the offline
        :class:`~memory_module.summarize.MockSummarizer` (no API spend).
    keep_last:
        Always retain at least this many of the most-recent turns verbatim, even under pressure,
        so the agent never loses immediate context to summarization.
    summary_budget_ratio:
        Fraction of ``token_budget`` the rolling summary is allowed to occupy. Bounding the
        summary as a *fraction of the window* is what stops a long conversation from producing a
        summary that no longer fits the window it was meant to shrink.
    """

    token_budget: int = 512
    summarizer: Summarizer = field(default_factory=MockSummarizer)
    keep_last: int = 2
    summary_budget_ratio: float = 0.5

    system_prompt: str = ""
    rolling_summary: str = ""
    messages: list[Message] = field(default_factory=list)
    #: count of turns folded into the rolling summary over this window's life
    compactions: int = 0

    # -- mutation ---------------------------------------------------------------------------

    def add(self, role: Role, content: str) -> None:
        """Append a turn, then compact if the window now exceeds its budget."""
        if role == "system" and not self.system_prompt:
            # the first system message seeds the (always-retained) system prompt
            self.system_prompt = content
            return
        self.messages.append(Message(role=role, content=content))
        self._compact_if_needed()

    def add_message(self, message: Message) -> None:
        self.add(message.role, message.content)

    # -- reads ------------------------------------------------------------------------------

    def used_tokens(self) -> int:
        """Total estimated tokens of the current live window."""
        total = estimate_tokens(self.system_prompt) + estimate_tokens(self.rolling_summary)
        return total + sum(m.tokens for m in self.messages)

    def render(self) -> list[Message]:
        """The window as the model would receive it: system, then summary, then recent turns."""
        out: list[Message] = []
        if self.system_prompt:
            out.append(Message("system", self.system_prompt))
        if self.rolling_summary:
            out.append(Message("system", f"Summary of earlier conversation: {self.rolling_summary}"))
        out.extend(self.messages)
        return out

    # -- compaction policy ------------------------------------------------------------------

    def _compact_if_needed(self) -> None:
        """Summarize-then-evict the oldest turns until the window fits the budget.

        Never evicts the system prompt (it lives outside ``messages``) and never evicts the last
        ``keep_last`` turns. If even that floor exceeds the budget, we stop rather than loop
        forever — better an over-budget tail than a dropped recent turn.
        """
        # Bound the rolling summary to a fraction of the window (in chars; ~4 chars/token) so it
        # can never outgrow the budget it exists to protect.
        summary_max_chars = max(40, int(self.token_budget * self.summary_budget_ratio) * 4)
        while self.used_tokens() > self.token_budget and len(self.messages) > self.keep_last:
            evict = self.messages[: len(self.messages) - self.keep_last]
            if not evict:
                break
            # fold the oldest single turn at a time so the summary stays proportional
            oldest = evict[0]
            self.rolling_summary = self.summarizer.summarize(
                self.rolling_summary, [oldest], max_chars=summary_max_chars
            )
            self.messages.pop(0)
            self.compactions += 1

    # -- persistence shape ------------------------------------------------------------------

    def snapshot(self) -> dict[str, Any]:
        """Serialize the window for the persistence backend."""
        return {
            "token_budget": self.token_budget,
            "keep_last": self.keep_last,
            "summary_budget_ratio": self.summary_budget_ratio,
            "system_prompt": self.system_prompt,
            "rolling_summary": self.rolling_summary,
            "compactions": self.compactions,
            "messages": [m.to_dict() for m in self.messages],
        }

    def restore(self, snapshot: dict[str, Any]) -> None:
        """Load a window previously produced by :meth:`snapshot`."""
        self.token_budget = snapshot.get("token_budget", self.token_budget)
        self.keep_last = snapshot.get("keep_last", self.keep_last)
        self.summary_budget_ratio = snapshot.get("summary_budget_ratio", self.summary_budget_ratio)
        self.system_prompt = snapshot.get("system_prompt", "")
        self.rolling_summary = snapshot.get("rolling_summary", "")
        self.compactions = snapshot.get("compactions", 0)
        self.messages = [Message.from_dict(d) for d in snapshot.get("messages", [])]
