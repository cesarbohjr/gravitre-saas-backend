# ECO-001 — bounded orchestration authority and release evidence

Evidence evaluated 2026-11-13 against PR #611 source commit `74d678f667ee8de4adfc44167367566fbc2d5803`. **Status: isolated acceptance demonstrated; full finding NOT CERTIFIED; release-blocking.** This is an evidence register, not a deployment receipt, production-provider proof, or architectural retirement authorization.

## 1. Source-to-runtime decision and execution ownership

| Ingress | Authenticated source caller | Bounded decision / tool owner | Governed effect |
| --- | --- | --- | --- |
| Text chat stream | `backend/app/routers/assistant.py` (chat route ~1311; stream delegate ~914–959) | `AgentIntelligence.execute_task_streaming` (~1780), `ReActEngine.run_streaming` (~5967) with routing control; `ChatIntelligenceFacade` delegates enrichment helpers to `IntelligenceRouter`, NOT a second execution core | ReAct permission/approval/write gates; not every branch has a persisted action |
| Pending connector action | `assistant.py` `POST /conversation/{conversation_id}/execute` (~2044–2145), signed identity and org/conversation ownership | `ChatConnectorExecutionService.execute_confirmed_task` (~1847) selected only when pending type `connector_action` | Approval binding, `_claim_write_before_invoke`, `tool_registry.execute_invoke_action`, durable `write_invoke_idempotency` claim/finalize and outcome bookkeeping |
| Pending multi-step orchestration | Same authenticated confirmation endpoint, pending type `connector_orchestration` | `ChatOrchestrationService.execute_confirmed_task` (~892), which delegates individual connector steps to the connector service (~1841–1850) | Per-step approval, scoped `write_authority` guard, delegated connector write fence |
| Agent/workflow worker | `backend/app/workers/workflow_worker.py` `process_workflow_run_job` (~25) | `execute_workflow_steps` (~71) -> registered `invoke_tool` handler -> `tool_service.invoke_tool` | Autonomous approval scope, PostgreSQL idempotency claim/finalize, canonical terminal-outcome pathway |
| General pending conversational execution | `assistant.py` other pending types (~2139–2145) | `ConversationalExecutionService` | Source-traced as a distinct pending type; not independently proven by joined connector-action receiver tests |

The authoritative decision for *which pending task* executes is the authenticated route's typed dispatch and approval policy; actual write authority remains at the invocation/claim boundary. `backend/app/orchestration_registry.py` documents `IntelligenceRouter` as a wrapper, and `ChatIntelligenceFacade` (~19–50) reuses helpers; neither is an independent authorization bypass by that fact alone. The original ECO-001 claim of active competing writers remains **unverified**. No component may be retired or its traffic switched based on this source trace.

The trace is source-backed and partially executable (actual mounted Chat confirmation and worker are in the joined acceptance). It is **not** a complete production ingress inventory: live text ReAct writes, voice, Plays, canvas, alternate pending conversational tasks, real provider OAuth, flags and deployment identity still need independent live/nonproduction acceptance appropriate to each lane. Thus `source_to_runtime_trace=false` remains correct for the full 43-finding closure test.

## 2. Positive and negative acceptance evidence

Exact source SHA `74d678f667ee8de4adfc44167367566fbc2d5803`:
- Full CI: https://github.com/cesarbohjr/gravitre-saas-backend/actions/runs/43385836750 — green. Consolidated `backend/scripts/eco001_master_acceptance.py`: **77 passed, 0 skipped**, including mounted signed Chat ingress, decision handoff, approval binding, cancellation, PostgreSQL ledger, independent Chat/Agent receiver and agent Play step acceptance.
- Full backend pytest: **17,106 passed, 44 skipped**, 14 subtests passed. The 44 skips are unrelated to the fail-closed 77-case ECO-001 acceptance and must not be represented as zero skips for the whole backend.
- Master QA P0: https://github.com/cesarbohjr/gravitre-saas-backend/actions/runs/43385836687 — **320 passed** synthetic/runtime-guard tests and **54 passed** disposable PostgreSQL guard tests.
- Independent receiver: https://github.com/cesarbohjr/gravitre-saas-backend/actions/runs/43385836556 — **9** initial and **34** PostgreSQL/independent-process cases passed; acceptance checks include denied dispatch, cross-tenant denial, completed replay, and lost acknowledgement, requiring zero unauthorized/duplicate writes.
- Positive matched Chat/Agent: `backend/tests/db/test_eco001_joined_chat_http_receiver_pg.py` and `test_eco001_joined_agent_worker_pg_receiver.py` execute actual mounted signed HTTP / actual worker, tool registry/handler and isolated receiver process, then independently query PostgreSQL `write_invoke_idempotency` terminal completed rows. Provider is **isolated test receiver, not real HubSpot**, and ancillary transports are adapted.
- Negative controls: `tests/routers/test_eco001_chat_execute_ingress.py` denies unowned conversations, missing/other user's signed token and denied approval without dispatch; `test_eco001_decision_handoff_runtime.py` ensures single-consumption selection and no invented provider call on error; `test_eco001_inflight_chat_cancellation.py` covers cancelled waiter, before-dispatch stop, and observed failed in-flight outcome; independent receiver explicitly audits denied, cross-tenant, replay and lost-ack cases.

