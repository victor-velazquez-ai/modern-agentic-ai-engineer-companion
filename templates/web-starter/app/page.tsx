import { Chat } from "./components/Chat";

/**
 * The chat page. Server component shell hosting the client-side <Chat /> UI.
 *
 * TODO: add your surrounding page — header, sidebar, auth gate, etc. The starter
 * keeps it to a centered chat column so the streaming surface is the whole story.
 */
export default function Page() {
  return (
    <main className="mx-auto flex h-screen w-full max-w-2xl flex-col px-4">
      <header className="border-b border-gray-200 py-4">
        <h1 className="text-lg font-semibold">Agent Chat</h1>
        <p className="text-sm text-gray-500">
          {/* TODO: replace with your product tagline */}
          Streaming chat in front of your agent. Edit{" "}
          <code className="rounded bg-gray-100 px-1">app/api/chat/route.ts</code> to wire a
          backend.
        </p>
      </header>
      <Chat />
    </main>
  );
}
