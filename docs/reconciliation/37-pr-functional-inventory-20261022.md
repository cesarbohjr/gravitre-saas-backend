# Gravitre — completed 37-source functional review and consolidation plan

Reviewed 2026-10-22 against frozen main `32f0d96792ee5b73622968fe0ca8953f42800705`.
Destination: `consolidation/37-pr-functional-reconciliation-20261022`, then one reviewed integration into `main`.

## Review result

All 37 source PRs have a functional disposition below. Their source heads, every returned changed path, current/relocated path, textual evidence and hashes are recorded in `37-pr-functional-evidence-20261022.json`. This is a completed repository code review and implementation decision record, not a production certification or a claim that the resulting changes have shipped. No application code was changed during this review.

The source PRs are requirements and evidence, not 37 merge instructions. Preserve current main and implement only the unique behavior listed here. Disposition ADD means an identified source-level gap; SUPERSEDED means preserve newer main behavior; SELECTIVE/TEST means adapt residual behavior or regression intent. No filename-only absence is used as proof that a relocated frontend is missing.

### Corrections to the earlier inventory

- Shared context and autonomous-loop helpers exist but have no application callers. Their integration is a real gap, not equivalent-core completion.
- Marketplace DOES have a publish gate through `validate_asset_payload(publish=True)` into `schemas._assert_publish_ready` and `certify_outcome_pack`, on internal/public review and approval and seeding. The missing safeguard is **trusted, persisted, digest-bound production evidence**, not all certification enforcement.
- Several SQL files are timestamp-renamed equivalents, not missing migrations. Do not replay them under their historical names.
- BE21 is already implemented by a safer workflow-only, single-use service on main; the older generic endpoint is not the correct port.
- #540 includes executable scripts at its recorded head despite stale documentation-only PR prose. #553 already includes two squash fixtures and pgvector reinstall after both resets at its recorded head.
- Older voice corpora have a runtime/evaluation-separated replacement. Preserve it rather than injecting competing examples.

## Single-branch implementation backlog

| Order | Deliverable | Source requirements | Concrete implementation and acceptance |
|---|---|---|---|
| 1 | Reproducible baseline and secure dependencies | #553 #556 #555 #426 | Bring isolated recovery tooling onto this branch, prove native replay/parity/restore/atomic metadata drills, retain data-free evidence. Coherent root/web manifests and locks; real desktop artifacts. No historical SQL rewrite or production mutation from this audit. |
| 2 | Canonical context and observation loop | #247 #248 #246–#251 #336 | Integrate the existing helpers into current kernel/reconciliation, not a second runtime. Fix companies count and safe read continuations. One write terminalizer, no URL/accepted/success-boolean proof, no stale approval or cancelled-turn write. |
| 3 | Acceptance and intelligence visibility | #231 #514 #540 #354 #347 #325 | One combined gate reusing current suites; missing consumer/permission/learning tests; 56-cell evidence inventory and three scenarios. Preserve current router, consent and runtime/eval separation; distinguish offline from live results. |
| 4 | Authoritative Marketplace evidence | #263 #264 #265 #271 #273 #275 | One certifier/store/runner/API contract. Service-owned evidence, tenant/install/environment/config/action binding, six behavioral proof dimensions, all advertised actions covered, immutable provenance and digest invalidation. Atomic final publication check at every publish/seed path. |
| 5 | Coherent packs and current UI | #261 #267 #272 #277 #289 #275 #276 #278 | One department portfolio, real skill snapshots, governed Security Ops and RevOps packs; valid authoring types and canonical play registration. Draft/internal until certified. Preserve relocated routes; truthful composition/readiness and verified outcome counts with estimates clearly separate from measurements. |
| 6 | Cross-system regression and release evidence | #429 #361 #444 #504 #480 #496 plus all above | Preserve safer replacements. Full current CI, native DB isolation/concurrency, Stripe events, role boundaries, connector proof, cancellation, memory/source lifecycle, voice/text, Marketplace publish denial and product flows. One final consolidated PR, one main merge, aligned web/backend SHA and independent production acceptance. |

Each order is a sequence of commits on the **same existing consolidation branch**. No application change is authorized by this document to bypass tests, feature-consent requirements or production migration approval. The user receives this complete review before application consolidation; do not merge source branches individually. Before implementation, recheck main and source-head drift and repeat affected comparisons only.

## Design constraints that prevent regression

1. **Execution:** current durable plans, sealed reads, workflow executor and single-use approval/write gate remain authoritative. Context is a projection; bounded autonomy consumes current observations. Cancellation/correction must prevent the provider write itself, including delayed workers. Failed/uncertain writes cannot auto-retry. Intentional new writes get distinct identity.
2. **Security:** preserve explicit child membership for MSP access, exact approval arguments, fenced idempotency and consumed-approval tokens. Do not restore permissive historical policies, parent inheritance or default-on lineage/training flags. No duplicate renamed migration.
3. **Certification:** configuration status, tags, generic schema success and fixture reports cannot establish production proof. Check all advertised actions against trusted independent receipts, required failure/permissions/KPI evidence, freshness and exact config. Service-only mutation, scoped reads and reviewer authority. Evidence check and publication must be race-safe; config edits invalidate prior readiness.
4. **Product truth:** historical department source includes production tags, prices and savings without supporting proof. Keep draft/internal and omit invented claims/prices. Verified events do not measure hours saved; retain main ROI estimate disclosure and measured business metrics as separate fields. Never derive readiness from editable tags.
5. **Cohesion:** one context, one observation loop, one certifier/store/runner, one Security Ops definition, one RevOps definition, one outcome projection and one relocated frontend. Preserve current outcome-contract certification machinery while adding the missing production-evidence boundary; do not replace that module wholesale.