Do not assert comprehensive independently persisted outcomes for every live ingress or real third-party provider: these tests control external credentials and several storage/notification edges. Pass evidence is **bounded acceptance**, not complete ECO-001 root-cause closure.

## 3. Evidence mapping and rollback gap

All **20/20** workflows for source SHA passed, including Supabase migration/billing browser checkout (https://github.com/cesarbohjr/gravitre-saas-backend/actions/runs/43385836611). None indicates that this SHA was deployed to production. Existing main/production must remain untouched. Source changes to this evidence file/register will create a *new commit* requiring fresh exact-head CI before that new head can be certified.

- Exact-SHA source CI, targeted positive/negative and isolated process SQL readback: **satisfied for the tested scope**.
- Active traffic decision authority, full cross-surface and real provider readback: **not fully demonstrated**.
- Production release/rollback: **not run**. Before release, authorize a controlled staging/production verification, record actual deployment SHA and aliases, feature flag state, fail-closed rollback trigger and independently observed post-rollback persisted-outcome continuity.
- Architectural retirement / deletion: **not authorized**. Preserve all existing paths until confirmed caller and behavioral parity is proved.
- ECO-001 register `fix_verified`, `live_status`, `rollback_verified`, `owner_approval`, `release_blocking` and global release gate remain unchanged until verified.

## 4. Explicit owner sign-off required

No GitHub review approval was present on PR #611 when checked. The responsible owner must review the source-to-caller map, the tested-vs-untested scope, the negative and independent readback evidence, and the release/rollback evidence. The owner must then explicitly approve the closure/release gates in the PR (or reject them with concrete missing evidence). **A user request to complete certification is not by itself an owner-approval event**, nor can a tooling agent self-approve it. Until that action and missing runtime/release evidence are present, ECO-001 remains P0 OPEN and PR #611/stacked #615 must not be merged/deployed as ECO-001-certified.


## Controlled runtime gate — environment discovery and execution hold (2026-11-13)

This section reports **actual connected-environment inspection**, not synthetic outcomes.

- Connected Vercel project `gravitre-saas-backend` (framework `nextjs`): preview deployment `dpl_B2TsnSDmrS3EdvoWPQpHmc73yUY4`, state READY, branch `feat/master-qa-tranche27-orchestration`, commit `a8c270cc621dd95472b5f26468bf69404ba55e00`, target preview (no production target). Its deployment identity proves a Next.js preview exists; it does **not** prove the PR's FastAPI execution engine is deployed. The preview could not be inspected through the public unauthenticated fetch, and no authenticated browser/provider path was executed.
- Connected Railway project `spirited-communication`, environment `production`, backend service `gravitre-saas-backend`: latest SUCCESS deployment `78fb8af7-2c90-4a4f-9a34-180398ad20fb` at main commit `557be844f191767ea51c9f1d1d4958e5b046ca53`. No staged changes were reported. **This is not PR #611's executable runtime**; do not use its traffic to certify this branch. The Redis deployment is separate and unchanged.
- Connected Supabase project `gravitre-acceptance` (ref `aadnwmjzrmbvadszroqt`): status ACTIVE_HEALTHY. Read-only SQL verified `public.write_invoke_idempotency` and `public.workflow_runs` exist, but `public.execution_outcomes` does not; status-grouped query against `public.write_invoke_idempotency` yielded **no rows**. No provider, tenant, or customer data was read, and no SQL mutation was executed. The empty ledger cannot substantiate a Chat/Agent live write, replay, denial, or terminal provider readback.
- Vercel's deployment flag listing returned an empty array. It does **not** prove backend runtime flags; the actual FastAPI `GET /health` exposes key relevant flags and `git_sha` when a suitable instance exists.

**New executable acceptance entrypoint:** `backend/scripts/eco001_deployed_ingress_preflight.py` and manually dispatched `.github/workflows/eco-001-deployed-ingress.yml`. This is a read-only *real deployed backend* gate, not a simulated suite: verify HTTPS, FastAPI-specific health JSON, nonproduction environment, exact `git_sha`, database connectivity and anonymous 401/403 for an owned conversation-state GET. It cannot be marked passed on the Next.js frontend preview or the older Railway production deployment. It will fail closed if target identity and SHA cannot be verified. No execution or external provider mutation is included. **The gate has not yet been run**, because no suitable PR #611 FastAPI nonproduction backend URL and exact-sha deployment have been confirmed.

The next owner-authorized step is to provide/provision the **isolated FastAPI nonproduction backend** running the reviewed PR SHA and connected to the acceptance database/isolated providers. Confirm it is isolated from customer data and live credentials. Run the deployed preflight, then perform *separate* approved Chat, Agent, Voice, Play and Canvas functional acceptance with real authorization/approval/cancellation/replay and independently persisted receiver outcomes. Record reversible deployment identity and actual restoration proof. Request human review when that evidence exists. Until then: runtime acceptance **BLOCKED_UNDEPLOYED_BACKEND**, owner review **REQUESTED_NOT_APPROVED**, ECO-001 **OPEN**. No production change, traffic switch, merge or third-party write was made.
