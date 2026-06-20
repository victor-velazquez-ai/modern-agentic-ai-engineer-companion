"""The typed message ledger (Ch 12).

An agent loop is, mechanically, a function over a *transcript*: the list of turns exchanged
with the model. Every higher-level pattern — ReAct, plan-execute, reflection (Ch 16) — is a
strategy for *what to append next*, so the ledger is the substrate they all share.

We model four roles, matching the shape every major SDK converges on:

* ``system``    — the standing instructions, exactly one, at the head.
* ``user``      — input from the world (the task, a human reply).
* ``assistant`` — the model's output. It may carry **text**, **tool calls**, or both.
* ``tool``      — the *result* of executing one tool call, threaded back by ``tool_call_id``.

The ledger here is deliberately provider-neutral. The :mod:`agent_loop.model` port is what
translates these typed turns to/from a concrete SDK's wire format, so the loop never touches a
vendor payload directly. Keeping the ledger immutable (frozen dataclasses, append-only history)
is what makes a run reproducible and a failure inspectable after the fact.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Any, Literal

Role = Literal["system", "user", "assistant", "tool"]


@dataclass(frozen=True, slots=True)
class ToolCall:
    """A single tool invocation the model asked for.

    ``id`` correlates the call with its :class:`ToolResult`. ``arguments`` is the decoded
    argument object (a ``dict``); malformed JSON from the model is repaired *before* a
    ``ToolCall`` is constructed (see :mod:`agent_loop.errors`), so by the time a call reaches
    dispatch its arguments are already a real mapping.
    """

    id: str
    name: str
    arguments: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class ToolResult:
    """The outcome of executing one :class:`ToolCall`, threaded back by ``call_id``.

    ``ok=False`` marks an error result. We still send errors back to the model as a normal
    ``tool`` turn (rather than raising) — letting the model *read its mistake and retry* is the
    whole point of the recovery policy; a raised exception would deny it that chance.
    """

    call_id: str
    name: str
    content: str
    ok: bool = True


@dataclass(frozen=True, slots=True)
class Message:
    """One turn in the transcript.

    A turn is either narrative (``text``) or structured (``tool_calls`` on an assistant turn,
    a ``tool_result`` on a tool turn) — frequently text *and* tool calls together, which is why
    they are separate fields rather than a union.
    """

    role: Role
    text: str = ""
    tool_calls: tuple[ToolCall, ...] = field(default_factory=tuple)
    tool_result: ToolResult | None = None

    @property
    def has_tool_calls(self) -> bool:
        return bool(self.tool_calls)


def system(text: str) -> Message:
    """Build the standing-instruction turn."""
    return Message(role="system", text=text)


def user(text: str) -> Message:
    """Build a user/input turn."""
    return Message(role="user", text=text)


def assistant(text: str = "", tool_calls: tuple[ToolCall, ...] = ()) -> Message:
    """Build an assistant turn carrying text, tool calls, or both."""
    return Message(role="assistant", text=text, tool_calls=tuple(tool_calls))


def tool(result: ToolResult) -> Message:
    """Build a tool-result turn from a :class:`ToolResult`."""
    return Message(role="tool", text=result.content, tool_result=result)


@dataclass(slots=True)
class Transcript:
    """An append-only ledger of :class:`Message` turns — the loop's single source of truth.

    The transcript is the *only* mutable state the loop owns. Everything else (the model port,
    the tools, the policy) is pure with respect to it. That is what lets you replay a run, snapshot
    it mid-flight, or hand the same history to a different model.

    Invariants enforced here:

    * a ``system`` turn may appear **only** as the very first message;
    * appends are the only mutation — turns are never edited in place.
    """

    messages: list[Message] = field(default_factory=list)

    @classmethod
    def start(cls, system_prompt: str, first_user: str | None = None) -> "Transcript":
        """Open a transcript with a system prompt and an optional first user turn."""
        t = cls(messages=[system(system_prompt)])
        if first_user is not None:
            t.append(user(first_user))
        return t

    def append(self, message: Message) -> "Transcript":
        """Append a turn, enforcing the system-turn-first invariant. Returns ``self``."""
        if message.role == "system" and self.messages:
            raise ValueError("a 'system' turn may only be the first message in a transcript")
        self.messages.append(message)
        return self

    def extend(self, messages: list[Message]) -> "Transcript":
        """Append several turns in order."""
        for m in messages:
            self.append(m)
        return self

    @property
    def last(self) -> Message:
        """The most recent turn (raises if the transcript is empty)."""
        return self.messages[-1]

    def assistant_turns(self) -> int:
        """How many assistant turns so far — the quantity the turn cap bounds."""
        return sum(1 for m in self.messages if m.role == "assistant")

    def snapshot(self) -> "Transcript":
        """Return a deep-ish copy safe to mutate independently (turns are immutable)."""
        return replace(self, messages=list(self.messages))

    def __len__(self) -> int:
        return len(self.messages)

    def __iter__(self):
        return iter(self.messages)
