"""The core agent loop (Ch 12) — observe -> decide -> act -> observe.

This is the substrate. Strip away ReAct, plan-execute, and reflection (Ch 16) and what remains
is this cycle:

1. **decide** — ask the model for the next assistant turn, given the transcript and the tools;
2. **stop?** — if the turn has no tool calls, the model is *done talking*: that text is the
   answer, return it;
3. **act** — otherwise dispatch every tool call, repairing malformed ones, isolating failures;
4. **observe** — append the tool results to the transcript and loop.

Around that cycle sit the four things a *toy* loop omits and a shipped one cannot:

* **a turn cap** so a confused model can't loop forever (the single most important safety bound);
* **tool-error recovery** — a failed call becomes a result the model reads and retries, governed
  by a :class:`~agent_loop.errors.RetryPolicy` that stops the bleed if it keeps failing;
* **malformed-call repair** — broken JSON arguments are fixed where safe, reported where not;
* **cancellation** — a caller-supplied predicate checked each turn, so a run can be cut from
  outside (a deadline, a user "stop", a budget guard) without a thread-kill.

The loop owns exactly one piece of mutable state, the :class:`~agent_loop.messages.Transcript`.
Everything else is injected and pure, which is what makes a run reproducible and a stop reason
auditable.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Callable

from .errors import MalformedToolCall, RetryPolicy, repair_tool_call
from .messages import Message, ToolResult, Transcript, tool as tool_message
from .model import ModelPort
from .tools import ToolRegistry


class StopReason(str, Enum):
    """Why the loop returned — every terminal path names itself, so a run is never a mystery."""

    COMPLETED = "completed"            # model produced a final answer (no tool calls)
    MAX_TURNS = "max_turns"            # hit the turn cap before finishing
    RECOVERY_EXHAUSTED = "recovery_exhausted"  # too many consecutive failing turns
    CANCELLED = "cancelled"            # the cancel predicate fired


@dataclass(frozen=True, slots=True)
class AgentResult:
    """The outcome of a run: the final text, why it stopped, and the full transcript.

    ``output`` is the last assistant *text* (empty if the loop stopped before the model spoke a
    final answer). ``transcript`` is the complete ledger — keep it; it's your trace, your replay
    input, and what you'd attach to an eval case.
    """

    output: str
    stop_reason: StopReason
    transcript: Transcript
    turns: int

    @property
    def ok(self) -> bool:
        return self.stop_reason is StopReason.COMPLETED


# A cancel predicate is checked before each model call; return True to stop the run.
CancelFn = Callable[[Transcript], bool]


@dataclass(slots=True)
class AgentLoop:
    """A configured, reusable agent loop.

    Construct it once with a model port, a tool registry, and the policy knobs; call :meth:`run`
    per task. Nothing about a single run mutates the loop, so one configured ``AgentLoop`` is safe
    to reuse across tasks (each :meth:`run` gets its own transcript).

    Parameters
    ----------
    model:
        The :class:`~agent_loop.model.ModelPort`. Defaults to the offline mock via
        :func:`~agent_loop.model.default_model` — so an ``AgentLoop()`` with no arguments runs
        free. Inject an ``llm-gateway`` client here for the live path.
    tools:
        The :class:`~agent_loop.tools.ToolRegistry` the model may call. Empty by default (a
        loop with no tools is just a single model turn).
    max_turns:
        Hard cap on assistant turns. The most important knob: tune it to the *longest legitimate*
        plan for your task, then add a small margin. Too low truncates real work; too high lets a
        stuck model waste tokens. See the README for tuning guidance.
    retry_policy:
        Governs consecutive tool-failure tolerance (see
        :class:`~agent_loop.errors.RetryPolicy`).
    on_event:
        Optional observer called with ``(name, payload)`` at each step (``"decide"``, ``"act"``,
        ``"stop"``). The seam the ``observability-stack`` blueprint plugs into; ``None`` by
        default so the loop has zero tracing overhead unless you ask for it.
    """

    model: ModelPort = field(default=None)  # type: ignore[assignment]
    tools: ToolRegistry = field(default_factory=ToolRegistry)
    max_turns: int = 8
    retry_policy: RetryPolicy = field(default_factory=RetryPolicy)
    on_event: Callable[[str, dict], None] | None = None

    def __post_init__(self) -> None:
        if self.model is None:
            from .model import default_model

            self.model = default_model()
        if self.max_turns < 1:
            raise ValueError("max_turns must be >= 1")

    def run(
        self,
        task: str,
        *,
        system_prompt: str = "You are a helpful assistant. Use tools when they help.",
        cancel: CancelFn | None = None,
    ) -> AgentResult:
        """Run the loop on one ``task`` and return its :class:`AgentResult`.

        ``task`` seeds the first user turn; ``system_prompt`` is the standing instruction. Pass
        ``cancel`` to stop a run from outside — it is checked *before* each model call, so a fired
        predicate costs no extra model spend.
        """
        transcript = Transcript.start(system_prompt, first_user=task)
        return self.resume(transcript, cancel=cancel)

    def resume(self, transcript: Transcript, *, cancel: CancelFn | None = None) -> AgentResult:
        """Continue an existing transcript — the reentrant core :meth:`run` delegates to.

        Useful for human-in-the-loop pauses (append a user turn and resume) and for tests that
        want to drive the loop from a hand-built history.
        """
        consecutive_failures = 0

        while True:
            turns = transcript.assistant_turns()

            if cancel is not None and cancel(transcript):
                return self._finish(transcript, StopReason.CANCELLED, turns)

            if turns >= self.max_turns:
                return self._finish(transcript, StopReason.MAX_TURNS, turns)

            # --- decide ---------------------------------------------------------------
            self._emit("decide", {"turn": turns + 1})
            response = self.model.complete(list(transcript), self.tools.specs())
            assistant_msg = response.message
            transcript.append(assistant_msg)
            turns = transcript.assistant_turns()

            # --- stop? ----------------------------------------------------------------
            if not assistant_msg.has_tool_calls:
                return self._finish(transcript, StopReason.COMPLETED, turns)

            # --- act ------------------------------------------------------------------
            results = self._dispatch(assistant_msg)
            self._emit("act", {"turn": turns, "results": len(results)})

            # --- observe --------------------------------------------------------------
            for r in results:
                transcript.append(tool_message(r))

            # --- recovery accounting --------------------------------------------------
            if results and all(not r.ok for r in results):
                consecutive_failures += 1
                if self.retry_policy.exhausted(consecutive_failures):
                    return self._finish(transcript, StopReason.RECOVERY_EXHAUSTED, turns)
            else:
                consecutive_failures = 0

    # -- internals -----------------------------------------------------------------------

    def _dispatch(self, assistant_msg: Message) -> list[ToolResult]:
        """Repair-then-execute every tool call in one assistant turn.

        Malformed calls (bad JSON args, missing name) never reach the registry: they are turned
        into error results here, so the model gets a precise "fix your call" message back. Valid
        calls go to :meth:`ToolRegistry.execute`, which itself can only return a result, never
        raise. Net effect: this method *always* returns one result per call, failures isolated.
        """
        results: list[ToolResult] = []
        for raw in assistant_msg.tool_calls:
            try:
                call = repair_tool_call(id=raw.id, name=raw.name, arguments=raw.arguments)
            except MalformedToolCall as exc:
                results.append(
                    ToolResult(call_id=raw.id, name=str(raw.name), content=str(exc), ok=False)
                )
                continue
            results.append(self.tools.execute(call))
        return results

    def _finish(self, transcript: Transcript, reason: StopReason, turns: int) -> AgentResult:
        output = self._final_text(transcript) if reason is StopReason.COMPLETED else ""
        self._emit("stop", {"reason": reason.value, "turns": turns})
        return AgentResult(output=output, stop_reason=reason, transcript=transcript, turns=turns)

    @staticmethod
    def _final_text(transcript: Transcript) -> str:
        for m in reversed(transcript.messages):
            if m.role == "assistant" and not m.has_tool_calls:
                return m.text
        return ""

    def _emit(self, name: str, payload: dict) -> None:
        if self.on_event is not None:
            self.on_event(name, payload)


def run_agent(
    task: str,
    *,
    model: ModelPort | None = None,
    tools: ToolRegistry | None = None,
    max_turns: int = 8,
    system_prompt: str = "You are a helpful assistant. Use tools when they help.",
    cancel: CancelFn | None = None,
) -> AgentResult:
    """One-call convenience wrapper around :class:`AgentLoop` for scripts and the demo.

    Everything defaults to the free, offline path: omit ``model`` and you get the mock, omit
    ``tools`` and the model simply answers in one turn.
    """
    loop = AgentLoop(
        model=model,  # type: ignore[arg-type]
        tools=tools or ToolRegistry(),
        max_turns=max_turns,
    )
    return loop.run(task, system_prompt=system_prompt, cancel=cancel)
