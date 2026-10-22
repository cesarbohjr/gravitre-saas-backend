# Consolidation audit — 37 open PRs versus production main

Audit initiated 2026-10-22. Audit base: `main` at `32f0d96792ee5b73622968fe0ca8953f42800705`.

## Rules
- This branch starts from main. Do **not** wholesale-merge stale PRs or replay unrelated historical commits.
- A PR being ahead/diverged does **not** prove its behavior is absent from main: classify by semantic code, tests, migrations and configuration equivalence.
- For each source PR, compare changed files with their current main equivalents, record evidence for: PRESENT / PARTIAL / MISSING / OBSOLETE / CONFLICTING. Carry forward only verified missing desired behaviors and tests.
- Reconcile overlapping PRs by feature, preserving latest production invariants. Never copy old dependencies, RLS policy changes, migrations, or billing authorization changes without independent tests.
- One implementation branch and ultimately one consolidation PR targeting main. Commit in reviewed, tested slices; do not merge until green CI and release gates. Keep existing PRs intact until explicit supersession evidence.

## Current factual findings
- GitHub lists exactly **37 open PRs**.
- Git history comparisons: **2 ahead** (#555, #556); **35 diverged**; **0 behind/identical**. These results do **not** establish functional gaps.
- #556 modifies package manifests and pnpm locks; dependency security audit must pass.
- #555 **verified missing and implemented in this consolidation branch**: main advertised desktop v0.1.0, PR #555 advertises v0.3.0; GitHub release `desktop-v0.3.0` exists, is published, and its nine assets include all five manifest downloads. Consolidation commit `70db9d7ee2ef8e9e4bdc6c19f47b774d08284874` updates `apps/web/public/desktop/latest.json`. CI/deployment not yet certified.
- #553 adds migration-history recovery workflow/scripts; previously observed metadata rollback drill failure, so retain release block until recovery gate succeeds.
- #540 adds seven-layer intelligence certification workflow and tests.
- #504 changes Stripe invoice webhook authority and billing tests; verify current main behavior, do not merge historical webhook implementation blindly.
- #496 and #426 are documentation-only comparisons (audit matrix; release runbook). Compare content relevance before transferring.
- #361 has broad security, RLS, memory and ML changes and must be reviewed as individual requirements, not one merge.
- Marketplace 3.0 (#261-#289) is heavily overlapping and ~900 commits behind main; consolidate requirements across all branches before any selective implementation.

## Source PR inventory — equivalence not yet certified
### Security / desktop / database
- [ ] [#556](https://github.com/cesarbohjr/gravitre-saas-backend/pull/556): classify changed behaviors against main; capture file/test evidence and missing delta.
- [x] [#555](https://github.com/cesarbohjr/gravitre-saas-backend/pull/555): classify changed behaviors against main; capture file/test evidence and missing delta.
- [ ] [#553](https://github.com/cesarbohjr/gravitre-saas-backend/pull/553): classify changed behaviors against main; capture file/test evidence and missing delta.

### Intelligence / acceptance / billing / audit
- [ ] [#540](https://github.com/cesarbohjr/gravitre-saas-backend/pull/540): classify changed behaviors against main; capture file/test evidence and missing delta.
- [ ] [#514](https://github.com/cesarbohjr/gravitre-saas-backend/pull/514): classify changed behaviors against main; capture file/test evidence and missing delta.
- [ ] [#504](https://github.com/cesarbohjr/gravitre-saas-backend/pull/504): classify changed behaviors against main; capture file/test evidence and missing delta.
- [ ] [#496](https://github.com/cesarbohjr/gravitre-saas-backend/pull/496): classify changed behaviors against main; capture file/test evidence and missing delta.
- [ ] [#480](https://github.com/cesarbohjr/gravitre-saas-backend/pull/480): classify changed behaviors against main; capture file/test evidence and missing delta.

### Operator / release / voice / platform
- [ ] [#444](https://github.com/cesarbohjr/gravitre-saas-backend/pull/444): classify changed behaviors against main; capture file/test evidence and missing delta.
- [ ] [#429](https://github.com/cesarbohjr/gravitre-saas-backend/pull/429): classify changed behaviors against main; capture file/test evidence and missing delta.
- [ ] [#426](https://github.com/cesarbohjr/gravitre-saas-backend/pull/426): classify changed behaviors against main; capture file/test evidence and missing delta.
- [ ] [#361](https://github.com/cesarbohjr/gravitre-saas-backend/pull/361): classify changed behaviors against main; capture file/test evidence and missing delta.
- [ ] [#354](https://github.com/cesarbohjr/gravitre-saas-backend/pull/354): classify changed behaviors against main; capture file/test evidence and missing delta.
- [ ] [#347](https://github.com/cesarbohjr/gravitre-saas-backend/pull/347): classify changed behaviors against main; capture file/test evidence and missing delta.
- [ ] [#336](https://github.com/cesarbohjr/gravitre-saas-backend/pull/336): classify changed behaviors against main; capture file/test evidence and missing delta.
- [ ] [#325](https://github.com/cesarbohjr/gravitre-saas-backend/pull/325): classify changed behaviors against main; capture file/test evidence and missing delta.

### Marketplace 3.0
- [ ] [#289](https://github.com/cesarbohjr/gravitre-saas-backend/pull/289): classify changed behaviors against main; capture file/test evidence and missing delta.
- [ ] [#278](https://github.com/cesarbohjr/gravitre-saas-backend/pull/278): classify changed behaviors against main; capture file/test evidence and missing delta.
- [ ] [#277](https://github.com/cesarbohjr/gravitre-saas-backend/pull/277): classify changed behaviors against main; capture file/test evidence and missing delta.
- [ ] [#276](https://github.com/cesarbohjr/gravitre-saas-backend/pull/276): classify changed behaviors against main; capture file/test evidence and missing delta.
- [ ] [#275](https://github.com/cesarbohjr/gravitre-saas-backend/pull/275): classify changed behaviors against main; capture file/test evidence and missing delta.
- [ ] [#273](https://github.com/cesarbohjr/gravitre-saas-backend/pull/273): classify changed behaviors against main; capture file/test evidence and missing delta.
- [ ] [#272](https://github.com/cesarbohjr/gravitre-saas-backend/pull/272): classify changed behaviors against main; capture file/test evidence and missing delta.
- [ ] [#271](https://github.com/cesarbohjr/gravitre-saas-backend/pull/271): classify changed behaviors against main; capture file/test evidence and missing delta.
- [ ] [#267](https://github.com/cesarbohjr/gravitre-saas-backend/pull/267): classify changed behaviors against main; capture file/test evidence and missing delta.
- [ ] [#265](https://github.com/cesarbohjr/gravitre-saas-backend/pull/265): classify changed behaviors against main; capture file/test evidence and missing delta.
- [ ] [#264](https://github.com/cesarbohjr/gravitre-saas-backend/pull/264): classify changed behaviors against main; capture file/test evidence and missing delta.
- [ ] [#263](https://github.com/cesarbohjr/gravitre-saas-backend/pull/263): classify changed behaviors against main; capture file/test evidence and missing delta.
- [ ] [#261](https://github.com/cesarbohjr/gravitre-saas-backend/pull/261): classify changed behaviors against main; capture file/test evidence and missing delta.

### Verified execution and conversational UX
- [ ] [#251](https://github.com/cesarbohjr/gravitre-saas-backend/pull/251): classify changed behaviors against main; capture file/test evidence and missing delta.
- [ ] [#250](https://github.com/cesarbohjr/gravitre-saas-backend/pull/250): classify changed behaviors against main; capture file/test evidence and missing delta.
- [ ] [#249](https://github.com/cesarbohjr/gravitre-saas-backend/pull/249): classify changed behaviors against main; capture file/test evidence and missing delta.
- [ ] [#248](https://github.com/cesarbohjr/gravitre-saas-backend/pull/248): classify changed behaviors against main; capture file/test evidence and missing delta.
- [ ] [#247](https://github.com/cesarbohjr/gravitre-saas-backend/pull/247): classify changed behaviors against main; capture file/test evidence and missing delta.
- [ ] [#246](https://github.com/cesarbohjr/gravitre-saas-backend/pull/246): classify changed behaviors against main; capture file/test evidence and missing delta.
- [ ] [#245](https://github.com/cesarbohjr/gravitre-saas-backend/pull/245): classify changed behaviors against main; capture file/test evidence and missing delta.
- [ ] [#231](https://github.com/cesarbohjr/gravitre-saas-backend/pull/231): classify changed behaviors against main; capture file/test evidence and missing delta.

## Exit criteria
1. All 37 PRs have evidence-backed disposition; all truly missing intended features listed by file, behavior, test and original PR.
2. Changes implemented only once on this branch, including necessary regression coverage and migrations with rollback evidence.
3. Web build, backend pytest, security audit, integration smoke, tenant/RLS and billing tests pass; migration replay and rollback acceptance pass.
4. One consolidation PR reviewed and merged to main; deployment verifies Railway/Vercel exact SHA plus runtime smoke before old PRs/branches are closed or removed.

**Important:** This file starts an auditable reconciliation. No claim is made that semantic equivalence review or implementation of all missing items has finished.
