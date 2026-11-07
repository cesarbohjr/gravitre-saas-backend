# PR #605 — Gate 26 holistic audit continuation

Date: 2026-11-05. Status: **audit in progress, no release/retirement certification**.

## Scope and governing records
This is additive to `gravitre-unified-ecosystem-modernization-plan.md`, `pr605-production-audit-gap-register.md`, `pr605-canonical-ownership-retirement-register.md`, and the Gate 25 relay acceptance report. Continue workstreams A–F across chat/voice, orchestration, context/memory, model policy, agents/plays/workflows, connectors, Postgres/outbox/Redis/Temporal, infrastructure, security and performance. Do not reduce the holistic audit to CI triage.

## New verified source-access finding
The repository branch `feat/gravitre-unified-ecosystem-modernization` exists and is readable through the GitHub connector. The production audit register names this branch as the audit branch. `.github/workflows/ci.yml` and the audit register were fetched from that branch. This verifies a target for controlled commits, but is not by itself an independent PR-head metadata check; verify the resulting commit is attached to PR #605 before certifying it.

## CI finding and disposition
At previously inspected commit `b5c4e646fc59f56f1d0fa6a66ffb5552f23eceaf`, integrated CI run 42136243980 failed in backend `Verify bounded media decoder` with exit code 124 during slow FFmpeg apt provisioning. The decoder's functional assertions were not demonstrated to fail. Backend PostgreSQL and pytest checks skipped after the setup failure. **Action:** inspect step-level timeout and provisioning source, separate dependency installation from decoder assertions while preserving security tests, commit bounded fix, rerun exact-head CI, record all mandatory pass/fail/skipped outcomes. No full CI pass is claimed.

## Holistic audit evidence backlog (required before freeze)
1. Ingress-to-decision-owner graph: enumerate deployed HTTP/WS/SSE and frontend entrypoints, feature flags, LIVE/classical delegation and actual callers. Mark source observation versus runtime confirmation.
2. Text/voice path: correlate authenticated session, STT interim/final transcript, turn state, model/tool execution, TTS audio and client playback; reproduce duplicate/echo/barge-in failures with synthetic fixtures and authorized traces.
3. Execution fabric: agents, plays, packages, workflows, connector availability, approvals, cancellation, retries, idempotency and canonical verified outcomes. Preserve tenant and write-fence invariants.
4. State/consumer ownership: map `workflow_runs`, `runs/run_steps`, outbox, event relay, audit tables, Redis and Temporal producers/readers; do not infer that dual writes are redundant.
5. Hosting and economics: verify production DNS/traffic ownership, Railway/Vercel deployments, provider routes, latency and spend with evidence. Never log secret values.
6. For each candidate in the retirement register, attach exact owner/callers, observed usage, replacement parity, regression tests, migration order, rollback and independent approval. Until then KEEP or INVESTIGATE, not delete.

## Controlled next steps
A. Verify this branch's latest commit appears as PR #605 head; no changes to main.
B. Repair the CI setup timeout without weakening decoder tests, and certify all mandatory jobs on the resulting exact SHA.
C. Expand production-grounded route/consumer inventory and update the existing ECO/DEC registers with individual findings and confidence levels.
D. Obtain named Security/Privacy and Operations signoffs in issue #607 before any deployed telemetry acceptance with synthetic data; demonstrate durable consumer effects, isolation and kill switch.
E. Keep historical reconciliation separately approval-gated. No merge, deployment, telemetry activation or legacy retirement authorized by this audit note.

## Evidence classification
**Verified:** branch exists and files are readable; previously inspected CI failed with exit 124; prior synthetic relay suite passed isolated checks. **Not verified:** current PR-head association after this commit, passing integrated CI, deployed end-to-end runtime trace, production privacy approval, holistic completeness, retirement eligibility.
