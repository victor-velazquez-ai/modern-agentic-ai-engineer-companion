# Runbook: SSO Outage

**Domain:** authentication · **Owner:** identity-platform team

## Symptoms
- Users report a redirect loop or a blank page after the identity provider callback.
- Spike in `auth.callback.error` metrics.

## First moves
1. Check the identity provider status page.
2. Confirm the auth domain certificate has not expired.
3. Look for a recent deploy to the `auth-gateway` service.

## Mitigation
- If a stale session cookie is the cause, advise customers to clear cookies for the auth domain.
- If the identity provider is down, enable the read-only maintenance banner.

## Escalation
- Page the identity-platform on-call after 15 minutes of customer impact.
