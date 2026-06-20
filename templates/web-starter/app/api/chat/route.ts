/**
 * Chat route handler — the one place secrets live and the backend is wired.
 *
 * POST /api/chat
 *   Body: { messages: UIMessage[] }  (sent by the useChat() hook in Chat.tsx)
 *   Returns: a streaming response the AI SDK renders token-by-token.
 *
 * Three backends, selected by the CHAT_BACKEND env var (see .env.local.example):
 *   - "mock"      → keyless echo path; streams a canned reply. The default, so the
 *                   UI runs with no configuration.
 *   - "anthropic" → calls the Anthropic API directly via the AI SDK provider.
 *   - "agent"     → proxies your own backend's SSE stream (e.g. the
 *                   fastapi-agent-service /v1/runs contract).
 *
 * ▢ TODO: pick your backend in .env.local and fill in the matching section below.
 * No agent logic lives here — this file is transport only.
 */

import { anthropic } from "@ai-sdk/anthropic";
import { streamText, type UIMessage } from "ai";
import {
  getAgentApiToken,
  getAgentApiUrl,
  getAnthropicModel,
  getBackend,
} from "@/app/lib/api";

// Edge-ready: streaming responses work on the Edge runtime. Switch to "nodejs"
// if your backend client needs Node APIs (e.g. some SDKs, fs, etc.).
export const runtime = "edge";

// Allow streamed responses up to 30s (raise on platforms that permit it).
export const maxDuration = 30;

export async function POST(req: Request): Promise<Response> {
  const { messages }: { messages: UIMessage[] } = await req.json();
  const backend = getBackend();

  switch (backend) {
    case "anthropic":
      return handleAnthropic(messages);
    case "agent":
      return handleAgent(messages);
    default:
      return handleMock(messages);
  }
}

/**
 * "anthropic" — call the model directly from the server.
 *
 * The provider reads ANTHROPIC_API_KEY from the environment automatically; it is
 * never exposed to the client. The AI SDK turns the model stream into the wire
 * format useChat() expects.
 *
 * ▢ TODO: this is a plain model call, NOT an agent. Replace the system prompt,
 * add tools, retrieval, or a real agent loop as your application needs.
 */
function handleAnthropic(messages: UIMessage[]): Response {
  const result = streamText({
    model: anthropic(getAnthropicModel()),
    system: "You are a helpful assistant.", // TODO: your system prompt
    messages,
  });
  return result.toDataStreamResponse();
}

/**
 * "agent" — proxy an upstream agent service that streams Server-Sent Events.
 *
 * This bridges the fastapi-agent-service contract (see ../fastapi-agent-service):
 *   GET ${AGENT_API_URL}/v1/runs/{id}/stream?input=...
 *   → SSE frames whose `data` is a JSON RunEvent: { type, token, data }
 *
 * We forward the latest user message as `input`, then translate each RunEvent
 * `token` into the AI SDK data-stream format so useChat() renders it live.
 *
 * ▢ TODO: if your backend uses a different contract (POST a run, then stream by
 * id; a message list instead of a single `input`; auth headers; etc.), adjust
 * the request and the frame parsing below.
 */
function handleAgent(messages: UIMessage[]): Response {
  const lastUser = [...messages].reverse().find((m) => m.role === "user");
  const input = lastUser?.content ?? "";

  const runId = crypto.randomUUID();
  const url = `${getAgentApiUrl()}/v1/runs/${runId}/stream?input=${encodeURIComponent(input)}`;

  const headers: Record<string, string> = { Accept: "text/event-stream" };
  const token = getAgentApiToken();
  if (token) headers.Authorization = `Bearer ${token}`;

  const encoder = new TextEncoder();

  const stream = new ReadableStream<Uint8Array>({
    async start(controller) {
      // AI SDK data-stream "text" parts are framed as: 0:"<json-string>"\n
      const writeText = (text: string) => {
        controller.enqueue(encoder.encode(`0:${JSON.stringify(text)}\n`));
      };

      try {
        const upstream = await fetch(url, { headers });
        if (!upstream.ok || !upstream.body) {
          writeText(`\n[agent backend error: HTTP ${upstream.status}]`);
          controller.close();
          return;
        }

        const reader = upstream.body.getReader();
        const decoder = new TextDecoder();
        let buffer = "";

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
              const event = JSON.parse(payload) as {
                type?: string;
                token?: string | null;
              };
              if (event.type === "token" && event.token) {
                writeText(event.token);
              }
              // "start"/"end"/"error" lifecycle events are ignored here.
              // TODO: surface errors to the user if you want.
            } catch {
              // Ignore non-JSON keep-alive frames.
            }
          }
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

/**
 * "mock" — keyless echo path so the UI streams with zero configuration.
 *
 * Streams a canned reply word-by-word in the AI SDK data-stream format. Useful
 * for building/styling the frontend before any backend exists. No key required.
 */
function handleMock(messages: UIMessage[]): Response {
  const lastUser = [...messages].reverse().find((m) => m.role === "user");
  const reply =
    `You said: "${lastUser?.content ?? ""}". ` +
    "This is the mock backend — set CHAT_BACKEND in .env.local to wire a real one.";
  const words = reply.split(" ");

  const encoder = new TextEncoder();
  const stream = new ReadableStream<Uint8Array>({
    async start(controller) {
      for (const word of words) {
        controller.enqueue(encoder.encode(`0:${JSON.stringify(`${word} `)}\n`));
        await new Promise((r) => setTimeout(r, 40)); // simulate token latency
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
