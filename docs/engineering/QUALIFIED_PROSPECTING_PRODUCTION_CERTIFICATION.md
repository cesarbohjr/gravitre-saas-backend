# Qualified Prospecting Play — production certification gate

Status: **NOT CERTIFIED**. This document is a test and release gate, not proof of execution. Related: #567 (implementation), #581 (agent/catalog reconciliation), #587 (shared intelligence compatibility).

## Current evidence (2026-10-28)
- Railway backend production deployment succeeded on 2026-10-27 at commit `e1a2a8b9e29a87489809f64cb5a42f3029b6fd5b`. This **does not prove** the Qualified Prospecting Play is installed, enabled or runnable.
- #567 describes the six-stage workflow as metadata with missing callable stage actions, incomplete provider coverage and incomplete durable review/credit evidence. Do not mark ready on the strength of the catalog, UI, or read-only one-step workflow.
- Production variables listing alone does not prove feature flags or database migrations. Do not disclose credential values.

## Phase 0 — identify exact deployed implementation
- [ ] Reconcile #567 head and main; enumerate canonical Play, workflow installation, stage handlers, registered action catalog, feature flags, migrations and frontend route.
- [ ] Verify active Railway deployment source commit and actual backend version; compare against commit containing the required code.
- [ ] Verify test tenant Play installation and readiness API without mutating production data; record sanitized evidence.

## Phase 1 — finish and certify engineering before merge
- [ ] Implement and register all six callable stages: discover, research, enrich, verify, consent_review, stage. Test real canonical workflow wiring and durable checkpoints.
- [ ] Audit each provider action against its executable handler and manifest. Distinguish permitted free/open data from paid/BYO sources; enforce source licensing, rate limits and credit budgets.
- [ ] Verify tenant isolation/RLS, credential vault, credit reservation and reconciliation, deduplication, provenance, suppression, CASL/consent basis, review queue and immutable audit evidence.
- [ ] Ensure stage produces **pending approved-action records only**, never automatic CRM writes; no email/outreach sends.
- [ ] Pass unit, integration, migration replay, security, workflow and browser tests on final head; capture run links and results.

## Phase 2 — gated production deployment
- [ ] Obtain explicit separate approval to merge and deploy. No deployment authorized by this PR.
- [ ] Deploy production with Play disabled by default; confirm flag and tenant allowlist are off outside isolated test tenant.
- [ ] Confirm schema and API health and no unrelated customer behavior change.

## Phase 3 — controlled production E2E (only after Phase 1/2)
- [ ] Obtain authorization for isolated production smoke tenant, permitted data sources, budget and external provider calls. Do not run without it.
- [ ] Execute all six stages with small bounded batches, using lawful/approved discovery sources and controlled test contacts; record sanitized per-stage results and evidence IDs.
- [ ] Exercise failure paths: missing source rights, invalid consent, suppressed contacts, mismatched identities, unavailable provider, rate limits, exhausted credits, tenant-crossing attempts and approval denial.
- [ ] Verify no external CRM writes or sends occur before explicit approval; test authorized staging only, then cleanup/rollback.
- [ ] Capture actual provider responses, counts, workflow IDs, trace links, source commit, deployment ID, environment and test time, without contact PII or credentials.

## Exit / release decision
- [ ] Independent reviewer confirms all evidence and no unresolved critical defects.
- [ ] Mark production E2E **PASS** only with actual completed run evidence. Otherwise remain **BLOCKED/PARTIAL** with exact failure categories.
- [ ] Separate customer activation approval; keep outreach disabled unless separately approved.

**Dependencies:** #567 owns implementation, this PR owns the certification checklist and evidence, #581 consumes the verified capability without duplicate agent SKUs. Do not merge or deploy #581/#587 as part of this work.
