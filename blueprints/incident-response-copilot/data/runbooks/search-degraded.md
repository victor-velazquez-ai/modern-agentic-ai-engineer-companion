# Runbook: search — degraded / slow queries

**Service:** search
**Symptom:** slow queries, p99 above target, occasional warnings — rarely customer-blocking.
**SLO:** error_rate < 2%, p99 < 500ms.

## When this fires
Search degradation is usually SEV3/SEV4: the experience is worse but orders still flow. Do not
over-rotate. Confirm it is not a symptom of a broader incident (a shared database under load)
before paging widely.

## First signals to pull (read-only)
1. `get_metrics(search)` — error_rate is typically near baseline; latency is the story.
2. `search_logs(search, "slow query")` — index freshness, a hot shard, or a heavy query.
3. `service_health(search)` — confirm it reports `healthy`/`degraded`, not `critical`.

## Common causes
- **Stale or rebuilding index.** Logs mention `index refreshed` / a refresh in progress. Latency
  self-heals as the refresh completes; watch rather than act.
- **A heavy query pattern.** A single expensive query class dominates p99.

### Remediation
- Mostly **non-mutating**: watch the dashboard, let an index refresh finish, rate-limit a heavy
  caller. Escalate to a mutating action only if degradation crosses the SLO for a sustained
  window — and then only with approval.

## Do NOT
- Do not roll back on a slow-query warning alone; search degradation is rarely deploy-caused.
