## Runtime repair checkpoint after the development cutover

The first installed-12 run exposed two concrete issues. The Voice wrapper's reusable call did not provide the read-only `pull-requests` permission ceiling required by the called lane's existing protected PR preflight; wrapper ceilings now include contents/actions/pull-requests **read only**, while execution jobs retain their narrower source permissions. This changes no provider grant and adds no write permission.

The old database-initialization job referenced expired artifact run `39929148399` and treated a one-time empty-target readiness check as a normal PR check. PRs now execute the real baseline/read-only guard tests without remote calls. Actual initialization readiness remains a manual, read-only check, requires an explicit retained migration-run artifact, and retains checksum/data-free SQL, dedicated-project, empty-target and no-write enforcement. No assertion or remote target restriction was relaxed. The original 120 source jobs are retained and one offline initialization guard job is added: **121 mapped jobs**, 94 historical source definitions, 12 canonical files.

The existing Master QA runner regenerated the repaired YAML, passed **24 focused unit checks**, the protected manual/billing/HubSpot source-guard pytest checks, and actionlint v1.7.12. Generated files were retrieved from that run's source-only output and are committed without the temporary generation step. This is generated-candidate proof; the resulting commit must still receive its own required-check and Voice startup readback. Main remains unchanged and production release authorization remains false.

---

## Development branch cutover: 94 source YAML files → 12 canonical workflows

The existing PR #611 branch now replaces the 94 source workflow files with the twelve generated canonical files in `.github/workflows/` (**net reduction: 82 files**). This is a reversible development/QA cutover, not a main-branch merge or production retirement. Main's installed automation and production services are unchanged. Original definitions are retained in `master-qa-workflow-source-contracts.json`, the complete source→job map is in the parity report, and Git history preserves rollback. No source is labeled DELETE_SAFE for a production release by the static tooling.

All five required GitHub Actions check names are retained in `qa-01-core.yml`, with main's protection settings unchanged. Core CI reuses its original run concurrency group so obsolete PR-SHA suites are cancelled rather than competing with the new head. Source status functions are scoped to their original dependency graph; an intentionally skipped upstream-metadata reader cannot skip the five required jobs or make a sibling failure impersonate another source result. Metadata Actions-read permission is confined to trusted workflow_run code; PR event routing has contents-read only.

**Verification before committing the cutover:** twenty-three focused unit checks pass; all 96 automatic source-event contracts have positive replay plus negative branch/path/fork/SHA cases. A temporary installed-12 layout passed four source metadata contracts and thirteen manual-acceptance assertion cases, including the actual no-network billing credential guard. Local pytest is unavailable; full pytest execution is an explicit GitHub CI gate. The previous automatic-replacement head passed its synthetic contract and actionlint job; this cutover requires its own exact-head CI and unskipped required-check readback before engineering certification.

Repository caller review found and migrated the deployment-path detector, brand guard's equivalent Core CI path, source-structure tests, and the ECO-001/ECO-002 manual ingress pointers. Existing voice inference-relay authorization is still restricted to its historical PR #587 workflow_ref; it was **not** broadened. Voice-owner/provider qualification remains a separate blocked release requirement. External/dynamic dispatch consumers, old main-run drainage, per-stage resource serialization and live/paid/protected acceptance remain main-release review items. No paid/live workflow or production deployment is dispatched by this cutover.

### Canonical file list

| Lane | Workflow file |
|---|---|
| Core CI/build | `qa-01-core.yml` |
| Auth, tenant, privacy | `qa-02-identity-privacy.yml` |
| Data, migrations, recovery | `qa-03-data-recovery.yml` |
| Governed execution/connectors | `qa-04-governed-execution.yml` |
| Intelligence/agents | `qa-05-intelligence.yml` |
| Voice/devices | `qa-06-voice.yml` |
| Browser/product | `qa-07-browser-product.yml` |
| Billing/marketplace | `qa-08-billing-marketplace.yml` |
| Marketing/acquisition | `qa-09-marketing.yml` |
| Operations/observability | `qa-10-operations.yml` |
| Release/production delivery | `qa-11-release.yml` |
| Independent master acceptance | `qa-12-independent-acceptance.yml` |

