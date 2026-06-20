"use client";

import type { UIMessage } from "ai";
import ReactMarkdown from "react-markdown";

/**
 * One chat bubble. Renders assistant content as Markdown (so streamed code
 * blocks, lists, and emphasis look right) and user content as plain text.
 *
 * TODO: customize avatars, timestamps, copy buttons, syntax highlighting, and
 * how tool calls / non-text parts are displayed.
 */
export function Message({ message }: { message: UIMessage }) {
  const isUser = message.role === "user";

  return (
    <div className={`flex ${isUser ? "justify-end" : "justify-start"}`}>
      <div
        className={`max-w-[85%] rounded-2xl px-4 py-2 text-sm ${
          isUser ? "bg-gray-900 text-white" : "bg-white text-gray-900 shadow-sm ring-1 ring-gray-200"
        }`}
      >
        {isUser ? (
          <span className="whitespace-pre-wrap">{message.content}</span>
        ) : (
          <div className="prose prose-sm max-w-none break-words">
            <ReactMarkdown>{message.content}</ReactMarkdown>
          </div>
        )}
      </div>
    </div>
  );
}
