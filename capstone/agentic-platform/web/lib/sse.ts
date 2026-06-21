/**
 * SSE handling — parse the platform API's run event stream.
 *
 * The backend (app/) streams a run as Server-Sent Events: each frame's `data`
 * is a JSON `RunEvent`. This module turns a raw SSE `ReadableStream` into an
 * async iterator of typed events, so the route handler can translate `token`
 * events into the AI SDK's data-stream wire format and ignore lifecycle frames.
 *
 * Keeping the frame parsing here (not in the route) is the seam Appendix C calls
 * out: lib/ owns API-client + auth + SSE handling; the route is transport glue.
 */

/** One event from the backend's run stream. */
export interface RunEvent {
  /** "start" | "token" | "tool_use" | "tool_result" | "approval" | "end" | "error" */
  type: string;
  /** Present on "token" events: the next chunk of assistant text. */
  token?: string | null;
  /** Arbitrary structured payload (tool calls, citations, approval cards, ...). */
  data?: unknown;
}

/**
 * Parse an SSE byte stream into `RunEvent`s.
 *
 * Yields each event whose `data:` line is valid JSON; silently skips keep-alive
 * comments and non-JSON frames (heartbeats). Honors back-pressure — it reads one
 * chunk at a time and buffers partial frames across reads.
 */
export async function* parseSSE(
  body: ReadableStream<Uint8Array>,
): AsyncGenerator<RunEvent> {
  const reader = body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  try {
    for (;;) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });

      // SSE frames are separated by a blank line.
      const frames = buffer.split("\n\n");
      buffer = frames.pop() ?? "";

      for (const frame of frames) {
        const dataLine = frame
          .split("\n")
          .find((line) => line.startsWith("data:"));
        if (!dataLine) continue;
        const payload = dataLine.slice(5).trim();
        if (!payload) continue;
        try {
          yield JSON.parse(payload) as RunEvent;
        } catch {
          // Ignore non-JSON keep-alive frames.
        }
      }
    }
  } finally {
    reader.releaseLock();
  }
}
