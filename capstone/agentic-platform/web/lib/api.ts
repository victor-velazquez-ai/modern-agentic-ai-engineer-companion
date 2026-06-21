/**
 * API client — typed access to the platform backend (app/).
 *
 * Thin wrappers around the FastAPI run/chat/document routes. The chat route
 * handler uses `streamRun` to open a run's SSE stream; other surfaces (run
 * timeline, document upload) call the JSON helpers. Server-only — it forwards
 * the request's bearer token and never runs in the browser.
 */

import { getApiUrl } from "./config";
import { backendAuthHeaders, type Session } from "./auth";
import { parseSSE, type RunEvent } from "./sse";

/** Start a run and stream its events from the backend.
 *
 * Mirrors the backend contract `GET {API}/v1/runs/{id}/stream?input=...` → SSE
 * `RunEvent` frames. Yields each parsed event for the caller to render.
 */
export async function* streamRun(
  input: string,
  session: Session | null,
  runId: string = crypto.randomUUID(),
): AsyncGenerator<RunEvent> {
  const url = `${getApiUrl()}/v1/runs/${runId}/stream?input=${encodeURIComponent(input)}`;
  const res = await fetch(url, {
    headers: { Accept: "text/event-stream", ...backendAuthHeaders(session) },
  });
  if (!res.ok || !res.body) {
    yield { type: "error", data: { status: res.status } };
    return;
  }
  yield* parseSSE(res.body);
}

/** Fetch a run's current state (for the run timeline view). */
export async function getRun(
  runId: string,
  session: Session | null,
): Promise<unknown> {
  const res = await fetch(`${getApiUrl()}/v1/runs/${runId}`, {
    headers: { Accept: "application/json", ...backendAuthHeaders(session) },
  });
  if (!res.ok) throw new Error(`getRun failed: HTTP ${res.status}`);
  return res.json();
}

/** Approve or reject a gated tool call (the approval-card action, Ch 20). */
export async function decideApproval(
  runId: string,
  approvalId: string,
  decision: "approve" | "reject",
  session: Session | null,
): Promise<void> {
  const res = await fetch(
    `${getApiUrl()}/v1/runs/${runId}/approvals/${approvalId}`,
    {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        ...backendAuthHeaders(session),
      },
      body: JSON.stringify({ decision }),
    },
  );
  if (!res.ok) throw new Error(`decideApproval failed: HTTP ${res.status}`);
}
