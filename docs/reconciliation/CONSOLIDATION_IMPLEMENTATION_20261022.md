# Gravitre consolidation implementation and validation

Single destination: `consolidation/37-pr-functional-reconciliation-20261022`, draft PR #557. Baseline main: `32f0d96792ee5b73622968fe0ca8953f42800705`.

## Implemented in this validation batch

- Corrected the normalized-versus-raw certification digest mismatch. Issuance verifies the current asset belongs to the organization and matches the requested configuration; an empty persistence response is a failure.
- Replaced authenticated certification writes with service-owned writes and tenant-scoped reads. Added an append-only service-owned scenario-check ledger. Caller evidence booleans cannot certify production. Action proof must have matching org/environment/config provenance, verifier attribution and resource identity; six fresh independent scenario receipts are required.
- Added a database publication trigger: missing, expired or stale configuration evidence blocks publication, including direct writes and seed paths. The final row check runs in the publication transaction. Schema-level structure validation remains separate from authoritative production certification. Production proof expires after 30 days.
- Fixed ReAct result recording so late observations do not re-enter the dispatch gate. Cancelled plans remain cancelled during finalization. All pending approval variants block dispatch; an uncertain write cannot authorize another write. Loop budgets follow the active ReAct cap. Multi-write completion requires separate step-bound proof.
- Added HubSpot company totals, latest-read cache exclusion and safe read continuations. Pending approvals keep ownership of confirmations; blocking provider reads are offloaded from the event loop.
- Integrated dependency/lockfile changes from #556 and desktop fallback changes from #555 into this branch. The source PRs remain separate evidence, not additional merge targets.
- Added the seven-by-eight intelligence evidence inventory and three offline contract bundles from #540, with a bounded workflow and correct artifact paths. Inventory success is not live certification.
- Added one combined text/voice/verification acceptance command with outbound-provider transport blocking.
- Added the missing Security Operations blueprint to the current canonical Outcome Pack registry. Its eight Plays use that same registry; no competing portfolio runtime, production badge or paid SKU was introduced. Expanded authorable Marketplace types to Play/dataset/dashboard/outcome packs under existing validation.
- Added installation-scoped verified-outcome counts to ROI reporting, with deduplication, attributable evidence requirements and pre-install/foreign-tenant exclusion. Catalog hours remain explicitly estimates; an outcome event is not measured hours saved.
- Added migration recovery tooling from #553 and factored pinned pgvector installation into one reusable helper invoked initially and after both disposable resets. CI run 39898462502 passed replay, schema parity, baseline restore and native PostgreSQL safety acceptance. Its final CLI-based metadata drill failed because squash does not mutate remote history; the replacement drill now exercises an explicitly atomic, loopback-only PostgreSQL operation. Production adoption and exact-head acceptance remain release gates.
- Fixed the repository brand guard finding in the review document. The official code/repository spelling remains Gravitre.

## Validation evidence

- Existing and new Marketplace/ReAct/count/lint regression batch: **667 passed**, 14.07 seconds, offline network guard enabled.
- Combined acceptance: **58 backend + 52 web checks passed**, including voice narration, cancellation, digest gates, runtime-state proof and static surface guards. No live provider calls permitted.
- Web complete suite after the proof-state changes: **1,909 passed in 300 files**, 42.89 seconds.
- Web TypeScript and production build passed with Next 16.4.2. ESLint: **0 errors**, 209 existing warnings.
- Root and web critical dependency audit commands exited zero. High-severity findings remain reported and require reachability triage; this is not a claim that all dependency findings are resolved.
- Three scenario bundles passed offline: customer support, sales operations and IT incident management. They are existing mocked contract slices, not full production business journeys or seven-layer live certification.
- Embedded PostgreSQL (PGlite) exercised authenticated/anonymous evidence-write denial, tenant read isolation, rejection without certification, exact-snapshot publication and stale-config rejection. It is not a native-server concurrency test.
- Added `tests/db/test_marketplace_certification_pg.py` to CI's native PostgreSQL acceptance, with `GRAVITRE_REQUIRE_PG=1` so a missing server cannot silently skip that gate.
- The initial focused run found the real digest mismatch; it was fixed rather than weakening the assertion. Tests that expected runtime status labels or caller booleans to self-certify production were changed to require governed/not-publishable behavior, with new denial tests. This is intentional safety tightening.
- Full backend offline regression is tracked separately below; do not infer full success from a focused batch. Earlier clean-checkout failures included missing Opacus and an unconstrained Stripe install; dependencies were aligned to repository constraints before rerunning.

