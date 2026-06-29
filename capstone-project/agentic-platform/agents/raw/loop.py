"""The framework-free agent loop (Ch 12, 20) — the engine the whole platform grows around.

Strip away ReAct, plan-execute, and reflection (Ch 16), strip away LangGraph and Pydantic AI
(Ch 18), and what remains is this cycle:

1. **decide** — ask the model for the next assistant turn, given the transcript and the tools;
2. **stop?** — a turn with no tool calls means the model is *done talking*: return that text;
3. **gate** — before acting, run each requested call through the :class:`~agents.approvals.ApprovalGate`;
   a held (risky) call pauses the run for a human; a denied call is reported back to the model;
4. **act** — dispatch the approved calls, repairing malformed ones, isolating failures;
5. **observe** — append the tool results to the transcript and loop.

Around that cycle sit the things a *toy* loop omits and a shipped one cannot: a **turn cap** (the
single most important safety bound), **tool-error recovery** governed by a
:class:`~agents.tools.errors.RetryPolicy`, **malformed-call repair**, **cancellation**, and — the
platform addition over the blueprint — the **human-in-the-loop approval gate** (Ch 20). The loop
owns exactly one piece of mutable state, the :class:`~agents.tools.messages.Transcript`; that, plus
the snapshot taken on a hold, is what makes a paused run resumable and a stop reason auditable.

This is the capstone's ``agents/raw/`` — the integrated counterpart of the ``agent-loop``
blueprint (``blueprints/agent-loop``). The blueprint shows the loop in isolation; this is the same
loop with the platform's gate, toolset, and model seam wired in.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Callable

from ..approvals import ApprovalGate, ApprovalRequest, ApprovalResolution
from ..tools.errors import MalformedToolCall, RetryPolicy, repair_tool_call
from ..tools.messages import Message, ToolResult, Transcript, tool as tool_message
from ..tools.model import ModelPort, default_model
from ..tools.schemas import ToolRegistry


class StopReason(str, Enum):
    """Why the loop returned — every terminal path names itself, so a run is never a mystery."""

    COMPLETED = "completed"                      # model produced a final answer (no tool calls)
    MAX_TURNS = "max_turns"                      # hit the turn cap before finishing
    RECOVERY_EXHAUSTED = "recovery_exhausted"    # too many consecutive failing turns
    CANCELLED = "cancelled"                      # the cancel predicate fired
    NEEDS_APPROVAL = "needs_approval"            # a risky call is held for a human (Ch 20)


@dataclass(frozen=True, slots=True)
class AgentResult:
    """The outcome of a run: final text, why it stopped, the full transcript, and any hold.

    ``output`` is the last assistant *text* (empty if the loop stopped before a final answer).
    ``transcript`` is the complete ledger — your trace, your replay input, your eval case.
    ``pending_approval`` is set only when ``stop_reason`` is ``NEEDS_APPROVAL``: it is the request
    the API/UI surfaces to a human, and the thing you resolve to resume (see
    :meth:`AgentLoop.resume_with_approval`).
    """

    output: str
    stop_reason: StopReason
    transcript: Transcript
    turns: int
    run_id: str
    pending_approval: ApprovalRequest | None = None

    @property
    def ok(self) -> bool:
        return self.stop_reason is StopReason.COMPLETED

    @property
    def awaiting_human(self) -> bool:
        return self.stop_reason is StopReason.NEEDS_APPROVAL


# A cancel predicate is checked before each model call; return True to stop the run.
CancelFn = Callable[[Transcript], bool]


@dataclass(slots=True)
class AgentLoop:
    """A configured, reusable agent loop.

    Construct it once with a model port, a tool registry, and the policy knobs; call :meth:`run`
    per task. Nothing about a single run mutates the loop, so one configured ``AgentLoop`` is safe
    to reuse across tasks (each run gets its own transcript and ``run_id``).

    Parameters
    ----------
    model:
        The :class:`~agents.tools.model.ModelPort`. Defaults to the offline mock via
        :func:`~agents.tools.model.default_model`, so an ``AgentLoop()`` with no arguments runs
        free. Inject the platform's ``llm/gateway.py`` client here for the live path.
    tools:
        The :class:`~agents.tools.schemas.ToolRegistry` the model may call. Empty by default.
    max_turns:
        Hard cap on assistant turns — the most important knob. Tune it to the *longest legitimate*
        plan for your task plus a small margin.
    retry_policy:
        Governs consecutive tool-failure tolerance.
    approval_gate:
        Optional :class:`~agents.approvals.ApprovalGate`. When set, every tool call is checked
        before it runs; a held call stops the loop with ``NEEDS_APPROVAL``. ``None`` (the default)
        means no gating — every call runs.
    on_event:
        Optional observer called with ``(name, payload)`` at each step (``"decide"``, ``"gate"``,
        ``"act"``, ``"stop"``). The seam the ``observability/`` stack plugs into; ``None`` by
        default so the loop has zero tracing overhead unless asked.
    """

    model: ModelPort = field(default=None)  # type: ignore[assignment]
    tools: ToolRegistry = field(default_factory=ToolRegistry)
    max_turns: int = 8
    retry_policy: RetryPolicy = field(default_factory=RetryPolicy)
    approval_gate: ApprovalGate | None = None
    on_event: Callable[[str, dict], None] | None = None

    def __post_init__(self) -> None:
        if self.model is None:
            self.model = default_model()
        if self.max_turns < 1:
            raise ValueError("max_turns must be >= 1")

    # -- public API --------------------------------------------------------------------

    def run(
        self,
        task: str,
        *,
        system_prompt: str = "You are a helpful assistant. Use tools when they help.",
        cancel: CancelFn | None = None,
        run_id: str | None = None,
    ) -> AgentResult:
        """Run the loop on one ``task`` and return its :class:`AgentResult`.

        ``task`` seeds the first user turn; ``system_prompt`` is the standing instruction. Pass
        ``cancel`` to stop a run from outside — checked *before* each model call, so a fired
        predicate costs no extra model spend. ``run_id`` ties the run to approval requests and
        traces; one is generated if omitted.
        """
        rid = run_id or f"run_{uuid.uuid4().hex[:12]}"
        transcript = Transcript.start(system_prompt, first_user=task)
        return self._drive(transcript, rid, cancel=cancel)

    def resume(
        self,
        transcript: Transcript,
        *,
        run_id: str,
        cancel: CancelFn | None = None,
    ) -> AgentResult:
        """Continue an existing transcript (e.g. after appending a human reply)."""
        return self._drive(transcript.snapshot(), run_id, cancel=cancel)

    def resume_with_approval(
        self,
        held: AgentResult,
        resolution: ApprovalResolution,
        *,
        cancel: CancelFn | None = None,
    ) -> AgentResult:
        """Resume a run that stopped with ``NEEDS_APPROVAL`` after a human decides.

        Takes the held :class:`AgentResult` and the human's :class:`ApprovalResolution`. On
        approval the gated tool call is executed now and its result appended; on rejection a
        "declined" result is threaded back. Either way the model gets a tool turn and the loop
        continues. Requires a configured ``approval_gate``.
        """
        if self.approval_gate is None:
            raise RuntimeError("resume_with_approval requires an approval_gate")
        if held.stop_reason is not StopReason.NEEDS_APPROVAL or held.pending_approval is None:
            raise ValueError("resume_with_approval expects a result awaiting approval")

        call, denied = self.approval_gate.apply(resolution)
        transcript = held.transcript.snapshot()
        if call is not None:
            result = self.tools.execute(call)
        else:
            result = denied if denied is not None else ToolResult(
                call_id=held.pending_approval.call.id,
                name=held.pending_approval.call.name,
                content="action declined.",
                ok=False,
            )
        transcript.append(tool_message(result))
        return self._drive(transcript, held.run_id, cancel=cancel)

    # -- the core driver ---------------------------------------------------------------

    def _drive(
        self,
        transcript: Transcript,
        run_id: str,
        *,
        cancel: CancelFn | None,
    ) -> AgentResult:
        consecutive_failures = 0

        while True:
            turns = transcript.assistant_turns()

            if cancel is not None and cancel(transcript):
                return self._finish(transcript, StopReason.CANCELLED, turns, run_id)

            if turns >= self.max_turns:
                return self._finish(transcript, StopReason.MAX_TURNS, turns, run_id)

            # --- decide ---------------------------------------------------------------
            self._emit("decide", {"run_id": run_id, "turn": turns + 1})
            response = self.model.complete(list(transcript), self.tools.specs())
            assistant_msg = response.message
            transcript.append(assistant_msg)
            turns = transcript.assistant_turns()

            # --- stop? ----------------------------------------------------------------
            if not assistant_msg.has_tool_calls:
                return self._finish(transcript, StopReason.COMPLETED, turns, run_id)

            # --- gate + act -----------------------------------------------------------
            results, hold = self._gate_and_dispatch(assistant_msg, run_id)
            if hold is not None:
                # Append any results decided *before* the held call, then pause.
                for r in results:
                    transcript.append(tool_message(r))
                self._emit("stop", {"run_id": run_id, "reason": StopReason.NEEDS_APPROVAL.value})
                return AgentResult(
                    output="",
                    stop_reason=StopReason.NEEDS_APPROVAL,
                    transcript=transcript,
                    turns=turns,
                    run_id=run_id,
                    pending_approval=hold,
                )
            self._emit("act", {"run_id": run_id, "turn": turns, "results": len(results)})

            # --- observe --------------------------------------------------------------
            for r in results:
                transcript.append(tool_message(r))

            # --- recovery accounting --------------------------------------------------
            if results and all(not r.ok for r in results):
                consecutive_failures += 1
                if self.retry_policy.exhausted(consecutive_failures):
                    return self._finish(transcript, StopReason.RECOVERY_EXHAUSTED, turns, run_id)
            else:
                consecutive_failures = 0

    # -- internals ---------------------------------------------------------------------

    def _gate_and_dispatch(
        self,
        assistant_msg: Message,
        run_id: str,
    ) -> tuple[list[ToolResult], ApprovalRequest | None]:
        """Repair → gate → execute each call in one turn. Stops at the first held call.

        Returns ``(results_so_far, hold)``. If ``hold`` is non-None, a risky call was held: the
        loop pauses, having already recorded the results of calls *before* it in this turn. Calls
        denied by policy become error results (no human needed) and the turn continues.
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

            if self.approval_gate is not None:
                outcome = self.approval_gate.check(run_id, call)
                self._emit("gate", {"run_id": run_id, "tool": call.name, "decision": outcome.decision.value})
                if outcome.request is not None:
                    return results, outcome.request
                if outcome.denied_result is not None:
                    results.append(outcome.denied_result)
                    continue

            results.append(self.tools.execute(call))
        return results, None

    def _finish(
        self,
        transcript: Transcript,
        reason: StopReason,
        turns: int,
        run_id: str,
    ) -> AgentResult:
        output = self._final_text(transcript) if reason is StopReason.COMPLETED else ""
        self._emit("stop", {"run_id": run_id, "reason": reason.value, "turns": turns})
        return AgentResult(
            output=output,
            stop_reason=reason,
            transcript=transcript,
            turns=turns,
            run_id=run_id,
        )

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
    approval_gate: ApprovalGate | None = None,
    system_prompt: str = "You are a helpful assistant. Use tools when they help.",
    cancel: CancelFn | None = None,
) -> AgentResult:
    """One-call convenience wrapper around :class:`AgentLoop` for scripts and demos.

    Everything defaults to the free, offline path: omit ``model`` for the mock, omit ``tools`` and
    the model simply answers in one turn.
    """
    loop = AgentLoop(
        model=model,  # type: ignore[arg-type]
        tools=tools or ToolRegistry(),
        max_turns=max_turns,
        approval_gate=approval_gate,
    )
    return loop.run(task, system_prompt=system_prompt, cancel=cancel)
