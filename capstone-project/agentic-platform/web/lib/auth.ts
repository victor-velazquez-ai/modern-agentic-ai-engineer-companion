/**
 * Auth helpers (stub).
 *
 * The capstone's web app authenticates users with a JWT signed by AUTH_SECRET
 * and forwards a bearer token to the FastAPI backend (which enforces authn/z,
 * rate limits, and multi-tenancy — Ch 26). This stub gives the route handlers a
 * single place to resolve the current request's token; replace the body with
 * your real session/JWT verification (next-auth, Clerk, a custom cookie, ...).
 *
 * Server-only — never import from a "use client" component.
 */

import { getApiToken } from "./config";

/** The authenticated principal for a request (expand as your IdP requires). */
export interface Session {
  userId: string;
  tenantId: string;
  token: string;
}

/**
 * Resolve the session for an incoming request.
 *
 * TODO: verify the request's auth cookie / Authorization header and decode the
 * JWT with AUTH_SECRET. For now this returns a dev session carrying the static
 * AGENT_API_TOKEN so the streaming path is wired end-to-end without an IdP.
 */
export async function getSession(req: Request): Promise<Session | null> {
  const header = req.headers.get("authorization");
  const bearer = header?.toLowerCase().startsWith("bearer ")
    ? header.slice(7).trim()
    : undefined;

  const token = bearer ?? getApiToken();
  if (!token) {
    // No auth configured (local dev): allow an anonymous dev session.
    return { userId: "dev-user", tenantId: "dev-tenant", token: "" };
  }
  return { userId: "dev-user", tenantId: "dev-tenant", token };
}

/** Build the headers to forward to the platform API for an authed request. */
export function backendAuthHeaders(session: Session | null): Record<string, string> {
  const headers: Record<string, string> = {};
  if (session?.token) headers.Authorization = `Bearer ${session.token}`;
  return headers;
}
