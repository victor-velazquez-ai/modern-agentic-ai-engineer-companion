# Production Incident Runbook

When a production incident is detected, the on-call engineer is the incident commander until
formally handed off. The first job is to assess severity. A SEV1 is a full outage or data-loss
risk; a SEV2 is major degradation; a SEV3 is a minor, contained issue.

For a SEV1 or SEV2, open an incident channel, post the current status, and page the secondary
on-call. Communicate impact in plain language every 30 minutes even if there is no change.
Mitigate first and find root cause later: roll back the most recent deploy if it correlates with
the start of the incident.

Once mitigated, declare the incident resolved in the channel and schedule a blameless postmortem
within five business days. The postmortem documents the timeline, the contributing factors, and
the action items, and is shared with engineering.

Never make a risky change to production alone during an incident. Pair with the secondary on-call
and get a second set of eyes before any irreversible action.
