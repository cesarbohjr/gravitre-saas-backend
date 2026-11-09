# PR #611 — Gravitre full-platform audit-to-remediation engineering program

> **Governing product mandate (2026-11-08):** [Autonomous Business Operating Intelligence & Execution Mandate](gravitre-autonomous-business-operating-intelligence-mandate.md). The 43 historical audit findings are a **minimum remediation floor**, not a complete definition of Gravitre. PR #611 must also implement and certify underspecified-goal understanding, evidence-backed cross-department diagnosis, goal-to-typed-plan compilation, reusable Agent/Play/workflow selection, editable executable canvas graphs, governed provider outcomes, calibrated forecasts, proactive goal monitoring, and measured speed/cost/quality. All new capability gates remain NOT CERTIFIED until real execution proof; green historic CI does not imply autonomy. PR #610 owns voice-specific implementation; #611 owns end-to-end business intelligence and execution parity. No release authorization is changed by this document.\n\n**Priority:** this register and its source-to-runtime proof are now the **next governing engineering gate**, ahead of claiming Master QA P0–P5 complete. **Status: BUILDING / NOT CERTIFIED.** PR #610 exclusively owns Voice 3.0 functional/algorithmic repairs; #611 owns platform-wide integration, preflight, deployment evidence and QA30 voice contract ingestion. The two PRs are complementary, not interchangeable.

## Implementation checkpoint — canonical goal ownership consolidation (2026-11-08)

**Scope:** first action from the reconciled PR #610/#611 engineering execution queue; no voice-owner changes, merge or deployment.

- **Single semantic owner:** `app.services.goal_service.GoalService` now owns tenant-aware `analyze_for_org`, semantic `GoalAnalysis` (objective family plus connected/missing data requirements), normalization, safe model fallback and reusing a single analysis during draft generation. No independent business-goal object or intelligence engine.
- **Existing builder owner:** sales is a bounded read-only `app.workflows.sales_growth_recipe`, under the existing workflow graph/builder/runtime, never a parallel dispatcher. Execution and persistence still occur only through existing workflow routers, policies, outbox and finalizer. The recipe requires a semantic `increase_sales` objective; it does not match keyword lists.
- **Duplicate files eliminated:** `app.services.business_goal_intelligence` and `app.services.sales_growth_goal_compiler` removed after route and affected regression imports were migrated. Main-branch code-search showed no pre-existing users of these two new modules; all changed-PR callsites were migrated. Future new entrypoints must call `GoalService` and existing builder/runtime owners directly.
- **Integrity:** when the model is unavailable, the fallback is `cross_functional` / `FALLBACK_UNVERIFIED`, with no invented 90% KPI target, no fabricated objective classification and no execution. Tenant-connected systems are looked up from the authenticated org, not from arbitrary user-supplied connector hints. All other departments remain understood but non-certified for execution until their actual workflow contracts pass.
- **Regression evidence pending at current exact head:** `test_business_goal_intelligence.py`, `test_sales_growth_goal_compiler.py`, `test_sales_growth_from_goal_route.py`, `test_actual_workflow_step_pg.py` under the existing Master QA P0 lane. These files keep their historical names to preserve QA compatibility, not service ownership.
- **Residual work:** model-intent scoring quality, real tenant context/RAG, all-domain typed compilation, Play readiness, builder ID round-tripping, independent live provider readback, actual chat/voice ingress wiring, latency and authority parity are **NOT CERTIFIED** and remain the next phases. Any test PASS only certifies its actual scope.

**Go/no-go:** keep #611 unmerged and product-wide release unauthorized until root-cause, test and production gate evidence are complete. Keep #610 as Voice 3.0 owner.

## Why the old Master QA ledger was insufficient

The original PR #605 audit found duplicate/competing execution authorities, registry vs actual connector readiness, ambiguity in provider/consumer outcome, historical architecture, potentially overlapping front-end hosts, voice handoff bugs, sequential latency and a large CI estate. Earlier #611 source ledger contained 43 entries but **zero tracked implementation commits, only three regression references, and zero certified synthetic or production closures**; 20 architecture decision entries had QA lane UNMAPPED. Several real regression tests were implemented later but never reconciled against each specific failure. A green CI workflow must **not** close a root cause that was not measured.

This program introduces **two independent ledgers**:
- Original historical evidence source (unaltered): `docs/delivery/master-qa-tranche27-findings-evidence-matrix.json`.
- Controlled full-stack remediation register v2: `docs/delivery/master-qa-remediation-register.v2.json`, one identity per ECO-001–015, DEC-001–020 and P27-01–08, totaling 43.

The source-only preflight `backend/scripts/master_qa_wiring_preflight.py` emits current import/call edge observations and unknown downstream claims. The executable invariant guard `backend/scripts/master_qa_remediation_guard.py` checks no finding disappears, every one has an owner/QA lane/source candidate/repair, and no PASS, legacy retirement or global release is authorized without exact-SHA evidence.

## Scope: all architectural and operational boundaries, not just test names

