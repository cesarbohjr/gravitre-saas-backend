# Consolidation inventory — 2026-10-22

Baseline: `main`. Source PRs are evidence, not merge instructions. No original PR may be closed solely on commit ancestry.

## Mandatory decision for each PR
Classify each feature/file as already present, equivalent/superseded, missing, conflicting, or obsolete. Record main-path evidence, tests, dependency and security impacts before porting. No blind cherry-picks.

## Source inventory (initial; classifications pending code review)
- [ ] #556 — Bump Next.js to 16.4.2 for a critical RCE advisory
- [ ] #555 — Point the bundled desktop download manifest at v0.3.0
- [ ] #553 — Repair Supabase migration replay with a production-equivalent baseline and PostgreSQL acceptance
- [ ] #540 — Phase 3: define seven-layer intelligence integration certification
- [ ] #514 — WIP: production acceptance remediation and learning visibility
- [ ] #504 — Keep Stripe authoritative for subscription status on invoice webhooks
- [ ] #496 — Audit MCP frontend/backend integration without duplicate UI
- [ ] #480 — Diagnose live forged-approval fixture failure without exposing secrets
- [ ] #444 — Release: BE-21 operator writes, memory lineage flag, connector UX
- [ ] #429 — Release 2–4 engineering slice: approval scope, turn_id, Freshservice UI, MSP scaffold
- [ ] #426 — Document controlled Supabase migration prerequisites and Gravitre release queue
- [ ] #361 — Phase 1 foundation repairs: security, context, memory, ML honesty, ops
- [ ] #354 — Natural chat and voice: keep repairs contextual and email retries on task
- [ ] #347 — Preserve real voice interruptions during echo suppression
- [ ] #336 — Fix HubSpot company counts, cached refusals and misrouted read continuations
- [ ] #325 — Restore guarded low-latency spoken route after Intent Gateway fallthrough
- [ ] #289 — Promote Revenue Operations 3.0 to dedicated flagship pack
- [ ] #278 — Make Marketplace 3.0 outcome-first in the catalog UI
- [ ] #277 — Add governed Security Operations 3.0 upgrade
- [ ] #276 — Finish Marketplace 3.0 outcome-first productization
- [ ] #275 — Complete Gravitre Marketplace 3.0 outcome-first experience
- [ ] #273 — Complete Marketplace 3.0 certification, outcome UX, and Security Operations
- [ ] #272 — Add Security Operations 3.0 outcome pack foundation
- [ ] #271 — Harden Marketplace 3.0 production verification
- [ ] #267 — Add Marketplace 3.0 outcome-first UX and evidence certification
- [ ] #265 — Add system-owned Marketplace 3.0 certification runner
- [ ] #264 — Enforce Marketplace 3.0 certification at publish
- [ ] #263 — Harden MSP Service Desk 3.0 certification
- [ ] #261 — Add Security Operations 3.0 outcome blueprint
- [ ] #251 — Gate connector write completion on vendor verification
- [ ] #250 — Make vendor proof the terminal success boundary
- [ ] #249 — Enforce verified completion across conversational execution
- [ ] #248 — Phase 3: add bounded autonomous execution and replanning loop
- [ ] #247 — Unify execution context across text and LIVE voice
- [ ] #246 — Require vendor proof before connector success
- [ ] #245 — Remove Ask Gravitre white bar across app pages
- [ ] #231 — Add conversational text + voice production acceptance gate

## Merge gates
- Establish baseline CI and production SHA; protect tenant RLS, auth, billing, approvals, agent execution, voice, connector vendor proof, and migration history.
- Bring over only demonstrably missing functionality, refactored to current interfaces; review overlapping Marketplace/Security/voice changes as clusters.
- Require migration replay, rollback and parity, security/dependency audit, unit/integration/E2E, staging acceptance and regression checks.
- Merge only when required checks pass; verify Railway/Vercel production after merge. Close/delete source branches only after mapping their unique functionality and verifying deployment.

Status: inventory captured; functional parity and CI verification not yet completed.