Manual runs select the former workflow using the `source` dropdown. Its inputs are namespaced by that source; type/default/approval semantics and protected environments remain enforced. Billing/voice reusable calls retain their exact suite. The main release authorization remains false, the 43-finding register's statuses/owners/order are unchanged, and bulk remediation resumes only after this branch's consolidation verification passes.

---

## Automatic replacement routing implemented — qualification pending

The twelve staged lane definitions now include source-preserving push, PR, schedule, manual and reusable entrypoints. `route-workflow-event.py` evaluates the retained source branches, paths, event types and cron expressions; unknown comparison history or unsupported filters fail closed. All **96 automatic source-event contracts** have positive offline replay coverage, with negative branch/path, repository/fork, missing-evidence and run-binding cases. The focused suite currently has **21 passing checks**.

Downstream canonical runs consume per-source outcome artifacts bound to the upstream run ID and head SHA; a sibling source failure cannot masquerade as another source's result. The release lane does not subscribe to itself: its former downstream smoke edges are explicit job dependencies. Reusable billing/voice calls retain their selected suite. Routing jobs have only contents/actions read access; provider/deploy jobs keep their source permissions and environment controls. Artifact redirects strip the GitHub Authorization header before crossing origins.

**Concurrency change requiring runtime qualification:** manual selected-source runs retain source-wide groups; automatic runs serialize repeated instances of each source job/matrix resource. Cancellation now operates per stage rather than cancelling an entire former multi-job source workflow at once. This is an explicit implementation difference, not a claim of byte-for-byte concurrency equivalence. Candidate lock groups remain isolated from installed originals. No automatic candidate is installed or dispatched by this checkpoint.

Source definitions are retained in `master-qa-workflow-source-contracts.json` for audit, regeneration and rollback after eventual file retirement. The compiler can verify either the current 94-source layout or a future twelve-file installed layout, including retained required check names. The original **94 active workflow files remain installed** until exact-head syntax, event routing, resource serialization, caller references and replacement execution are qualified. Paid/provider-live, production deployment and destructive acceptance have not been authorized or run by this consolidation work. No 43-finding remediation is resumed by these static results.

## Required-check verification resolved; candidate syntax repairs

Authenticated GitHub admin UI readback of main rule `85943377` confirms five required GitHub Actions contexts: **Backend (pytest)**, **Dependency audit**, **Integration Smoke Test**, **Shared runtime text/voice gate**, and **Web (lint + typecheck + build)**. All are owned by existing `ci.yml`. Up-to-date-branch checks, conversation resolution and administrator enforcement remain enabled. No settings were changed. Evidence is in `master-qa-required-checks-readback.json`; the compiler checks that the retained Core CI still supplies all five names. The integration API remains 403, but required-check verification is no longer blocked.

The first candidate validation run passed the eight source-contract tests but actionlint caught two compiler defects: boolean cancellation expressions had been stringified and bare step-level input conditions had not been namespaced. Both transformations are repaired, with regression tests added. There are now eleven focused checks. Runtime candidate execution and automatic-trigger cutover remain outstanding; do not call consolidation complete or restart the 43-finding program yet.

## Replacement implementation checkpoint — staged manual candidates

Twelve candidate YAML files are implemented under `.github/workflow-candidates/`, covering all 94 source workflows and 120 source jobs. `scripts/build-canonical-workflows.py --check` compares them with current source contracts; `scripts/tests/test_canonical_workflows.py` has eight focused checks for job/step retention, permissions/environments, dependencies, typed inputs/defaults, manual approval input validation, reusable-call resolution and tamper rejection. The existing Master QA synthetic job now checks candidates and lints an isolated twelve-file layout using actionlint v1.7.12, without running candidate jobs or changing its existing check name.

**Scope limitation:** these candidates implement selected-source manual dispatch, not automatic-trigger cutover. The parity report explicitly records automatic parity as NOT_IMPLEMENTED and runtime parity as NOT_RUN. All source automatic triggers remain active. Candidate concurrency groups are isolated from originals. Dynamic GitHub workflow identity, environment workflow restrictions, repository-wide callers, protected required checks, exact-head replacement runs and automatic event routing remain unverified. A successful static check does not authorize installation or deletion. Installed workflow count remains 94, with zero retirements in this checkpoint.

