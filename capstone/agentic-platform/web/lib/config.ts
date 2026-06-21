/**
 * Server-side configuration helpers.
 *
 * Imported ONLY by server code (route handlers, lib/auth, lib/api), so the
 * secrets it reads never reach the client bundle. Do not import from a "use
 * client" component. No business logic — just typed access to env config.
 */

/** Base URL of the platform API (no trailing slash). */
export function getApiUrl(): string {
  const url = process.env.AGENT_API_URL ?? "http://localhost:8000";
  return url.replace(/\/+$/, "");
}

/** Optional bearer token sent to the API, if it requires auth. */
export function getApiToken(): string | undefined {
  return process.env.AGENT_API_TOKEN || undefined;
}

/** JWT signing secret for the web app's own sessions. */
export function getAuthSecret(): string | undefined {
  return process.env.AUTH_SECRET || undefined;
}

/** Repo-wide offline switch — when set, the UI streams a canned reply. */
export function isMock(): boolean {
  return (process.env.COMPANION_MOCK ?? "1").trim().toLowerCase() === "1";
}
