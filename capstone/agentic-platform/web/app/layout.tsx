import type { Metadata } from "next";
import type { ReactNode } from "react";
import "./globals.css";

/**
 * Root layout — the app shell wrapping every page. Bare on purpose; add your
 * header/nav, fonts, auth provider, and analytics here.
 */
export const metadata: Metadata = {
  title: "Agentic Platform",
  description: "Streaming chat, run timeline, and approvals over the agent backend.",
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en">
      <body className="min-h-screen">{children}</body>
    </html>
  );
}