GitHub main-branch protection still returns HTTP 403 through the integration. The browser fallback reaches GitHub sign-in; no authenticated admin session is available yet. This access gap blocks required-check readback but is not the only outstanding implementation item.

## Corrected execution mandate — 12-workflow consolidation precedes bulk remediation (2026-11-15)

**Owner instruction takes precedence over the earlier temporary retention strategy.** Consolidate the repository's CI/testing and necessary deploy/operational automation into a comprehensible **target of 12 canonical workflow YAML files** before resuming bulk engineering of the 43 findings. The current branch inventory is **94 files** in `.github/workflows/` (not merely the 23 workflows run on the most recent PR commit); the older 95-file count is historical. A passing PR workflow subset does not certify the entire installed workflow inventory.

The 12 target *responsibilities*, to be implemented by preserving existing commands, permissions, environment protection, artifact names, and branch-check context, are:

| Canonical lane | Essential scope | Safety and trigger policy |
|---|---|---|
| 01. Core CI and build | Web lint/typecheck/build, backend pytest, integration smoke, dependencies, unit/regression and billing smoke | PR/main; changed-path optimization must not hide release blockers |
| 02. Auth, identity, tenant and privacy | Login, memberships/RLS, authorization, tenant isolation, privacy deletion and security/credentials | PR/main plus protected scheduled credential audit |
| 03. Data, migrations and recovery | Supabase migrations, PG ledger, schema history, backup/recovery and durable consumer/outbox | PR for static/isolated; manual protected staging for destructive/live |
| 04. Governed execution and connectors | Chat/Agents/Plays/Canvas tool invocation, approvals, revocation, denial, provider write fencing, connector OAuth and replay/crash safety | PR isolated receiver; manual guarded disposable provider readback |
| 05. Intelligence and agent quality | Routing, contextual retrieval, seven intelligence controls, scenario golden tests, department/agent evaluation, source freshness | PR/main; representative perf baselines separately reviewed |
| 06. Voice, realtime and devices | Confirmed turns, interruption/barge-in, duplex, STT/TTS, live transports, acoustic and physical device gates | Offline PR/daily; explicitly authorized paid/live device runs |
| 07. Browser and end-to-end product | Desktop, extension, onboarding, conversation UI, navigation, signup, authenticated browser, Playwright | PR/main with isolated test accounts |
| 08. Billing, marketplace and revenue | Stripe/Klarna-style billing contract, marketplace install/entitlement/usage, commercial enforcement, attribution, paid checkout | PR isolated; paid/live checks manual with protected credentials |
| 09. Marketing, SEO and acquisition | Analytics, social, SEO publish safeguards, publishing, acquisition data, Lighthouse and IndexNow | PR static; scheduled or event-triggered production publishing stays protected |
| 10. Scheduled operations and observability | Health, connector monitoring, metrics rollups, sync, ingestion, retries, knowledge refresh, operational diagnostics | Explicit schedule/push triggers with tenant protections and write-authorization semantics preserved |
| 11. Release and production delivery | Railway/Vercel release, commit identity, production smoke, rollback, prod variables, deployment integrity | Main/release only, require approved environment and release checks |
| 12. Master audit independent acceptance | 43-finding register, QA00–QA90, isolated PostgreSQL/synthetic receivers, exact-head evidence, nonproduction ingress and independent readback | PR offline + protected manual QA and rollback gates; never infer owner sign-off |

These lanes are **coverage buckets**, not proof they are implemented or that all 94 files can be removed immediately. Several current workflows perform production deploys, recurring business operations, or manual destructive/provider-live approvals; they must be migrated into appropriate guarded lanes before removing their former YAML files. Do not replace a required check with a skipped job that falsely reports success. Preserve each workflow's audit trail and external consumers.

