"use client";

import { useChat } from "@ai-sdk/react";
import { Message } from "./Message";

/**
 * The streaming chat surface.
 *
 * `useChat()` (Vercel AI SDK) runs the whole streaming loop: it POSTs the
 * message history to /api/chat, reads the streamed response, and re-renders as
 * tokens arrive. No SSE/fetch/stream-parsing code lives here — the route
 * handler and lib/ own that. This is yours to design (run timeline, approval
 * cards, message actions).
 */
export function Chat() {
  const { messages, input, handleInputChange, handleSubmit, status, error } =
    useChat({ api: "/api/chat" });

  const isStreaming = status === "submitted" || status === "streaming";

  return (
    <div className="flex flex-1 flex-col overflow-hidden">
      <div className="flex-1 space-y-4 overflow-y-auto py-4">
        {messages.length === 0 ? (
          <p className="mt-8 text-center text-sm text-gray-400">
            Ask the agent anything to start a run.
          </p>
        ) : (
          messages.map((message) => (
            <Message key={message.id} message={message} />
          ))
        )}

        {error ? (
          <p className="rounded-md bg-red-50 px-3 py-2 text-sm text-red-700">
            Something went wrong. Check the server logs and your backend config.
          </p>
        ) : null}
      </div>

      <form onSubmit={handleSubmit} className="border-t border-gray-200 py-4">
        <div className="flex items-center gap-2">
          <input
            className="flex-1 rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-gray-500 focus:outline-none"
            value={input}
            onChange={handleInputChange}
            placeholder="Type a message…"
            disabled={isStreaming}
          />
          <button
            type="submit"
            className="rounded-md bg-gray-900 px-4 py-2 text-sm font-medium text-white disabled:opacity-50"
            disabled={isStreaming || input.trim().length === 0}
          >
            {isStreaming ? "…" : "Send"}
          </button>
        </div>
      </form>
    </div>
  );
}
