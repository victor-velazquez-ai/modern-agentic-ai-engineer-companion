# `agents/raw/` — the framework-free agent loop

The engine the whole platform grows around (Ch 12), with the human-in-the-loop approval gate wired
in (Ch 20). No orchestration library hides the control flow — you can read the entire
`observe → decide → gate → act → observe` cycle in `loop.py`.

## The cycle

1. **decide** — ask the model (`ModelPort`) for the next assistant turn given the transcript + tools;
2. **stop?** — no tool calls ⇒ the model is done talking; return its text (`StopReason.COMPLETED`);
3. **gate** — run each requested call through the `ApprovalGate` (if configured): allow / hold / deny;
4. **act** — dispatch the approved calls, repairing malformed ones, isolating failures;
5. **observe** — append the tool results and loop.

## What a shipped loop adds over a toy one

- **A turn cap** (`max_turns`) — the single most important safety bound; a confused model can't loop forever.
- **Tool-error recovery** — a failed call becomes a result the model reads and retries, bounded by `RetryPolicy`.
- **Malformed-call repair** — broken JSON arguments are fixed where safe, reported where not.
- **Cancellation** — a caller predicate checked before each model call (a deadline, a user "stop").
- **Approval gate (Ch 20)** — a risky call pauses the run with `StopReason.NEEDS_APPROVAL`; the
  transcript snapshot makes the hold resumable. `resume_with_approval(...)` continues it once a
  human decides.

## Surface

```python
from agents.raw import AgentLoop, run_agent, StopReason
```

- `AgentLoop(model=..., tools=..., max_turns=..., approval_gate=..., on_event=...)` — configure once, `run()` per task.
- `loop.run(task)` → `AgentResult` (`.output`, `.stop_reason`, `.transcript`, `.run_id`, `.pending_approval`).
- `loop.resume(transcript, run_id=...)` — continue an existing transcript (e.g. after a human reply).
- `loop.resume_with_approval(held, resolution)` — resume a run that stopped for approval.
- `run_agent(task, ...)` — one-call convenience for scripts/demos; everything defaults to the offline mock.

The `on_event` callback (`"decide"` / `"gate"` / `"act"` / `"stop"`) is the seam the
`observability/` stack plugs into; it's `None` by default so the loop has zero tracing overhead
until you ask for it.

## Relationship to the other variants

`graph/` and `pydantic_ai/` express *this same agent* in their frameworks (Ch 18); the supervisor
delegates to *this* loop per worker (Ch 17). This is the integrated counterpart of the
[`agent-loop`](../../../../blueprints/agent-loop/) blueprint — same loop, with the platform's gate,
toolset, and model seam wired in.
