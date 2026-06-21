# Runbook: checkout — high error rate / customer-facing 5xx

**Service:** checkout
**Symptom:** elevated error_rate (>5%), customers see failed orders, p99 latency climbs.
**SLO:** error_rate < 1%, p99 < 800ms.

## When this fires
The checkout service returns 5xx on a meaningful fraction of requests. This is almost always
SEV1/SEV2 because it is directly money-losing and customer-facing. Page the on-call immediately
and open an incident channel before deep investigation.

## First signals to pull (read-only)
1. `get_metrics(checkout)` — confirm error_rate, p99_latency_ms, cpu, rps.
2. `search_logs(checkout, "ERROR")` — look for the dominant error class.
3. `list_deploys(checkout)` — note the most recent (current) deploy and its time.

## Most common cause: connection-pool exhaustion
Look for `pool exhausted`, `HikariPool-1 - Connection is not available`, or
`connection pool at 100% utilization` in the logs. The checkout pool is sized at 20; under a
traffic spike or a slow downstream (payments) the pool drains and requests time out waiting for
a connection.

### Remediation (mutating — REQUIRES APPROVAL)
- **Restart the service** (`restart_service checkout`) to clear an exhausted pool. Fastest
  recovery when the pool has wedged; the on-call must approve before it runs.
- If the error onset lines up with the most recent deploy, **roll back**
  (`rollback_deploy checkout --to <previous version>`) instead — a restart will not fix a
  regression that ships a too-small pool or a new blocking call.

## Second cause: a bad deploy
If `list_deploys(checkout)` shows a deploy that landed minutes before the error onset, treat the
deploy as the prime suspect and roll back first; investigate after the bleeding stops.

## Do NOT
- Do not raise the pool size blindly during the incident — that masks the real downstream
  problem and can overwhelm the database.
- Do not let the copilot restart or roll back without a human approving the specific action.
