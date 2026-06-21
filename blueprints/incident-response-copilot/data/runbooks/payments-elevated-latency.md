# Runbook: payments — elevated latency / timeouts

**Service:** payments
**Symptom:** p99 latency rising, upstream callers (checkout) see timeouts.
**SLO:** error_rate < 0.5%, p99 < 400ms.

## When this fires
Payments is a downstream dependency of checkout. When payments slows down, checkout's
connection pool backs up and *checkout* starts erroring even though the root cause is here.
Correlate across both services before deciding where to act.

## First signals to pull (read-only)
1. `get_metrics(payments)` — is error_rate actually up, or only latency?
2. `search_logs(payments, "timeout")` — slow downstream (a card processor) vs. internal slowness.
3. `list_deploys(payments)` — did a recent deploy add a synchronous network call?

## Common causes
- **Slow external processor.** p99 up, error_rate near baseline, logs show `upstream ... timeout`.
  This is usually not fixable from our side; raise with the processor and shed/queue load.
- **A regression that added a blocking call.** Onset correlates with the latest payments deploy.

### Remediation (mutating — REQUIRES APPROVAL)
- If a recent deploy correlates, **roll back** (`rollback_deploy payments --to <previous>`).
- A restart rarely helps latency caused by a slow downstream; prefer load-shedding and comms.

## Do NOT
- Do not restart payments reflexively — if the processor is slow, a restart just drops in-flight
  charges and makes reconciliation harder.
