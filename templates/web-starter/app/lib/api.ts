/**
 * Server-side backend configuration helpers.
 *
 * This module is imported ONLY by the route handler (app/api/chat/route.ts), so
 * the secrets it reads (`ANTHROPIC_API_KEY`, `AGENT_API_TOKEN`) never reach the
 * client bundle. Do not import it from a client component ("use client").
 *
 * There is no business logic here — just typed access to environment config and
 * the constants the route handler needs.
 */

export type ChatBackend = "mock" | "anthropic" | "agent";

/** Which backend the chat route should use. Defaults to the keyless mock path. */
export function getBackend(): ChatBackend {
  const value = (process.env.CHAT_BACKEND ?? "mock").toLowerCase();
  if (value === "anthropic" || value === "agent" || value === "mock") {
    return value;
  }
  // Unknown value → fail safe to mock so the UI still runs.
  return "mock";
}

/** Default model id: the latest, most capable Claude model. */
export const DEFAULT_MODEL = "claude-opus-4-8";

/** Resolved model id for the Anthropic backend. */
export function getAnthropicModel(): string {
  return process.env.ANTHROPIC_MODEL ?? DEFAULT_MODEL;
}

/** Base URL of the agent backend (no trailing slash), for the "agent" backend. */
export function getAgentApiUrl(): string {
  const url = process.env.AGENT_API_URL ?? "http://localhost:8000";
  return url.replace(/\/+$/, "");
}

/** Optional bearer token sent to the agent backend, if it requires auth. */
export function getAgentApiToken(): string | undefined {
  return process.env.AGENT_API_TOKEN || undefined;
}
