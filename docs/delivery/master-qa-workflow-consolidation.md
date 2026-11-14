# Master QA consolidation — canonical register, branches and workflow ownership

Date: 2026-11-14. **Engineering scope only. No automatic production deployments, real-provider writes, or release-approval claims.**

## Authoritative scope and completion snapshot

- `docs/delivery/master-qa-remediation-register.v2.json` is the sole 43-finding source of truth; do not replace it with per-PR progress lists. 43 historical IDs preserved: **ECO-001 administrative consolidation** into ECO-002; **42 separately tracked active** findings; **0** `fix_verified=true`; **29** currently `release_blocking=true`. ECO-001 was administratively consolidated, *not technically fixed or retired*.
- `docs/delivery/master-qa-00-90-release-manifest.json` is the seven-lane release contract. QA00/QA10/QA20/QA40 are PARTIAL, QA30/QA50/QA90 are BLOCKED at audit time. `release_authorized=false`.
- Do not assert that a source-level fixture, partial CI, standalone targeted PR, or healthy HTTP response establishes production-grade acceptance or owner signoff.
- Release gates: source/caller trace; canonical owner; positive and negative tests; independent downstream provider/ledger observations; exact-head CI; deployed SHA where required; verified rollback; owner approval. Keep PROD unchanged without explicit separate authorization.

## Open PR inventory reviewed (11)

| PR | Domain | Decision; not an assertion of completed merge |
|---|---|---|
| #611 | Master register and ecosystem QA remediation | **Canonical integration/release branch**; production merge remains blocked |
| #615 (stacked onto #611) | ECO-002 instrumented router and regression/reports | Candidate for **selective evidence import**, not blind merge: adds `router_stage_timing.py` and three ECO-specific workflows while #611 already uses `routing_stage_metrics.py`. Reconcile histogram definitions and instrumentation once; preserve tests, measured evidence and governor ownership. At review, head had 5/5 own workflows successful, **not master full-CI certification** |
| #616 (stacked onto #611) | ECO-003 context latency and tenant contracts | Candidate for **selective import**: adds one ECO-specific workflow and a context-assembler patch that overlaps #611's `context_stage_metrics.py`. Preserve report/tests while preventing double timing or changed tenant/error behavior. At review, 3/3 own workflows successful, **not master full-CI certification** |
| #610 | Voice 3.0 / ECO-004 | Voice implementation **stays owned here**; PR #611 may consume only exact-head certified V0–V7 and negative/device outcomes. Never silently copy an uncertified voice owner into router code |
| #612 | QA00/QA10 authenticated proxy and SQL recovery | Controlled isolated prerequisite; review/migrate separately with migration rollback |
| #604 | Nango catalog connector coverage | Distinct connector integration; owner review and live OAuth grants required |
| #603 | About/Careers visual design | UI-only, not an ECO closure proof |
| #600 | Conversational quality and voice parity | Overlaps PR #610 and master QA; reconcile per behavior/test, not blind merge |
| #596 | Agency Agents suite | Marketplace-specific deliverables and evidence |
| #588 | Source scheduler and Slack retries | Operations/connector owner review and regression |
| #580 | Seven-intelligence provider/consumer tests | Review and import executable fixtures, not unsupported PASS |

All 11 PRs remain unmerged at this review; no branch deletion is authorized by this document. The first branch API page returned 100 branch refs; more may exist. Do not delete remote branch refs until they have **no unique commits, no open PR, no protected or deployment usage**, and their final integration is certified.

## Workflow consolidation policy

At audit, PR #611 had **95** workflow YAML files. These are *not* all test workflows: some are scheduled operations, production deploys, provider-live gates, manual safety preflights and unique acceptance batteries. Global deletion would introduce regressions.

**One canonical master evidence gate:**
- `.github/workflows/master-qa-p0-synthetic.yml`, display name **Master QA | QA00–QA90 Core Evidence & Runtime**. Runs on relevant master-plan source/manifest changes and by manual dispatch, retains existing offline synthetic guard + disposable PostgreSQL exercises, runs ECO-002/003 routing/tenant contracts explicitly, compiles release manifest, register and source-wiring artifacts. This gate is **not a substitute for full CI or for live proof**.
- `.github/workflows/ci.yml` remains the single broad build/typecheck/pytest/security/regression pipeline. Preserve the existing job names until branch protection and required-status-check policy are independently read and updated.
- Maintain specialist source-change lanes for database migrations, governed actions/outbox, connector governance, voice confirmation/duplex/offline, billing and department/evaluation suites until a replacement is **demonstrably equivalent** on exact source SHA. Only after that retire duplicate automatic pull_request triggers.
- `.github/workflows/eco-001-deployed-ingress.yml` remains a protected, **manual and read-only** ECO-002-inherited runtime preflight; keep historical file path for inbound references. QA50 provider reads/writes and production/paid/staging workflows must *never* automatically run for ordinary PRs.
- `.github/workflows/master-qa-p27-sandbox-readback.yml` retains explicit human and environment authorization. Do not combine it with untrusted PR auto workflows.
- Preserve schedules that actually monitor live operations, release or compliance; these require separate owner review and are not obsolete merely because their filenames predate the master QA register.

### Retire only proven obsolete automation

- `.github/workflows/pr587-controlled-reconcile.yml`: branch-specific **automated merge/reconciliation** workflow for `feat/phase2-dialogue-intelligence`, not a test; hardcoded conflict choices, `contents: write`, no matching open PR in the 11-PR inventory. **Retire from PR #611**; keep Git history as an audit/recovery reference.
- Other `pr587-*` and `issue-535-*` paths still provide specialized replay/acoustic checks. Do not delete them without test-equivalent migration and any required-check readback. Remove misleading names only when preserving job/status identities or obtaining branch-rule owner approval.

## Before closing/repointing PR #615/#616

1. Review unique diff and compare against current #611 at the **same** base; resolve `context_assembler.py`, `intelligence_router.py` and `ci.yml` changes explicitly. Do not apply two separate timing layers on one hot path.
2. Verify new scripts contain no network calls, secret leaks or automatic provider writes; run targeted tests before adding them to the canonical master suite.
3. Record import SHAs and full changed-file list, run required **entire** exact-head CI; retain manual and independent negative acceptance; then close duplicate branches only after human-reviewed clean integration.
4. Reconcile required GitHub branch-status checks before renaming/deleting any workflow with an external required status. The static workflow audit explicitly marks those required-check states as UNKNOWN.
5. Merge into `main` or deploy production only under explicit independent release authorization and rollback certification.

## One-page gate status

- **Done:** register retained; ECO-001 consolidated administratively; ECO-002 and ECO-003 opt-in instrumentation committed; ECO-004 source trace and PR610 targeted voice test work; many independent isolated PostgreSQL/synthetic tests; QA runner and evidence manifests.
- **Not done:** zero fully verified 43 findings; 29 explicit release blockers; exact-head QA all-green; representative p50/p95; QA ingress exact SHA/database/401 or 403 readback; real iOS voice/provider; governed consumer readback; signed owner approval and rollback; production deployment.
- **Do not infer:** 95 workflows imply 95 redundant tests, or 11 PRs are safe to merge simply because their targeted checks pass.

This document is a scoped governance and consolidation record, not evidence of completed release certification.