**Deletion rule:** for each source workflow, record (a) its exact current triggers/inputs, (b) jobs and scripts, (c) artifacts/environment/secrets/permissions and callers, (d) target lane and verified parity, (e) required branch-protection status context, (f) replacement run URL on exact SHA, and only then mark `DELETE_SAFE`. If any field is unknown, mark `MIGRATION_BLOCKED` and keep source active; never silently remove security, scheduled operations, or authorized production functionality. Existing GitHub connector was denied main-branch protection read, so required status contexts remain **UNKNOWN** until verified by someone with repository admin access.

**Priority order (binding):** inventory all 94 → implement and verify 12 canonical workflows → migrate and disable old auto triggers in controlled batches → delete redundant source files only after parity/required-check readback → run the 12-lane full end-to-end gate → resume **bulk** engineering remediation against the 43-finding register in original dependency order. ECO-002 remains P0 release-blocking meanwhile; don't prematurely call the findings closed. Do not repeatedly restart 17k+ backend pytest after each small repair during this consolidation.

**Current status:** inventory confirmed 94 files, 12-lane target written, **migration/deletion not yet completed**, production unchanged, no workflows retired by this update. This section supersedes the earlier paragraph that treated broad specialist workflow retention as the final state.

---

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

- `.github/workflows/pr587-controlled-reconcile.yml`: removed from PR #611 as a branch-specific write-capable reconciliation action that was not a test.
- `.github/workflows/pr587-local-acoustic.yml` migrated (same command, manual authorization semantics and artifact outputs) to `.github/workflows/master-qa-qa30-acoustic-qualification.yml`. Original filename removed; acoustic qualification remains intentionally manual.
- `.github/workflows/pr587-offline-cancellation.yml` migrated (identical verification command, artifact upload and old evidence input paths) to `.github/workflows/master-qa-qa30-offline-cancellation.yml`; the workflow self-trigger path was updated. Original filename removed.
- `.github/workflows/issue-535-voice-confirmation.yml` migrated (identical voice approval-race replay, provider-commit pytest checks, no-paid-provider test environment, and artifact output) to `.github/workflows/master-qa-qa30-voice-confirmed-turns.yml`; only the display name and self-trigger path changed. Original filename removed.
- `backend/tests/master_qa/test_master_qa_workflow_consolidation.py` enforces retained specialist coverage and these retirements. **Do not retire any additional distinct source-change or provider-live workflows without a passing replacement and required-check/readback evidence.**

## Current selective evidence imports (not blanket branch merges)

- From #616, retained the **actual-latency report concept**, adapted to the existing canonical `eco003_context_stage` logs rather than importing its conflicting `eco003_context_stage_timing` source patch. Imported equivalent provenance/sample-floor/percentile contracts into `backend/scripts/eco003_context_stage_latency_report.py` and `backend/tests/master_qa/test_eco003_context_stage_latency_report.py`. Independently fixed `ContextAssembler.assemble` exception logging to emit the exception class, not tenant identifiers or raw message. Unique #616 contract tests and source patch still require compatibility review; #616 not closed or merged.
- From #615, retained the **stage-latency reporting concept**, adapted to existing `eco002_route_stage` logs and fixed stage labels rather than adding `router_stage_timing.py` or the three extra independent auto CI workflows. Added `backend/scripts/eco002_route_stage_latency_report.py` and `backend/tests/master_qa/test_eco002_route_stage_latency_report.py`. No correlation IDs exist in canonical stage telemetry; these reports deliberately do **not** infer per-request critical-path latency or authorize concurrency. #615 has additional independent ledger/correlation harnesses requiring separate parity, data-provenance and provider-write review, so #615 remains open/unmerged.
- The master evidence workflow invokes both report test suites alongside existing ECO-002/003 stage and tenant tests. These commits are **not** evidence of green exact-head CI or measured runtime latency.
- GitHub's `main` branch protection read was denied (`Resource not accessible by integration`, HTTP 403); ruleset listing returned an empty list. An empty rulesets API response is **not** proof of no required legacy checks, so status-check deletions and workflow display-name changes still need authorized repository settings readback. Rename legacy workflows only where test coverage and status context were explicitly reviewed.

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
