/**
 * One chat message bubble. Renders user vs. assistant turns differently. Extend
 * to render tool-call chips, citations, and approval cards as the run stream
 * carries them (Ch 38).
 */

interface MessageLike {
  id: string;
  role: string;
  content: string;
}

export function Message({ message }: { message: MessageLike }) {
  const isUser = message.role === "user";
  return (
    <div className={isUser ? "text-right" : "text-left"}>
      <span
        className={
          "inline-block max-w-[85%] whitespace-pre-wrap rounded-2xl px-4 py-2 text-sm " +
          (isUser ? "bg-gray-900 text-white" : "bg-gray-100 text-gray-900")
        }
      >
        {message.content}
      </span>
    </div>
  );
}