## Per-source decisions

### #556 — Dependency security: ADD

Source: `claude/next-security-16-4` at `5a11898f62aaa7075a4166de726e7a0fa4bc6ada`. [PR #556](https://github.com/cesarbohjr/gravitre-saas-backend/pull/556)

**Compared behavior:** Main retains Next 16.3.6 in the web manifest and lockfile and the older root dependency. The PR changes both manifests and both lockfiles, including proxy-addr.

**Resolution:** Carry one coherent dependency update across both install roots; frozen installs, audit, lint, types, build and tests. Revalidate advisory/version at implementation time; PR prose is not advisory verification.

**Evidence:** apps/web/package.json; apps/web/pnpm-lock.yaml; package.json; pnpm-lock.yaml. Full changed-path comparison is in the evidence JSON.

### #555 — Desktop fallback manifest: ADD

Source: `claude/project-thread-o8a2jh` at `978b4f3bfa1f1955d27b983ea12a27d9aaf7a755`. [PR #555](https://github.com/cesarbohjr/gravitre-saas-backend/pull/555)

**Compared behavior:** Main fallback is v0.1.0; the source patch changes version, published date and five platform download URLs to v0.3.0. This is separate from the browser release-discovery path.

**Resolution:** Update fallback after checking release assets, platform names and integrity/signing evidence. Preserve dynamic newest-release lookup and offline/rate-limit fallback.

**Evidence:** apps/web/public/desktop/latest.json. Full changed-path comparison is in the evidence JSON.

### #553 — Migration recovery tooling: ADD / REPAIR

Source: `repair/supabase-migration-replay-baseline` at `24c24c68ab63d23c3b80fe882d3d29fe89c18a0f`. [PR #553](https://github.com/cesarbohjr/gravitre-saas-backend/pull/553)

**Compared behavior:** None of the 14 recovery paths is on main. Source head now reinstalls pgvector after both resets and contains two earlier fixture migrations for squash. The earlier single-fixture diagnosis is stale for this head.

**Resolution:** Bring recovery tools into this branch; refactor duplicated reinstall into one verified helper; run real replay/parity/restore/concurrency and actual metadata rollback/success. Keep production read-only during review; separately approve any live history adoption.

**Evidence:** scripts/migration_recovery/*; .github/workflows/migration-history-recovery.yml. Full changed-path comparison is in the evidence JSON.

### #540 — Intelligence certification coverage: ADD

Source: `test/phase3-intelligence-certification-foundation` at `8f1ac1987899543310a26c78cf4cef5ba3972137`. [PR #540](https://github.com/cesarbohjr/gravitre-saas-backend/pull/540)

**Compared behavior:** Five source files are absent on main. Source head has executable inventory validation and three offline test bundles, despite its older description saying documentation only. build() initializes all 56 cells NOT_TESTED; an ordinary successful inventory job is not certification.

**Resolution:** Retain 7-by-8 coverage and three bundles, bind cells to executed evidence, and distinguish inventory success, offline contracts and live certification. Reuse current phase2/12-scenario suites; add no second intelligence router.

**Evidence:** backend/scripts/phase3_intelligence_coverage.py (source); .github/workflows/phase3-offline-12-scenarios.yml (main). Full changed-path comparison is in the evidence JSON.

### #514 — Learning and acceptance: TESTS / ADAPT

Source: `fix/acceptance-remediation-20261019` at `d4848e0bf8cb3951358b3d536e75e338c578da0e`. [PR #514](https://github.com/cesarbohjr/gravitre-saas-backend/pull/514)

**Compared behavior:** All added production lines in outcome_learning_handler, schema_param_extractor and sentiment_friction_service are present. Three proposed test files are absent, including role-boundary and incomplete-companion regression expectations.

**Resolution:** Preserve current services; adapt missing permission, alias extraction, timeout, sentiment and learning-delivery tests to actual routes and ReAct contracts. Do not restore the incomplete checkpoint wholesale or loosen admin-only endpoints to satisfy stale tests.

**Evidence:** backend/app/services/outcome_learning_handler.py; schema_param_extractor.py; sentiment_friction_service.py; source tests/test_production_acceptance_regressions.py. Full changed-path comparison is in the evidence JSON.

### #504 — Stripe subscription authority: PRESERVE

Source: `fix/stripe-authoritative-invoice-webhooks-20261018` at `048434ffd91e7a8e186018c3630d566f2cc1190a`. [PR #504](https://github.com/cesarbohjr/gravitre-saas-backend/pull/504)

**Compared behavior:** Main invoice notifications leave subscription status to lifecycle events and retain audit; cache invalidation is in finally. Both authority regression test functions are present and adapted to org_billing, unlike the older subscriptions assertion.

**Resolution:** No application port. Keep current lifecycle-authority and cache tests; retain accurate historical audit notes only.

**Evidence:** backend/app/routers/webhooks/stripe.py::_apply_stripe_event/_process_stripe_event; backend/tests/billing/test_invoice_subscription_authority.py. Full changed-path comparison is in the evidence JSON.

### #496 — MCP reconciliation matrix: DOCS

Source: `audit/mcp-frontend-reconciliation-20261017` at `e488356ddb753aeecf2772e2c1927bf7544d2960`. [PR #496](https://github.com/cesarbohjr/gravitre-saas-backend/pull/496)

**Compared behavior:** Source is one documentation file, not an implementation. It maps existing Connector/Capability/Agent/Approval/Run surfaces and explicitly makes granular grant UI and execution crosswalk conditional investigations.

**Resolution:** Preserve the matrix as dated source evidence. Add its grant-administration and MCP execution-ID crosswalk acceptance cases to the canonical plan; do not turn a documented question into an invented feature or new page.

**Evidence:** source docs/delivery/frontend-backend-3plus-reconciliation-matrix.md. Full changed-path comparison is in the evidence JSON.

### #480 — Approval probe diagnostics: SUPERSEDED

Source: `fix/release1-live-fixture-constraints-20261016` at `a859fc71c713416a4b0809b821c84dc0c57e1e67`. [PR #480](https://github.com/cesarbohjr/gravitre-saas-backend/pull/480)

**Compared behavior:** Main already logs exception type, stage and code and exits 2. The proposed source only adds code to the older diagnostic.

**Resolution:** No port; keep richer main diagnostics and fail-closed exit.

**Evidence:** scripts/verify_release1_live_approval_bypass.py. Full changed-path comparison is in the evidence JSON.

### #444 — BE21 recommendations and flags: SUPERSEDED / SELECTIVE

Source: `release/be21-and-audit-gaps` at `a76f4ad384a4e00290abd7463c51796aebe989cc`. [PR #444](https://github.com/cesarbohjr/gravitre-saas-backend/pull/444)

**Compared behavior:** Main router includes governed_recommendations with org/user/type/expiry single-use claim, workflow-only execution and verified=false until proof. Its service-only table migration replaces the old broader endpoint/table design. Main intentionally retains default-off lineage with approved environment allowance; source enables it globally. Roadmap toast wording differs.

**Resolution:** Preserve safer main endpoint and migration 20261022160000. Do not import old generic operator execution or duplicate migration. Keep environment-specific lineage policy; no automatic flag activation. Only adopt useful roadmap wording with a verified support contact.

**Evidence:** backend/app/operators/router.py; governed_recommendations.py; supabase/migrations/20261022160000_be21_governed_recommendations.sql; scripts/railway_safety_vars.py. Full changed-path comparison is in the evidence JSON.

### #429 — Release 2–4 security and UX: MOSTLY SUPERSEDED

Source: `cursor/full-release-implementation-6b92` at `4f2547c3b6f354adbde83ce4a443d5da54ecee67`. [PR #429](https://github.com/cesarbohjr/gravitre-saas-backend/pull/429)

**Compared behavior:** Auth/session, Freshservice panel/proxy, lifecycle envelope, cost binding, approval scope and idempotency core changes are on main. Three historical migration names have timestamp-renamed equivalents. Main MSP access now requires explicit child membership and main write fingerprints/queue have later hardening.

**Resolution:** No 73-file transplant. Preserve narrower MSP authorization, exact write fingerprinting and current queue fencing. Carry only missing regression assertions/documentation after matching current contracts. Do not restore parent-membership inheritance.

**Evidence:** backend/app/services/workflow_approval_scope.py; write_invoke_idempotency.py; msp_org_context.py; apps/web/lib/supabase/server.ts; backend/app/workers/workflow_queue.py. Full changed-path comparison is in the evidence JSON.

### #426 — Release migration runbook: DOCS / SUPERSEDED

Source: `chore/release-queue-and-migration-runbook-20261013` at `02a9cb2a7af147731ad41cdc431ede20f8119650`. [PR #426](https://github.com/cesarbohjr/gravitre-saas-backend/pull/426)

**Compared behavior:** Only a dated release-queue document. Main has an evolved version; its old pending PR list and sequential source-PR merge instruction conflict with the one-branch strategy.

**Resolution:** Retain single migration authority, SHA/checksum approval, staging, backups and append-only evidence. Replace old queue with this plan; no old merge train.

**Evidence:** docs/delivery/RELEASE_QUEUE_AND_MIGRATIONS.md. Full changed-path comparison is in the evidence JSON.

### #361 — Foundation, security, memory and ML: MOSTLY SUPERSEDED

Source: `claude/project-thread-k1cc3y` at `e9c0d59ed758c60242da1e1404ccac6f1a2faecf`. [PR #361](https://github.com/cesarbohjr/gravitre-saas-backend/pull/361)

**Compared behavior:** Most code and tests from all 63 changed paths are on main. Both historical SQL bodies are identical after ignoring comments/whitespace under newer timestamps. Main champion gate rejects uncomparable metrics, causal training uses measured deltas, and MCP approvals have claim-token fencing beyond this source.

**Resolution:** No wholesale port. Preserve current tenant filters, source liveness, dedupe, permission binding and stricter ML promotion. Do not restore permissive no-metric deployment or weaker MCP approval release. Port only genuinely absent test intent against current code.

**Evidence:** backend/app/ml/intelligence_training.py; causal_analysis.py; backend/app/services/mcp_client_service.py; supabase/migrations/20261011192411_phase1_security_rls.sql; 20261011192424_phase1_memory_recall.sql. Full changed-path comparison is in the evidence JSON.

### #354 — Natural chat and voice: PRESERVE / TEST

Source: `codex/natural-chat-voice-flow` at `5c2dd7a282e77d9549c02db139bea037a8335988`. [PR #354](https://github.com/cesarbohjr/gravitre-saas-backend/pull/354)

**Compared behavior:** Social repair, adaptive research and intent behavior are substantially present. Main lifecycle has newer identity/repeat-write handling; narration suppresses internal knowledge/search progress through normalized tokens. Acknowledgement wording differs but is not a missing capability.

**Resolution:** Preserve current runtime; carry useful behavioral cases for retries, status questions, internal narration and social repair. Do not replace newer lifecycle verification or restore stock acknowledgement lists as a latency fix.

**Evidence:** backend/app/services/action_lifecycle.py; conversation_tier.py; conversational_behavior.py; pipecat_voice/voice_tool_narration.py; tests/services/test_natural_dialogue_regressions.py. Full changed-path comparison is in the evidence JSON.

### #347 — Echo and real interruption: SUPERSEDED

Source: `fix/voice-echo-preserve-real-interruptions` at `0d3c7e74968b80bc0a782c21258283f178c1d910`. [PR #347](https://github.com/cesarbohjr/gravitre-saas-backend/pull/347)

**Compared behavior:** Main is_echo_of protects explicit corrections and requires a contiguous match from one spoken segment. It has focused echo-correction tests; comment/wording differences are not missing behavior.

**Resolution:** No application port. Preserve real microphone barge-in and current per-turn cancellation; include source cases in regression selection.

**Evidence:** backend/app/services/pipecat_voice/voice_audio_origin.py::is_echo_of; backend/tests/services/pipecat_voice/test_echo_correction_guard.py. Full changed-path comparison is in the evidence JSON.

### #336 — HubSpot counts and read continuations: ADD / ADAPT

Source: `fix/chat-incident-hubspot-count-20261008` at `cb8540b002514998c1ccc6e542a10c7c20bcf19f`. [PR #336](https://github.com/cesarbohjr/gravitre-saas-backend/pull/336)

**Compared behavior:** Main listing path handles contacts/deals; source adds companies count, verified total handling and nearest-request continuation resolution. resolve_listing_read_message is absent. Main calls listing synchronously while source offloads I/O and guards replay-cache freshness.

**Resolution:** Adapt companies-count and continuation logic into the sealed read path, retaining pending approval ownership. Require fresh provider total; never count only the first page. Check cache bypass and async offload at current call boundary.

**Evidence:** backend/app/services/listing_f2_read_turn.py::listing_f2_intent/try_listing_f2_read_turn; canonical_cognitive_resolution.py; intent_gateway.py. Full changed-path comparison is in the evidence JSON.

### #325 — Voice tiering and style corpus: SUPERSEDED

Source: `fix/restore-guarded-voice-lite-20261007` at `510ee5cb8a40b6a20fe73974b536fedd4b7fd48a`. [PR #325](https://github.com/cesarbohjr/gravitre-saas-backend/pull/325)

**Compared behavior:** Main uses shared classify_conversation_tier with pending-task and escalation checks; voice/text prompt assembly uses conversation_dna_for_turn. Old JSON corpora are replaced by dialogue_library/runtime_fewshots.json and separate eval_conversations.json.

**Resolution:** Preserve current shared classifier and runtime/eval separation; no old regex tier classifier, duplicate prompt injection, or old corpus import. Keep latency and task-routing tests.

**Evidence:** backend/app/services/operator_task_intent.py::use_spoken_lite_path; conversation_tier.py; module_d_unified_voice_spec.py; pipecat_voice/dialogue_library/__init__.py. Full changed-path comparison is in the evidence JSON.

### #289 — Revenue Operations flagship: ADD / ADAPT

Source: `feat/marketplace3-revenue-operations-v2` at `10492ab687ea09489d2d3c928936250cf48c99c8`. [PR #289](https://github.com/cesarbohjr/gravitre-saas-backend/pull/289)

**Compared behavior:** Dedicated builder and department-portfolio dispatch are absent. Main has generic Revenue Operations catalog content, which is not the same multi-play governed pack. Source depends on the missing department-portfolio substrate.

**Resolution:** Adapt flagship after pack schema/catalog/certification is coherent. Resolve real CRM capabilities, install children, outcome metrics and skill bindings; keep draft/internal until actual proof.

**Evidence:** source backend/app/marketplace/marketplace3/revenue_operations.py; main backend/app/marketplace/seed_catalog.py. Full changed-path comparison is in the evidence JSON.

### #278 — Outcome-first cards: SELECTIVE

Source: `feat/marketplace-3-outcome-ux` at `e41e9f59b7034709572bafed8cf1a8e9c2ecd568`. [PR #278](https://github.com/cesarbohjr/gravitre-saas-backend/pull/278)

**Compared behavior:** Main relocated pages already provide outcome tiles, businessOutcome, contents and featured outcome. Source adds per-type counts and readiness labels, but derives verification from tags/asset.verified and labels estimated hours under Measured value.

**Resolution:** Preserve modern pages. Add useful composition counts and evidence-backed readiness; reject tag-derived production/outcome badges and estimate-as-measured wording.

**Evidence:** apps/web/app/(app)/marketplace/assets/page.tsx; assets/[slug]/page.tsx; source outcomeVerificationLabel. Full changed-path comparison is in the evidence JSON.

### #277 — Security Operations governed actions: ADD / ADAPT

Source: `feat/marketplace-3-security-operations-v2` at `a4769bce12b11d11baae5e0d6f9dcb631b0fdc33`. [PR #277](https://github.com/cesarbohjr/gravitre-saas-backend/pull/277)

**Compared behavior:** Main has registered managed Okta read handlers and most action extensions, including groups/apps/factors. Dedicated Security Operations pack and canonical eight-play registration are absent. Source action retrieval enrichment also differs.

**Resolution:** Reuse managed connections and current action contracts. Add only missing governed plays/pack/metadata; validate every containment write, approval and independent readback. Never seed a blueprint as production-ready.

**Evidence:** backend/app/services/managed_security_tools.py; connectors/action_catalog/extensions.py; source marketplace3/security_operations.py; plays/catalog.py. Full changed-path comparison is in the evidence JSON.

### #276 — Outcome overview and analytics: SELECTIVE

Source: `feat/marketplace-3-msp-service-desk-v3` at `3161d65c46424aab6419f1b02f6e0e46dba22cd6`. [PR #276](https://github.com/cesarbohjr/gravitre-saas-backend/pull/276)

**Compared behavior:** Relocated UI exists; proposed reusable outcome-pack-overview and verifiedOutcomeEvents/measurementBasis projection do not. Main ROI explicitly labels catalog hours as estimates, which must be retained. Source still turns one verified event into full declared hours.

**Resolution:** Add evidence-linked outcome counts, pack overview and install details to current components. Deduplicate results by tenant/install/run/digest; retain estimate disclosure and never infer measured hours from an event count.

**Evidence:** backend/app/marketplace/roi.py; apps/web/components/marketplace/install-experience.tsx; source outcome-pack-overview.tsx. Full changed-path comparison is in the evidence JSON.

### #275 — Outcome experience, seeding and ROI: SELECTIVE

Source: `feat/marketplace-3-flagship-packs` at `73eb4483ed34045dff9fc773fbf72f41afbe5aa7`. [PR #275](https://github.com/cesarbohjr/gravitre-saas-backend/pull/275)

**Compared behavior:** Modern detail/installed pages and generic publish schema checks exist; explicit persisted-certification helper and seed certification guard do not. ROI changes overlap #276 exactly.

**Resolution:** Implement certification enforcement once across publish and seed; reuse modern routes, one ROI projection and current install contracts. Avoid duplicate pages and historical tests tied to removed paths.

**Evidence:** backend/app/marketplace/publish.py; schemas.py; seed_service.py; roi.py; apps/web/app/(app)/marketplace/installed/page.tsx. Full changed-path comparison is in the evidence JSON.

### #273 — Marketplace completion integration: UMBRELLA / DEDUPLICATE

Source: `feat/marketplace3-completion-integration` at `db26fa8cefd418d9fef24b00064f409bc1eb6211`. [PR #273](https://github.com/cesarbohjr/gravitre-saas-backend/pull/273)

**Compared behavior:** This source overlaps certification store/runner/evidence, Security Ops, department portfolio and UI from multiple PRs. Its permissions probe is fully present on main; the other major historical modules are absent.

**Resolution:** Use as dependency map, never as a whole merge. One canonical implementation of each #264/#265/#267/#271/#272 component, with safer #277/#289 variants and current frontend.

**Evidence:** source backend/app/marketplace/marketplace3/{certification_store,certification_runner,production_evidence,department_portfolio,security_operations}.py. Full changed-path comparison is in the evidence JSON.

### #272 — Security Operations foundation: SUPERSEDED BY ADAPTATION

Source: `feat/marketplace-3-msp-service-desk-clean` at `682badbbe0a03d68d1c996176a4155b91ace93f5`. [PR #272](https://github.com/cesarbohjr/gravitre-saas-backend/pull/272)

**Compared behavior:** Read-only Okta/tool registration overlaps main and #277; pack and plays overlap later source variants.

**Resolution:** Absorb unique blueprint requirements into #277 adaptation; no second Security Ops builder or tool registry.

**Evidence:** backend/app/services/managed_security_tools.py; source marketplace3/security_operations.py; #277. Full changed-path comparison is in the evidence JSON.

### #271 — Production verification evidence: ADD / HARDEN

Source: `fix/marketplace3-evidence-certification` at `7bdffd9283e19f391f0b4120542915bdf0ee0438`. [PR #271](https://github.com/cesarbohjr/gravitre-saas-backend/pull/271)

**Compared behavior:** Main certify_outcome_pack permits production level from declared runtime status plus skill resolution, without runtime_evidence references. Source adds production environment/ref/action coverage and changes seed behavior.

**Resolution:** Require trusted ledger evidence for every advertised runtime action and measured outcome, bound to tenant/install/config/environment. Preserve existing outcome-contract tests and replace status-only certification.

**Evidence:** backend/app/marketplace/marketplace3/certification.py::certify_outcome_pack; source runtime_evidence checks; seed_service.py. Full changed-path comparison is in the evidence JSON.

### #267 — Department portfolio and skill packages: ADD / ADAPT

Source: `feat/marketplace3-outcome-ux` at `a66b4149524ed755bbd4265614ea5f3693ba8ef9`. [PR #267](https://github.com/cesarbohjr/gravitre-saas-backend/pull/267)

**Compared behavior:** Main lacks department_portfolio builder, seven referenced capability-package directories and department play registration. Modern frontend exists. Source original seeds production-verified tags, prices and savings; later variants change this to draft/internal.

**Resolution:** Adapt real pack/play/skill definitions using reviewed snapshots. Keep draft/internal, remove unproven badges and unapproved prices/savings. Reconcile department catalog alternatives; no duplicate generic packs.

**Evidence:** source backend/app/marketplace/marketplace3/department_portfolio.py; capability_packages/*-skills; main seed_catalog.py. Full changed-path comparison is in the evidence JSON.

### #265 — System-owned certification runner: ADD / HARDEN

Source: `feat/marketplace-3-certification-runner` at `0978f0d38ada9277e5162fcce114829c2c48d5b0`. [PR #265](https://github.com/cesarbohjr/gravitre-saas-backend/pull/265)

**Compared behavior:** Runner, production collector and API endpoints absent; authenticated tenant-isolation probe and tests already present. Historical collector filters org and asset-linked installs, but source-of-record success is any verified write rather than proof for all advertised actions.

**Resolution:** Reuse probe. Add restricted server-run certification, immutable evidence and action-complete coverage. Fixture mode may never promote production readiness. Fence environment/config/install/time and trusted writes; no caller-supplied proof.

**Evidence:** backend/app/marketplace/marketplace3/permissions_probe.py; source certification_runner.py; production_evidence.py; routers/marketplace.py. Full changed-path comparison is in the evidence JSON.

### #264 — Digest-bound certification persistence: ADD / HARDEN

Source: `feat/marketplace-3-certification-publish-gate` at `61cc847b12bd3b1e1ff9fe34a901b77f248d1fe3`. [PR #264](https://github.com/cesarbohjr/gravitre-saas-backend/pull/264)

**Compared behavior:** Store, evidence table migration and explicit persisted evidence gate are absent. Main does have an indirect schema-level certification gate, so earlier claims of no publish gate were too broad. Historical FOR ALL authenticated membership RLS is unsafe for authoritative evidence.

**Resolution:** Implement service-only evidence writes, tenant-scoped authorized reads, digest invalidation and atomic publish check. Apply one new reviewed migration after history reconciliation; do not duplicate historical version. Test owner/member/foreign-tenant tampering and TOCTOU.

**Evidence:** source certification_store.py; 20261002030000_marketplace_3_certification_evidence.sql; main marketplace/schemas.py::_assert_publish_ready. Full changed-path comparison is in the evidence JSON.

### #263 — MSP Service Desk evidence standard: ADD / RECONCILE

Source: `feat/msp-service-desk-marketplace-3` at `28c202d928e44c57ccc910858ee23b92db0c64a1`. [PR #263](https://github.com/cesarbohjr/gravitre-saas-backend/pull/263)

**Compared behavior:** Main MSP blueprint exists; source adds six explicit fresh-install/golden/failure/permissions/KPI/readback evidence requirements that current status-based certification lacks. Related #271 uses a different runtime-evidence contract.

**Resolution:** Combine six behavioral requirements with action-complete trusted runtime proof in the one certifier. Keep blueprint tested/governed until proof; do not implement competing evidence parameters.

**Evidence:** backend/app/marketplace/marketplace3/msp_service_desk.py; certification.py; source #263/#271 tests. Full changed-path comparison is in the evidence JSON.

### #261 — Security Ops blueprint and asset authoring: ADD / DEDUPLICATE

Source: `feat/marketplace-3-security-operations` at `53b839cf10ec28d204495c84002abce5c3cb4684`. [PR #261](https://github.com/cesarbohjr/gravitre-saas-backend/pull/261)

**Compared behavior:** Main CRUD allowed types omit play/dataset_pack/dashboard_pack/outcome_pack although schemas support them. Security blueprint and dedicated publish wrapper absent; schema publish checks exist indirectly.

**Resolution:** Expand authoring types with validation and role tests; implement one Security Ops pack via #277 and one persisted publish gate via #264. Do not add a redundant certification engine.

**Evidence:** backend/app/marketplace/crud.py::_ASSET_TYPES; schemas.py; source marketplace3/security_operations.py. Full changed-path comparison is in the evidence JSON.

### #251 — Verified-write terminal lifecycle: PRESERVE

Source: `fix/verified-write-lifecycle` at `2aef2e115c45c51472ac422a7b6f37e66c9bd2fd`. [PR #251](https://github.com/cesarbohjr/gravitre-saas-backend/pull/251)

**Compared behavior:** Main contains verifying/inconclusive statuses, verification_owns_terminal deferral, org-filtered terminalization, conversation update and canonical outcome fanout. Historical SQL is identical under 20261001162827.

**Resolution:** No old lifecycle transplant or duplicate migration. Preserve current readback and cancellation fencing; use its mismatch/inconclusive/repeat-write tests as consolidation baseline.

**Evidence:** backend/app/services/chat_connector_execution_service.py; write_success_verification.py::_finalize_verified_write_run; workflows/constants.py. Full changed-path comparison is in the evidence JSON.

### #250 — Vendor proof boundary: SUPERSEDED / TEST

Source: `feat/execution-verification-lifecycle` at `50d3da7cb7989e1cfad5e3dacc5f411610fae9ab`. [PR #250](https://github.com/cesarbohjr/gravitre-saas-backend/pull/250)

**Compared behavior:** Main uses newer #251-style terminal ownership and lifecycle envelope instead of this source running-state helper. Frontend envelope handles verifying/uncertain, but legacy success=true fallback can still render Completed when evidence is missing.

**Resolution:** Keep canonical newer terminalizer. Add a cross-surface test for accepted-but-unverified legacy payloads; harden write-specific fallback without breaking successful reads or delivered artifacts.

**Evidence:** apps/web/lib/gravitre-ai-runtime-state.ts::deriveAiRuntimeState; backend/app/services/write_success_verification.py. Full changed-path comparison is in the evidence JSON.

### #249 — Conversational completion truth: PARTIAL / TEST

Source: `feat/execution-standard-verified-completion` at `9fd50f86cb27cc4e2805a0905acefb6e026f6025`. [PR #249](https://github.com/cesarbohjr/gravitre-saas-backend/pull/249)

**Compared behavior:** Main post-action consequence/recommendation functions suppress completion for required but unverified writes; UI prefers lifecycle envelopes. Historical new test files are absent; fallback success interpretation remains a residual risk shared with #250.

**Resolution:** One canonical evidence adapter for current write results; test stale/missing envelopes across chat, voice and run UI. No old whole-runtime replacement.

**Evidence:** backend/app/services/post_action_experience_service.py; apps/web/lib/gravitre-ai-runtime-state.ts; components/gravitre/ai-runtime-status.tsx. Full changed-path comparison is in the evidence JSON.

### #248 — Bounded execution loop: ADD WIRING

Source: `feat/phase3-autonomous-execution-loop` at `59f1e691936b88f15814ed7118a7f90cfd76ba31`. [PR #248](https://github.com/cesarbohjr/gravitre-saas-backend/pull/248)

**Compared behavior:** Decision module and strengthened local tests exist, but global app search finds no callers; decide_after_observations bridge and normalized execution_loop slot are absent. A tested helper is not integrated autonomy.

**Resolution:** Wire after the current authoritative observation reconciliation; preserve budgets, same plan ID, approval waits, no autonomous write retry and provider-proof completion. Add end-to-end consumer tests, not only helper tests.

**Evidence:** backend/app/services/autonomous_execution_loop.py::decide_execution_loop; execution_plan_service.py; conversation_state_service.py. Full changed-path comparison is in the evidence JSON.

### #247 — Unified execution context: ADD WIRING

Source: `feat/unified-execution-context` at `ef4960f4dc0418330aa4969c33325c4f798b0c9b`. [PR #247](https://github.com/cesarbohjr/gravitre-saas-backend/pull/247)

**Compared behavior:** Builder and tests exist, but no application caller of build_execution_context; current kernel RETRIEVE lacks the injection and normalized task-state slot.

**Resolution:** Project current durable fields once before planning for text/voice, preserving identity, pending approval and safe stored-dict normalization. Persist only necessary projection state; add actual kernel consumer tests and tenant/repeat-action cases.

**Evidence:** backend/app/services/execution_context.py::build_execution_context; cognitive_turn_kernel.py; conversation_state_service.py. Full changed-path comparison is in the evidence JSON.

### #246 — Vendor-proof wording: SUPERSEDED / SELECTIVE

Source: `fix/verified-execution-truth-contract` at `680402dea18472581e60a2ef013d9cb6f1a50637`. [PR #246](https://github.com/cesarbohjr/gravitre-saas-backend/pull/246)

**Compared behavior:** Main has newer verification terminalization and a substantially redesigned execution panel. The old URL-derived Verified sentence is gone, but the exact vendorVerified UI guard and historical tests are absent.

**Resolution:** Do not restore partial_success promotion or old panel. Reuse explicit current evidence/lifecycle for write result wording, shared with #249/#250, and test that a URL or success boolean is never proof.

**Evidence:** apps/web/components/gravitre/assistant/chat-execution-panel.tsx; backend/app/services/write_success_verification.py; source execution-proof-language.test.ts. Full changed-path comparison is in the evidence JSON.

### #245 — Ask helper white bar: SUPERSEDED

Source: `fix/remove-ai-helper-white-band` at `8c10bb10fc9210ecb2a0954f3765d54aef3256c2`. [PR #245](https://github.com/cesarbohjr/gravitre-saas-backend/pull/245)

**Compared behavior:** Current shell frame has removed the old dock-aware selectors and extra 68/116px reservation. Component structure and clearance classes have evolved; old string test would be stale.

**Resolution:** No application port. Retain modern frame and check full-height/scrolling/mobile clearance in the final visual acceptance.

**Evidence:** apps/web/components/gravitre/app-shell.tsx::AppShellFrame. Full changed-path comparison is in the evidence JSON.

### #231 — Combined conversation acceptance: ADD / ADAPT

Source: `closure/conversational-product-acceptance` at `f036407254cb1aa7afe5b775d7449ce63e1dd8f9`. [PR #231](https://github.com/cesarbohjr/gravitre-saas-backend/pull/231)

**Compared behavior:** The three proposed orchestration files are absent. Main has conversation-parity, voice-SLO, revocation, standing batteries and 12-scenario workflows, but these do not reproduce the proposed combined backend + web + static acceptance entrypoint.

**Resolution:** Build one reusable combined gate using current test selectors and existing suites, on the consolidated head. Keep physical audibility/owner voice judgment separate from offline tests. Do not add duplicate suites or claim production acceptance from CI alone.

**Evidence:** source scripts/run-conversational-product-acceptance.sh; main .github/workflows/conversation-parity-contract.yml; phase3-offline-12-scenarios.yml. Full changed-path comparison is in the evidence JSON.

## Migration cross-reference

The following pairs have identical SQL after stripping comments and whitespace (first five verified directly during review; grants also verified separately):

| Source historical name | Current main name | Action |
|---|---|---|
| 20261011180000_phase1_security_rls.sql | 20261011192411_phase1_security_rls.sql | Preserve main; no duplicate |
| 20261011181000_phase1_memory_recall.sql | 20261011192424_phase1_memory_recall.sql | Preserve main; no duplicate |
| 20261014060000_msp_parent_org_scaffold.sql | 20261016032007_msp_parent_org_scaffold.sql | Preserve main; no duplicate |
| 20261014100000_write_invoke_idempotency.sql | 20261016032018_write_invoke_idempotency.sql | Preserve main; no duplicate |
| 20261014100001_write_invoke_idempotency_grants.sql | 20261016032029_write_invoke_idempotency_grants.sql | Preserve main; no duplicate |
| 20261001155000_verified_write_lifecycle_states.sql | 20261001162827_verified_write_lifecycle_states.sql | Preserve main; no duplicate |
| 20261016032120_operator_recommendations.sql | 20261022160000_be21_governed_recommendations.sql | Replacement design; preserve narrower service-only main implementation |
| 20261002030000_marketplace_3_certification_evidence.sql | No matching current table/reference | New reviewed service-owned evidence schema; reconcile history before assigning/applying migration |

These comparisons establish Git source equivalence, not the contents of a live database. Migration recovery must compare actual deployed history, schema, RLS, grants, functions and extension versions before a production plan is accepted.

## Validation performed for this review

- Retrieved all 37 current PR heads and full paginated patches, cloned repository and checked all 37 local remote refs match recorded head SHA.
- Compared every returned path, including relocated Marketplace/Run routes, and searched application callers, API handlers, publishing validation, table/migration references, newer tests and replacement modules.
- Verified renamed SQL bodies after ignoring comments/whitespace; protected later ML, MSP, approval and BE21 hardening from old-source replacement.
- Existing focused tests: `cd backend && python -m pytest -q tests/services/test_execution_context.py tests/services/pipecat_voice/test_echo_correction_guard.py tests/test_voice_conversation_dna_regression.py tests/services/pipecat_voice/test_dialogue_library.py --noconftest` — **508 passed in 0.49s**. This validates these helpers/style/echo contracts only; it does not demonstrate absent runtime wiring.
- Broader attempted collection including `tests/services/test_autonomous_execution_loop.py` stopped because this clean checkout lacks `pydantic_settings`. No application failure or pass inferred from that environment error. Full dependency-backed CI is an implementation/release gate, not fabricated audit evidence.
- No live provider, production DB, authenticated UI or deploy acceptance was performed by this source review; no production certification is asserted.

## Release and source retirement criteria

Maintain a coverage ledger mapping every addition above to the final implementation commit and executable tests. Require all current repository checks on the combined head; no cancelled run counts as a pass. Verify native tenant/RLS/grant and concurrency behavior, malformed/stale/cancelled approvals, read/write evidence distinctions, billing event ordering, seven-capability unknown/error behavior, Marketplace digest/tamper/race denials, pack install/upgrade/uninstall and text/voice consistency.

Stage the combined release against a production-equivalent schema. Approve actual migration SQL/history changes separately with checksum, backup/recovery drill and immutable SHA. Merge the one consolidated PR only after the agreed gates. Then verify Vercel and Railway serve that merged SHA, inspect independent health response, and collect authenticated product acceptance including Plays/Workflows/Schedules and physical voice where applicable. Update this ledger with exact evidence.

Close source PRs only after their unique requirements are mapped to preserved-main or deployed consolidation evidence. Keep branches until that mapping is complete; no blind bulk closure/deletion. This final plan replaces the old 37-PR merge queue.


## Implementation follow-through

See [CONSOLIDATION_IMPLEMENTATION_20261022.md](CONSOLIDATION_IMPLEMENTATION_20261022.md) for implemented fixes, validation evidence, current remaining requirements and corrections based on the canonical Outcome Pack registry. The original source snapshot above is an audit baseline, not a live implementation status.