| Workstream | Authoritative chain to inspect | Specific audit requirement and missing-proof class | Minimum repair/acceptance |
| --- | --- | --- | --- |
| 01. Production topology and cost | DNS/TLS → Vercel frontend, Railway API/web, Redis → Supabase | Identify actual user-facing domain target, deployed SHAs and effective environment-variable **names**. Existing dual frontend projects are not automatically redundant. | 2 verified requests per route class to identified host, trace/health evidence, cost/owner, zero new paid testing service, rollback. |
| 02. Browser, API and voice proxy | Next.js route → `voice-api-proxy.ts` → `public-urls.ts` → FastAPI HTTP/WS | Static source confirms `voiceFastApiBase` falls back to localhost when `FASTAPI_BASE_URL` is absent. Whether live deploy misroutes is **UNKNOWN**; do not assert without runtime config. | Exact backend origin in sanitized deployed config, auth/org/env forwarded, NDJSON/WS reconnect and fallback negative tests; coordinate voice behavior with #610. |
| 03. Canonical intelligence entry | chat/text/voice/agent entry → intent/model policy → intelligence router → one authorized executor | Map competing LIVE/classical/ReAct callers and actual traffic. Phrase-trigger classical fallback is source-confirmed; runtime impact unknown. | Source + deployed trace per ingress; explicit handoff/failure semantics and parity tests before removing any fallback. |
| 04. Latency and context | policy/settings → classification/context → knowledge/memory → model | Serial awaited stages seen in audit; latency root cause not established. | Stage p50/p95, bounded call graph and tenant context isolation, measured improvement, regression on empty and large context. |
| 05. Agent/Play/workflow ownership | agent selection → Play manifest → workflow graph → governed action → outcome | Registration does not prove executability or correct owner; verify nested/delegated agent, approval and workflow entry modes. | Real persisted run/step, approval/denial/revocation, nested Play path, outcome once, causal identity through every hop. |
| 06. Connector catalog and provider readiness | manifest → action registry → execution matrix → availability → OAuth/native/Nango → authorized invoke → provider readback | `chat_tool_bridge.py` enumerates actions from execution matrix; direct tenant readiness at catalog time is not proven. | Absent, disconnected, expired token, wrong scope, correct scope and approved mutating action; independent provider GET, no invented result or unauthorized write. |
| 07. Persistence, outbox and consumer | `workflow_runs` ↔ `runs`/`run_steps`, audit/event → relay → consumer | Dual writes and mirrored projections are intentional; no schema deletion without reader/consumer proof. | Disposable real PostgreSQL, tenant/RLS, exact terminal status, duplicate callback, replay, consumer fanout, cancellation and reconciled mirror. |
| 08. Worker/process recovery | Redis queue → workflow step checkpoint → SQL recovery lease → provider reconciliation | Process crash after external commit is ambiguous; exact-once dispatch requires authoritative readback, not receipt replay. | Independent OS worker death, unique provider resource, SQL owner fencing, readback and finalizer once, safe pause if unknown; staged opt-in in existing Railway only. |
| 09. Models, prompts, memory and knowledge | provider policy/fallback → retrieval → conversation state → response | Multiple memory/knowledge routes, model fallback and stale context need actual callers, tenant policy and error honesty. | No silent downgraded model or false tool claim, evaluated context continuity, proper erasure and authorization, output trace. |
| 10. Voice 3.0 integration (PR #610) | mic/STT/turn arbiter → governed kernel → TTS/PCM/client | P0 early turn, duplicate transcripts, choppy audio, unsolicited narration; specification exists but not shipped. | #610 delivers V0–V7 engineering/regressions; #611 ingests exact SHA and QA30 results. Physical iOS/desktop 20-minute owner acceptance stays separate. |
| 11. Security, billing, tenant and privacy | auth → org/RBAC/RLS → approvals → Stripe/usage → audit | Historical #605 isolated billing is foundation, not all price/webhook/tenant paths. Live telemetry HMAC approval remains in issue #607. | Deny cross-tenant and revoked scopes, subscription/invoice/webhook state reconciliation, privacy consent, no credentials in artifacts. |
| 12. Release engineering and verification | CI workflows → required checks → migration → Railway/Vercel → rollback | 92 source workflows inspected; activation, required check dependencies, minutes/spend and exhaustive dispositions remain unknown. | Audit individual workflows, preserve protected contexts, additive QA00/10/20/30/40/50/90, exact-SHA evidence, no skipped-as-pass or premature disabled gates. |

## Implementation queue: dependency-aware, no premature closure

**R0 — ledger integrity (in PR #611; source-only).** Preserve all 43 audit IDs; assign accountable subsystem and QA lane; identify candidate chain, concrete remediation and negative tests. Emit two CI artifacts: remediation summary + bounded 21-edge source-wiring graph. This does not imply any finding fixed.

**R1 — prove production topology and current active wiring (read-only).** Resolve DEC-013/015/016/017, ECO-008, P27-01: deployment SHAs, actual DNS, backend/voice ingress path, authentic org/environment propagation, runtime config *names* and current billing exposure. Confirm existing Railway's one API replica/Redis and keep the explicit no-new-paid-environment constraint.

**R2 — canonical authority and tools.** Resolve ECO-001/005/011/012/015 and DEC-001–006/018 using actual route→intent→registry→connector→outcome traces. Add direct read, approved write, denial, disconnected/scope mismatch and repeat callbacks. No classical/ReAct/connector deletion before parity and active caller proof.

**R3 — persisted multi-hop proof.** Resolve ECO-010/013/014 and DEC-007/008/012/019 plus P27-02–06: agent→Play→workflow→connector→provider→run/outbox→consumer. Use durable PostgreSQL integration and independent provider source-of-record, not single-process mocks as substitutes. Distinguish CI synthetic pass from real existing-portal HubSpot acceptance.

**R4 — interruption + tenant/privacy.** Prove orphan recovery, revocation, concurrency and kill/restart against SQL and isolated worker process first; then carefully gated existing Railway child-only interruption with API continuity. Keep both flags OFF by default; no new service or mandatory staging.

**R5 — experience and efficiency.** Measured model/context/latency and real voice V0–V7 from PR #610. Must not claim quality solely because CI passed; record p50/p95, audio glitches, completion accuracy and user-rated naturalness.

**R6 — release truth.** Complete 92-workflow operational disposition; QA00–90 orchestrator, exact-head required checks, immutable evidence links and ticket/owner sign-off, migration and rollback. Every unresolved P0 finding blocks the global full-platform certificate unless a named, approved scoped exception exists.

## Invariant for each closed finding

An audit finding becomes **CERTIFIED** only when it has:
1. A confirmed defect/root cause or documented no-change proof with active source/consumer trace and accountable owner.
2. Exact implementing commit and executable regression test ID; positive and negative proof with affected entrypoints and tenant boundaries.
3. Independent persisted consumer/provider result, including denial, replay and failure behavior; no unauthorized side effect.
4. Exact-head successful CI link, explicitly identified deployed SHA and rollback exercise for live certification; never promote synthetic to production.
5. Explicit owner approval, any necessary security/privacy/provider approvals, and source-of-record evidence. Destructive retirement additionally requires consumer migration/parity and rollback.

The validator makes missing core evidence a hard error when anyone sets PASS or `fix_verified=true`. It rejects unauthorized retirement or `global_release_authorized=true` while P0 findings are open. The release ledger currently has **zero certified closures**, not because no code exists but because individual proof has not yet been mapped and approved.

## Known targeted source findings, not guesses

- Source `backend/app/services/unified_turn_classical_fallback.py` retains `_MESSAGE_TOOL_SSE_PATTERNS` and `needs_tool_sse` signal. Classification: **SOURCE_CONFIRMED split path; actual runtime usage UNKNOWN**.
- Source `backend/app/services/chat_tool_bridge.py` builds registered tools via `build_connector_execution_matrix` and `resolve_registry_action`. Classification: **SOURCE_CONFIRMED registration; token scope/provider success UNKNOWN**.
- Subsequent source audit traces `chat_connector_execution_service._verify_plan_executable` to `find_integration_availability(..., action_key=plan.invoke_action)`, `tool_service._hubspot_connector_and_token` to org-scoped connector retrieval and `ensure_hubspot_access_token`, and the execution matrix to registered handler resolution. These are **real connected source edges**, not proof every ingress uses the guard, nor proof a live token/account was accepted or a provider write succeeded. Connector authorization is therefore **PARTIALLY WIRED / END-TO-END UNVERIFIED**, not simply missing.
- Source `apps/web/lib/voice-api-proxy.ts` returns `http://localhost:8000` when `FASTAPI_BASE_URL` is absent, otherwise `backendBaseUrl()`. Classification: **SOURCE_CONFIRMED fallback; deployed misconfiguration UNKNOWN**.
- Source `backend/app/main.py` starts isolated worker supervisor, child process uses `_worker_loop` with in-process worker explicitly suppressed by its opt-in flag. Classification: **SOURCE_CONFIRMED and targeted CI regression; actual Railway child PID test NOT RUN**.
- Source `backend/app/services/execution_outcome.py` has the canonical terminal writer and documented intentional mirror. Classification: **SOURCE_CONFIRMED; no storage retirement approved**.

## Safety, branch ownership and release boundaries

- PR #610 remains draft, code owner for all Voice 3.0 turn/PCM/STT and naturalness changes. PR #611 may inspect and assert ingress wiring but must not silently reimplement or supersede #610's V0–V7.
- No mandatory second HubSpot account, Railway staging service, Redis replica, dedicated database or paid test vendor; existing infrastructure plus disposable CI are the preferred acceptance surfaces. No guarantee of zero usage-related costs.
- PR #611 remains unmerged; production orphan recovery and isolated child flag remain OFF. No actual provider write, production migration, Railway process interruption, OAuth/scopes change, secrets export, DNS cutover or legacy component deletion is authorized by adding this register.
- A green remediation **integrity** check proves the ledger is well-formed, *not* that its 43 findings are repaired. Full-platform acceptance stays blocked until all required per-finding evidence is complete.
