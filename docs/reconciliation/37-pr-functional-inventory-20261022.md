# Gravitre — 37-PR functional reconciliation and single-branch consolidation plan
Updated 2026-10-22. Target: **one consolidation branch**, `consolidation/37-pr-functional-reconciliation-20261022`, followed by one reviewed integration into `main`. The 37 source PRs are **evidence, not merge instructions**. No application code has been moved.

## Evidence grades / limitations
- **PRESENT** = checked a current main file or direct symbol; **EQUIVALENT-CORE** = important behavior confirmed in main, not complete test parity.
- **CANDIDATE-GAP** = historical implementation absent or changed, alternative behavior not fully excluded.
- **UNVERIFIED** = only PR scope/changed-file inventory known; no claim of behavior equivalence or production validation.
- Every one of 37 PRs has a changed-file inventory. **The full 37-PR functional equivalence review is NOT complete**. Do not mark it complete until per-PR current-main symbol/call-path/test comparisons are recorded.

## High-confidence current-main findings
1. #504: Stripe webhook `backend/app/routers/webhooks/stripe.py` treats invoice events as audit evidence and no longer directly mutates subscription state. **EQUIVALENT-CORE**; compare tests/docs.
2. #247: `backend/app/services/execution_context.py` exposes `build_execution_context`, checkpoint, pending action and provider evidence. **EQUIVALENT-CORE**; trace all text/voice consumers.
3. #248: `backend/app/services/autonomous_execution_loop.py` exposes `decide_execution_loop`, bounded replanning, vendor verification, approval waits. **EQUIVALENT-CORE**; prove live call sites and cancellation gates.
4. #251: `write_success_verification.py` on main contains `_finalize_verified_write_run` and `verification_owns_terminal`; **PARTIAL PRESENT**, not proof of full write lifecycle.
5. #347: `pipecat_voice/voice_audio_origin.py` exists; **PRESENT, parity unverified**.
6. #336: `canonical_cognitive_resolution.py` exists; **PRESENT, parity unverified**.
7. #480: `scripts/verify_release1_live_approval_bypass.py` exists; **PRESENT, parity unverified**.
8. #555: `apps/web/public/desktop/latest.json` exists, but manifest v0.3.0 not detected; **CANDIDATE-GAP**; verify actual release artifact and signing before change.
9. #556: main `apps/web/package.json` pins Next.js 16.3.6, not proposed 16.4.2; **CANDIDATE-GAP / SECURITY PRIORITY**; inspect advisory, lockfiles, current supported version and CI before upgrade.
10. #540: `backend/scripts/phase3_intelligence_coverage.py` absent at original path; **CANDIDATE-GAP**, check replacement CI and existing seven-capability tests.
11. #289: `marketplace3/revenue_operations.py` and `department_portfolio.py` absent at original paths; **CANDIDATE-GAP**, inspect current packs/catalog.
12. #263/#271: `marketplace3/msp_service_desk.py` exists; **PRESENT, parity unverified**.
13. #276/#275: `backend/app/marketplace/roi.py` exists; **PRESENT, parity unverified**.
14. #245: `apps/web/components/gravitre/app-shell.tsx` exists; **PRESENT, CSS/layout behavior unverified**.

## Marketplace: traced frontend, database and publish path
- Main routes relocated to `apps/web/app/(app)/marketplace/assets/page.tsx` and `[slug]/page.tsx`, not older `apps/web/app/marketplace/assets/` paths. Listing has Outcome Pack filter, outcome tiles, featured outcome; detail displays `businessOutcome`, `estimatedHoursSaved`, `packItems`. Do not transplant #267/#275/#276/#278 historical pages. Compare only missing per-card counts, verification labels, ROI and install UX.
- Main contains `marketplace3/certification.py` and `permissions_probe.py` (authenticated tenant-isolation probe), but not historical `certification_store.py`, `certification_runner.py`, `production_evidence.py`, `security_operations.py`. `marketplace/publish.py` has no `outcome_pack` or certification reference. Main router's other submission certification is not proof of Outcome Pack publish gating. **LIKELY CANDIDATE-GAP**: persisted immutable-config-digest evidence, fixture-vs-production distinction, read-only ledger proof, fail-closed publication, governed Security Operations pack.
- #264/#273 share migration `supabase/migrations/20261002030000_marketplace_3_certification_evidence.sql`, absent from current Git main path; repo code search for `marketplace_outcome_pack_certifications` returned no hits. This is **NOT proof of live DB absence**. It defines asset/org FK, digest, level, publish_ready, evidence/report, unique(asset_id,config_digest), indexes and RLS.
- **Security flaw to resolve before reuse**: historical `FOR ALL TO authenticated` organization-membership RLS may permit direct evidence mutation by any member if grants permit. Use narrowly authorized service-role writes, tenant-scoped reads, explicit reviewer/admin authority, tamper resistance, config-digest invalidation, verified provider/ledger proof, and denial tests. Never self-certify based on fixture tests or claimed success.
- **Migration blocker**: #553 historical replay/production-baseline reconciliation must be validated first; never apply duplicate version or rewrite live history without independently verified supported repair and rollback.

