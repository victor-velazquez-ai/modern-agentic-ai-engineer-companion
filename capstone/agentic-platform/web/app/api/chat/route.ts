/**
 * Chat route handler — the one place auth lives and the backend is wired.
 *
 * POST /api/chat
 *   Body: { messages: UIMessage[] }  (sent by the useChat() hook in Chat.tsx)
 *   Returns: a streaming response the AI SDK renders token-by-token.
 *
 * Two paths, selected by COMPANION_MOCK (see lib/config):
 *   - mock  → keyless echo; streams a canned reply so the UI runs with zero
 *             configuration (the repo-wide offline default).
 *   - live  → proxies the platform backend's run SSE stream via lib/api +
 *             lib/sse, forwarding the request's bearer token (lib/auth).
 *
 * No agent logic lives here — this file is transport only. The agent runs in the
 * backend (app/ + agents/); the frontend just renders its stream.
 */

import { streamRun } from "@/lib/api";
import { getSession } from "@/lib/auth";
import { isMock } from "@/lib/config";

// Node runtime: the lib/ helpers read env + fetch the backend over SSE.
export const runtime = "nodejs";
export const maxDuration = 60;

interface UIMessage {
  role: string;
  content: string;
}

export async function POST(req: Request): Promise<Response> {
  const { messages } = (await req.json()) as { messages: UIMessage[] };
  const lastUser = [...messages].reverse().find((m) => m.role === "user");
  const input = lastUser?.content ?? "";

  if (isMock()) return mockReply(input);

  const session = await getSession(req);
  const encoder = new TextEncoder();

  const stream = new ReadableStream<Uint8Array>({
    async start(controller) {
      // AI SDK data-stream "text" parts are framed as: 0:"<json-string>"\n
      const writeText = (text: string) =>
        controller.enqueue(encoder.encode(`0:${JSON.stringify(text)}\n`));
      try {
        for await (const event of streamRun(input, session)) {
          if (event.type === "token" && event.token) writeText(event.token);
          else if (event.type === "error")
            writeText("\n[agent backend error]");
          // "start"/"tool_use"/"approval"/"end" frames are ignored here;
          // the run-timeline view consumes them via lib/api.getRun().
        }
      } catch (err) {
        writeText(`\n[failed to reach agent backend: ${String(err)}]`);
      } finally {
        controller.close();
      }
    },
  });

  return new Response(stream, {
    headers: {
      "Content-Type": "text/plain; charset=utf-8",
      "x-vercel-ai-data-stream": "v1",
    },
  });
}

/** Keyless echo path so the UI streams with zero configuration. */
function mockReply(input: string): Response {
  const reply =
    `You said: "${input}". ` +
    "This is the mock backend — unset COMPANION_MOCK and set AGENT_API_URL to " +
    "stream from the real platform API.";
  const words = reply.split(" ");
  const encoder = new TextEncoder();

  const stream = new ReadableStream<Uint8Array>({
    async start(controller) {
      for (const word of words) {
        controller.enqueue(encoder.encode(`0:${JSON.stringify(`${word} `)}\n`));
        await new Promise((r) => setTimeout(r, 30));
      }
      controller.close();
    },
  });

  return new Response(stream, {
    headers: {
      "Content-Type": "text/plain; charset=utf-8",
      "x-vercel-ai-data-stream": "v1",
    },
  });
}