## Remaining source coverage and decisions

| Sources | Current disposition |
|---|---|
| #245 #325 #347 #354 #361 #429 #444 #480 #504 | Preserve newer main implementations and regression coverage; no wholesale source transplant. In particular retain narrowed MSP access, workflow-only BE21, fenced MCP approvals and stricter ML promotion. |
| #246 #249 #250 #251 | Preserve canonical terminalizer; residual frontend accepted/unverified handling is hardened in this batch. Native DB and cancellation acceptance still apply. |
| #247 #248 | Existing kernel projection and loop integration retained, corrected and tested. Actual provider-write authority remains in the existing gate. |
| #336 | Company-count and read-continuation gaps implemented and tested. |
| #540 #231 | Coverage inventory/bundles and combined acceptance command implemented. Live certification and physical voice acceptance are separate. |
| #553 | Recovery tooling consolidated and pgvector helper refactored; native replay/parity/baseline/atomic metadata drill still must pass on this exact branch. No production history changes. |
| #555 #556 | Manifest and coherent dependency changes consolidated; keep artifact availability/signing and full release checks in the ledger. |
| #263 #264 #265 #271 #273 #275 | Persisted, service-owned evidence and transactional publication boundary implemented. Organization-admin status/fixture/production-collection APIs and measured outcome collection are now implemented. System-run scenario recording, seed UX remain integration work. The organization publish queue now uses the authoritative certification status and collection APIs. Missing evidence keeps packs unpublished. |
| #261 #272 #277 | Security Ops blueprint and eight canonical registry Plays added. Production execution/containment verification and approved skill snapshots are not inferred from the blueprint. |
| #267 #289 | **Architecture correction:** current main already has manifest-driven growth, sales, customer success, finance, marketing and MSP packs, deriving Plays/metrics/governance centrally. Preserve them. Map genuinely unique historical RevOps/people/executive/skill requirements onto those manifests; do not reintroduce the removed parallel department-portfolio registry. |
| #276 #278 | Server ROI verified-event projection and types added, while current relocated UI is preserved. Organization publish readiness is wired to the authoritative evidence API; broader catalog composition remains to reconcile. Never derive production labels from tags. |
| #514 | Core learning/parameter/sentiment changes already exist. Ported the 22 historical permission/production-acceptance regressions against current routes; all passed. Broader companion consumer requirements remain separately scoped. |
| #496 #426 | Retain accurate MCP acceptance and migration governance requirements; stale PR lists/old merge-train instructions are superseded by this one-branch ledger. |

All 37 source PRs are accounted for. This ledger distinguishes preserved behavior, implemented gaps and remaining integration work; it does not label all source requirements deployed.

## Release constraints

No merge, source-branch closure, production migration or deployment was performed. Keep PR #557 draft until full combined CI, native migration/history acceptance, security review and the remaining functional requirements pass. Any production migration requires a reviewed exact SQL/checksum/backup plan and approval under the repository governance rules. Verify merged/deployed SHA and authenticated product acceptance after an eventual release.

Automatic approval review rejected an earlier acceptance invocation because it attempted `api.openai.com` without an established payload/credential scope. The command was replaced by the repository offline network guard (extended for httpx2); the safer combined gate passed without provider requests. No bypass or provider credentials were introduced.

## Follow-up corrections from actual CI execution

