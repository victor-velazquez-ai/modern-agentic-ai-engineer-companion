import { Chat } from "./components/Chat";

/**
 * The chat workspace — a server-component shell hosting the client-side
 * streaming <Chat /> UI. The run timeline, tool-call rendering, and approval
 * cards hang off this page as the frontend grows (Ch 38).
 */
export default function Page() {
  return (
    <main className="mx-auto flex h-screen w-full max-w-2xl flex-col px-4">
      <header className="border-b border-gray-200 py-4">
        <h1 className="text-lg font-semibold">Agentic Platform</h1>
        <p className="text-sm text-gray-500">
          Streaming chat in front of the agent backend. The route handler at{" "}
          <code className="rounded bg-gray-100 px-1">app/api/chat/route.ts</code>{" "}
          proxies the backend SSE run stream.
        </p>
      </header>
      <Chat />
    </main>
  );
}