## All 37 PRs: functional disposition and specific remaining proof
| PR | Workstream | Disposition today | Required pre-port comparison |
|---|---|---|---|
| 556 | Next.js security upgrade | CANDIDATE-GAP | advisory, main package/lockfile, complete web CI |
| 555 | desktop v0.3.0 manifest | CANDIDATE-GAP | manifest SHA, published binary, checksums/signatures, dependency on #556 |
| 553 | Supabase replay repair | UNVERIFIED RELEASE BLOCKER | exact-head CI, baseline restore/parity, rollback, current live migration history |
| 540 | seven-layer Phase 3 certification | CANDIDATE-GAP | replacement coverage CI, seven capabilities, real/simulated separation |
| 514 | outcome learning and acceptance | UNVERIFIED/PARTIAL PRESENT | handler, sentiment friction, schema params, tests and runtime wiring |
| 504 | Stripe invoice authority | EQUIVALENT-CORE | test assertions, cache invalidation, out-of-order events |
| 496 | frontend/backend MCP matrix | DOCUMENTATION ONLY | compare document against current contracts, retain unique actionable gaps |
| 480 | approval-bypass fixture script | PRESENT | script semantic diff, actual authenticated adversarial CI |
| 444 | BE21 operator and flags | UNVERIFIED | merged BE21 replacements, migration history, operator approval and flag safety |
| 429 | release 2–4 broad security/UX | UNVERIFIED HIGH RISK | 73-file diff, auth, RLS, approval scope, Freshservice, MSP, migrations, CI |
| 426 | release queue migration document | DOCUMENTATION ONLY | merge accurate prerequisites, supersede stale release instructions |
| 361 | foundation/security/ML repair | UNVERIFIED HIGH RISK | 63-file per-service mapping; no wholesale replacement of main |
| 354 | conversational/voice behavior | UNVERIFIED | cognitive LLM, retries, narration, intent, tool/cancel behavior and tests |
| 347 | interruption echo suppression | PRESENT | audio-origin logic, true barge-in versus echo, tests |
| 336 | HubSpot counts/intent | PRESENT | canonical resolution, count tool, read-turn regression |
| 325 | low-latency spoken path | UNVERIFIED | intent gateway, DNA corpus, actual latency, regression |
| 231 | conversation acceptance CI | UNVERIFIED | workflow/script existence and 12 scenario text/voice gate |
| 289 | Revenue Operations flagship | CANDIDATE-GAP | current catalog/portfolio, ROI, governed skills |
| 278 | outcome-first cards | RELOCATED/PARTIAL PRESENT | missing composition counts, proof labels, value presentation |
| 277 | Security Ops governed actions | CANDIDATE-GAP | Okta action registry, tool permissions, eight plays |
| 276 | Outcome Pack UX/analytics | RELOCATED/PARTIAL PRESENT | ROI analytics, install experience, detail UI |
| 275 | Marketplace outcome experience | RELOCATED/PARTIAL PRESENT | publish, ROI, install, catalog and tests |
| 273 | certification/security/UX umbrella | CANDIDATE-GAP + OVERLAP | reconcile #261–#278 individually; no wholesale port |
| 272 | Security Ops foundation | CANDIDATE-GAP + OVERLAP | #261/#277/#273 blueprint equivalence |
| 271 | production verification | PARTIAL PRESENT | certification fail-closed semantics, runtime evidence |
| 267 | department packs/outcome UX | RELOCATED/PARTIAL PRESENT | catalog/seed skills, department portfolio |
| 265 | system-owned certification runner | CANDIDATE-GAP | fixture/prod distinction, API exposure, tests |
| 264 | digest-bound certification publish gate | CANDIDATE-GAP | persistence, schema, role authority, publish enforcement |
| 263 | MSP Service Desk certification | PRESENT | exact level/production-proof checks and tests |
| 261 | Security Operations blueprint | CANDIDATE-GAP | published pack/skills/approval constraints |
| 251 | verified write terminal lifecycle | PARTIAL PRESENT | org-scoped vendor GET, terminal ownership, SQL states and tests |
| 250 | vendor proof terminal boundary | UNVERIFIED/PARTIAL PRESENT | UI status and write-verification race behavior |
| 249 | verified completion runtime | UNVERIFIED/PARTIAL PRESENT | conversational terminal state and frontend proof |
| 248 | bounded execution loop | EQUIVALENT-CORE | invocation paths, stop/approval/write safety, tests |
| 247 | unified execution context | EQUIVALENT-CORE | text/voice wiring, stale state and identity isolation |
| 246 | vendor-proof language | UNVERIFIED/PARTIAL PRESENT | truthful UI completion wording and lifecycle |
| 245 | Ask Gravitre white bar | PRESENT | CSS geometry and visual E2E screenshots |
 
