import type { Metadata } from "next";
import type { ReactNode } from "react";
import "./globals.css";

/**
 * Root layout — the app shell. Wraps every page.
 *
 * TODO: set your real product name/description, add fonts, analytics, providers,
 * a header/nav, etc. This is intentionally bare so you start from a clean shell.
 */
export const metadata: Metadata = {
  title: "Agent Chat", // TODO: your product name
  description: "Streaming chat UI in front of an agent backend.", // TODO
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en">
      <body className="min-h-screen">{children}</body>
    </html>
  );
}