- Added organization-admin certification status and fixture/production collection endpoints. Requests reject extra evidence fields; foreign assets return 404; fixture mode never persists production proof; production collection uses the authenticated actor and stored configuration.
- Added measured KPI/outcome evidence collection bound to current pack Plays, independently verified run IDs, source records, measurement state and freshness. Runtime labels and caller dictionaries remain insufficient.
- The native certification job initially failed before collecting tests because bare `pytest` omitted the application module path; its command now uses `python -m pytest`, consistent with the existing PostgreSQL gates.
- The pinned squash command completed local-file generation and explicitly instructed a separate remote history repair. It cannot prove an atomic remote metadata transaction. The replacement test locks the disposable metadata table, compares the exact original version/name/SQL arrays, deletes and inserts within one transaction, forces INSERT rejection, checks rollback and then checks successful adoption without application schema changes. This changes an incorrect test assumption, not the required rollback assertion. Production remains unreachable by the helper; connection-string query overrides are rejected.
- Strengthened the database trigger to refuse direct authenticated/anonymous publication even when a valid certificate exists; publication must use the governed server review path.
- Refused the reserved localhost namespace before MCP DNS resolution, preserving the explicit private-network opt-in. The historical ReAct completion fixture now carries actual verifier attribution instead of a bare boolean, consistent with the stronger production contract.
- All five v0.3.0 desktop download URLs returned HTTP 200 in HEAD checks. The manifest correctly retains `signed: false`; signing was not asserted or fabricated.
- The first full offline run reached 11,731 passing tests, then stopped with two failures (now corrected) and three Redis integration setup errors caused by absent/blocked local Redis. The complete rerun excludes only the dedicated Redis integration file; native PostgreSQL and Redis remain required in CI.

CI on implementation commit `2a3fba25` passed web tests/lint/types/build, dependency audit, shared text/voice runtime, Department Eval, federated contracts, conversational acceptance, intelligence coverage, Lighthouse, SEO and migration safety. Its two native-job/harness failures are corrected in the follow-up implementation; do not describe the earlier overall CI run as passing.

- Full offline backend rerun reached **11,865 passed, 276 skipped**, with one recipient ambiguity scenario timing out; that scenario and all 96 recipient scenarios passed independently. Isolated bounded recipient mailbox I/O onto the existing dedicated executor and added a regression that occupies the default executor. That regression plus route/loopback follow-ups passed (11 tests). A final full rerun is in progress; prior totals are not represented as a clean full pass.
- Production certification now resolves skill bindings from published, visible capability assets and reuses the canonical current source approval/security/content/snapshot checks. Pack-declared IDs and the legacy caller-resolved ID argument cannot establish reviewed production provenance. Fixture structural validation remains separate.

## Final publication and acceptance follow-up

- Added certification status/configuration/production-collection controls to the existing organization publish queue, with authenticated backend proxies, tenant-scoped cache identity, in-flight duplicate prevention and explicit fixture-versus-production wording. UI proof states require authoritative matching level/readiness fields and withhold readiness on fetch errors; collection requests send mode only. Four UI regressions pass.
- Publication and status both recheck current skill provenance after certificate issuance. Revoked approvals or changed source snapshots withdraw readiness and block publication. Route/store revocation tests: **17 passed**.
- Complete web rerun including the new controls: **1,913 passed**, 301 files. TypeScript, targeted ESLint and production build passed.
- Ported the 22 missing historical #514 permission/production-acceptance regressions and preserved test dependency overrides between cases. They pass against the existing current implementation; no permission relaxation was needed.
- Native migration-history recovery workflow **39900238661 passed** on commit `64998978`: recorded-history replay, original metadata SQL-array restoration, schema parity, fresh baseline restore, native concurrency/authorization checks, rejected-insert rollback and successful atomic metadata-only replacement.
- CI **39900238649** on that commit passed every mandatory native PostgreSQL gate (including certification), Redis integration, web and shared runtime/dependency jobs. Its complete backend regression job was still running at this report checkpoint. Subsequent UI/revocation/test changes require the final-head CI run; earlier green jobs are not represented as final-head acceptance.