## Dependency graph and implementation waves
**Gate 0 — Freeze baseline:** snapshot `main` SHA, branch heads, PR state, deployed Railway/Vercel SHAs, Supabase schema/migration history, exact required CI. Resolve nine-commit Railway drift noted in #543; distinguish deploy state from GitHub.
**Gate 1 — Migration reliability (#553):** verified all-history replay, restored baseline, schema/RLS/ACL parity, rollback, controlled metadata reconciliation only if authorized; no billable preview without rate approval.
**Wave A — Security/release:** #556 dependency update, #555 manifest only with real artifact; #429/#361 security diff; #444 BE21 and #480 adversarial approvals; #504 no-op if equivalent. Never weaken billing, RLS, org isolation or write gate.
**Wave B — Canonical execution:** #246–#251, #247–#248, #354/#347/#336/#325/#231. Preserve one lifecycle/one context/one vendor proof. Verify cancellation prevents write itself; provider GET evidence required before completed. Text/voice share same authority.
**Wave C — Seven intelligence capabilities:** #514/#540, current sentiment/contextual/causal/temporal/relational/adaptive/predictive router, consent/training/visibility, measured outcomes; don't invent model activation or live inference.
**Wave D — Marketplace 3.0:** #261/#263/#264/#265/#267/#271/#272/#273/#275/#276/#277/#278/#289. Introduce only missing coherent schema, server-side certification, production evidence, publish gating, governed packs, ROI, modern relocated UI. Resolve duplicate overlapping blueprints and migrations.
**Wave E — Documentation/acceptance:** #496/#426 and release docs, end-to-end product flows, CI, migrations, security and rollback.

## Required validation before consolidation can be called complete
1. For each of 37 PRs: record current head SHA, patch-level behavior, main call sites and replacement evidence, test files, status (present/equivalent/missing/conflicting/obsolete), migration/feature flag dependencies and exact resolution. A file-exists check is not sufficient.
2. Merge no source PR wholesale. Implement unique gaps on `consolidation/37-pr-functional-reconciliation-20261022` only, preserving current main contracts. Avoid competing branches, duplicate engines, duplicate migrations or second runtime.
3. Run current required CI (backend, frontend, security, lint/types, migration safety), real PostgreSQL tenant-isolation/RLS, Stripe out-of-order event tests, verified vendor writes, cancellation and approval adversarial tests, Marketplace fixture/live proof and publication-denial tests, seven-layer scenarios, voice interruption and text/voice parity, full E2E where available.
4. Stage against production-equivalent schema; compare before/after baseline and document any feature flag and rollback. Obtain full user-facing findings summary **before application code changes**; then approval/CI and one exact-SHA PR into `main`. Production deployment must match merged SHA and pass smoke/health, not inferred from a green build.
5. Retire source PRs only after exact functional coverage and deployment evidence. Do not delete active source branches while reconciliation is incomplete.

## Current status
**37/37 changed-file inventories captured. Deep functional review partially complete; no full 37/37 equivalence certification, no consolidated application code, no merge/deploy.** This document is the complete *scope and execution plan*, not a claim of completed technical audit.
