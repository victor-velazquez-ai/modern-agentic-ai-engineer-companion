# Engineering Handbook

Engineering works in two-week iterations. Every change ships behind code review: at least one
approval from a code owner is required to merge, and CI must be green. We favor small, frequent
pull requests over large ones because they are easier to review and safer to roll back.

All code lands on the main branch through pull requests; direct pushes to main are disabled.
Write tests for new behavior and keep the build under ten minutes. Feature flags gate anything
risky so we can disable it without a deploy.

Production access follows least privilege. You request access through the access portal with a
business justification, and it is granted for a fixed window. Anyone with production access must
use a hardware security key.

On-call rotates weekly. Before your rotation, read the incident runbook and confirm your pager
is working. Document anything you learn during an incident in the team runbook so the next person
benefits.
