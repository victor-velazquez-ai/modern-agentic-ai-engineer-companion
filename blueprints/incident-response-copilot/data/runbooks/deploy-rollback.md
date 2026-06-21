# Runbook: deploy correlation & rollback (any service)

**Applies to:** any service where an incident's onset lines up with a recent deploy.
**Symptom:** errors or latency began within minutes of a deploy landing.

## The deploy-correlation rule
The single highest-signal question in triage: **did anything change?** Pull `list_deploys(<svc>)`
and compare the *current* deploy's timestamp to the error onset. If the onset is within ~15
minutes of a deploy, the deploy is the prime suspect — regardless of how the failure looks.

## Decide: roll back vs. restart
- **Roll back** when a recent deploy correlates with the onset. A restart cannot fix a code
  regression; it just delays the inevitable. Roll to the immediately previous known-good version.
- **Restart** when there is no correlated deploy and the failure looks like exhausted/wedged
  state (a drained connection pool, a stuck worker).

### Remediation (mutating — REQUIRES APPROVAL)
- `rollback_deploy <service> --to <previous version>` — gated; the on-call approves the exact
  service + target version.
- `restart_service <service>` — gated; approve only when state-clearing is the right move.

## After the action
- Verify recovery with `get_metrics` / `service_health` before declaring mitigation.
- Record the action, the approver, and the outcome — the audit ledger does this automatically,
  and the postmortem reads from it.

## Do NOT
- Do not roll forward with a hotfix mid-incident unless rollback is impossible; rollback is the
  faster, more reversible mitigation.
