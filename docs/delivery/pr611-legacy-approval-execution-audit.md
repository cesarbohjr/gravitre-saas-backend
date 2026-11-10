# PR #611 — legacy approval/execution caller audit (incremental)

**Scope:** P0 approval and execution path inventory. **State:** partial, not a 43-finding certification. Reviewed against PR #611 branch through `0b45b869`. Production routes and frontend consumers still require an exhaustive generated route inventory/caller graph.

## Evidence and disposition

| Surface / entry point | Observed owner / caller | Classification | Next gate |
| --- | --- | --- | --- |
| `POST /api/assistant/chat` | `routers/assistant.py` → `AgentIntelligence.execute_task_streaming`; Voice uses `spoken_mode` through the same stream path | **Retain**; unified conversational entry | Verify actual write adapters and identity propagation across text/voice |
| `POST /api/assistant/conversation/{id}/execute` | `routers/assistant.py::execute_conversation_task` dispatches `connector_orchestration`, `connector_action`, other tasks to three services after conversation ownership + HITL checks | **Active separate execution branch; not safe to retire** | Frontend caller inventory, idempotency, authorization parity, verify result persistence before consolidation |
| Frozen connector WRITE confirmation | `unified_turn_pending_live._execute_governed_pending_confirm` → `pending_write_resume.resume_frozen_write_on_confirm` → `chat_connector_execution_service.process_turn` | **Retain pending migration**; real caller | Confirm canonical pending-action/HMAC and durable write claim; regression added for connection authority |
| MCP approval decisions | `workflows.py::approve_run_alias/reject_run_alias` → `mcp_approval_service.decide_mcp_approval` → `MCPClientService.execute_tool` | **Retain**; atomic decision and consumed-at claim | Check handler permissions, engine restart and independently verified provider readback |
| `connector_chat` approval decisions | `workflows.py::approve_run_alias/reject_run_alias` directly reconstruct and execute `chat_connector_execution_service` plan; separate CAS on `reviewed_at` | **Consolidation candidate, not dead code** | Compare binding, approval state transitions, crash recovery and audit integrity with MCP canonical flow |
| `POST /api/workflows/runs/{id}/approve` | Workflow-run approval with role/capability checks and `try_mark_run_running` | **Retain**; distinct workflow run schema | Check shared authority/step replay versus graph runtime |
| `POST /api/workflows/runs/{id}/resume` | In-graph approval calls `execution_engine.resume_workflow_graph` | **Retain**; distinct paused graph state | Verify claim leases, replay and batch compatibility |
| `POST /api/workflows/runs/{id}/approval-batch/decide` | Batch decision service then `resolve_approval_batch_and_resume` | **Retain** until equivalence is proven | Verify per-item decisions and concurrent resumptions |
| `/api/admin/mcp/*` | `routers/mcp_admin.py`; admin configuration/discovery, not itself approval dispatch | **Retain** | Verify tool revocation affects pending approvals |
| `assistant._run_tools` | Defined as legacy pre-run wrapper; default-branch search found declaration in `assistant.py` only | **Possible dead helper** | Exhaustive PR-head code/test/reflection import search before removal |

## Confirmed issue and repair

`pending_write_resume.resume_frozen_write_on_confirm` formerly appended the target integration from persisted `pending_task` to `connected_integrations`. `chat_connector_execution_service.process_turn` uses that argument during cognitive resolution *before* it reloads live connected integrations. A frozen action target is not an authoritative connection record. On PR #611 this injection was removed in commit `371c6fc` and regression coverage requiring an unchanged empty connection list was committed in `0b45b86`. **CI against exact head pending**; do not mark certified.

## Remaining audit work

1. Generate complete PR-head Python symbol references and frontend API route caller inventory, including dynamic/reflection callers, tests, and feature flags. Default-branch GitHub code search is only a preliminary locator, not proof of absence.
2. Verify the `connector_chat` decision path versus MCP and workflow approvals: tenant binding, approval CAS, rejection CAS, idempotency, status persistence, and crash recovery; only then plan migration.
3. Test frozen confirmed-write resumption with disconnected/revoked integration and ensure provider writes are never dispatched.
4. Reconcile each audited route and each confirmed fix against the separately maintained **43-finding master QA register**; do not imply that a route audit closes unrelated findings.
5. Exact-head focused tests, full CI, protected acceptance gates, and independent side-effect readback before removal/merge/deployment.

**Release posture:** PR #611 remains draft/open as applicable, unmerged and undeployed. No legacy route removed by this audit. Avoid PR #610 voice-plan scope changes.


## Follow-up: connector_chat decision claim race (2026-11-09)

The `connector_chat` approve handler conditionally claims `approvals.status = pending AND reviewed_at IS NULL` before provider dispatch. Its reject sibling previously performed an unconditional update after reading the pending row, allowing a stale concurrent reject to overwrite an approved/in-flight decision and clear pending conversation state. PR #611 commit `450d81f` makes rejection use the same atomic predicate, returning HTTP 409 without clearing task state when the claim loses. Commit `3057736` adds regression tests for reject/reject, reject/approve replay and rejected stale claim. **Exact-head CI remains required.**

**Remaining high-risk gap — not yet certified:** the approved `connector_chat` path claims `reviewed_at`, then invokes the provider, then updates approval status. Worker death between these events leaves an unresolved approval and uncertain provider side effects. Existing claim prevents duplicate manual dispatch, but there is not yet evidence of independently verifiable provider readback or a durable recovery machine for this path. Do not auto-retry or retire it as equivalent to MCP; require a durable dispatch/outcome contract and isolated crash/restart acceptance first.


## Connector_chat durable approval-route dispatch record (2026-11-09)

**PR commits:** `0d8e247` implementation; `4878440` focused tests.

`/api/approvals/{id}/approve` previously set `reviewed_at` before invoking the connector, but left `status=pending` and had no durable dispatch/outcome state. It set `status=rejected` for connector execution failures, conflating refusal of consent with uncertain provider-side failure.

The route now atomically claims `status=approved`, `reviewed_at`, reviewer and `context.dispatch.state=claimed` **before** its first connector call. The claim is conditional on `status=pending AND reviewed_at IS NULL`. The provider return is recorded as `verified` only when the execution object explicitly reports `outcome_verified=True`; otherwise it is `reported_success_unverified`, `reported_failure_unverified`, or `uncertain` for exceptions. Outcome data stores bounded entity identity and the frozen argument digest without provider secrets or full result payload. A claimed but outcome-less approval stays approved after abrupt process death; no HTTP retry can dispatch it again. Execution failures must not rewrite human approval as rejection. A failed outcome write returns an error and leaves the dispatch claim non-replayable.

**Evidence boundary:** targeted HTTP regression tests exercise the persisted in-memory approval row, dispatch-before-call ordering, exception uncertainty, and replay refusal using a new request/client. This is **not** a real OS-process death test, production DB concurrency certification, nor independent provider readback. Real protected-acceptance database testing, an isolated provider that records side effects, and process kill/restart with independent readback remain release blockers. Do not claim full end-to-end exactly-once delivery: the claim prevents automatic redispatch but cannot by itself prove that a provider committed the operation.

**Follow-on:** ideally consolidate `connector_chat` onto the existing durable write-invoke ledger and canonical approval/outcome machine once actor/tenant/intent binding and replay parity are proven. Until then, this approval-row claim is an additional fail-closed route-level record, not a replacement for the core write ledger.


## Exact-head CI evidence and remaining external-provider gate (2026-11-09)

- GitHub Actions **run 42755888199** at commit `2262b2b`: `MCP approval crash/restart acceptance (isolated)` **PASSED**. Log: `worker_exit=71, provider_writes=1, durable_claim=true, restart=rejected`.
- The same protected job ran `connector_chat_crash_acceptance.py` against the dedicated `Gravitre MCP Acceptance QA` Supabase tenant and a synthetic local HTTP provider: **PASSED**. Independently recorded local provider `writes=1` after real child-worker `os._exit(71)`, parent observed `approvals.context.dispatch.state=claimed` in the real database, separate restart process obtained HTTP 409 with no second provider write. No real external business record was created.
- Full `Backend (pytest)` at that exact head **FAILED (1 of 17,036 tests)**: `tests/routers/test_approvals_alias.py::test_approvals_reject_alias_closes_chat_connector_write`. Confirmed cause: `_ChatApprovalTable` mock omitted `is_()` for the new conditional CAS predicate. Repaired fake filter semantics and fixture row in commits `bdfe239`, `88fa894`. **Rerun against the latest SHA required.** Do not treat earlier passing acceptance as certification of subsequent SHAs.

### Canonical-ledger parity and external readback still open

The API approval claim and the underlying `write_invoke_idempotency` RPC represent **different fences**. Existing `connector_chat` approval-route evidence proves that the approval record is claimed once before provider dispatch and does not automatically redispatch after crash; it does **not** prove that every connector execution underneath creates a valid `write_invoke_idempotency` claim, finalizes the same logical action key, or reconciles an ambiguous response through provider readback.

Before marking equivalent: confirm a single immutable action identity across approval context, `pending_action_id`, canonical ledger key and provider idempotency token; enforce tenant/actor/connector revocation at dispatch time; verify uncertain and failed results do not resurrect retry authority; require provider-specific lookup by a unique, isolated marker rather than interpreting a successful HTTP response as independently verified business success.

**Live HubSpot/Gmail:** No dedicated test account/record and live provider authorization has been established for this tranche. Do not send email or create/update CRM records on an arbitrary account. A separate controlled test must create a uniquely tagged disposable record (with explicit test-tenant authorization), independently query the provider's read API, assert the exact ID/fields and single write, and clean it up with confirmed readback. Keep this gate open until that evidence exists.


## Canonical ledger parity check — partial (2026-11-09)

**Verified in code:** `backend/app/services/tool_service.py` claims the service-role `write_invoke_idempotency` ledger before lower-level provider execution using `build_write_idempotency_key`, `claim_write_invoke`, `finalize_write_invoke` when `write_invoke_idempotency_enabled` is set, or `claim_approved_autonomous_write` when autonomous authority is set. It can reject replay and preserve uncertain outcomes. **But** the legacy `connector_chat` queue route executes `chat_connector_execution_service.execute_plan`; its separate approval-row CAS is not sufficient evidence that every downstream connector executes the same ledger RPC, with the same logical ID and provider key. An integration-by-integration dispatch trace and the enabled flags in the running environment are necessary.

**Confirmed additional identity gap closed:** the queue route had checked frozen binding at its router boundary, but called `execute_plan` without passing `approved_params`. That bypassed `_execute_plan`'s own `assert_plan_matches_binding` and treated the F1 write compiler's `args_approved` as false. Commit `b74dc532` now hands down the frozen `approval_action_id`, bound tool, action, integration and argument digest in `approved_params`. Commit `9816e9ba` asserts that exact binding reaches the executor. **Exact-head CI required.**

**Not certified:** shared write ledger parity across all connector families, atomic approval+ledger transaction, revocation race protection, independent readback for ambiguous real-provider outcomes and canonical reconciliation. Do not add an independent second ledger claim in the router without proving it is the same logical operation as the lower-level write claim; that would introduce another competing execution identity.

**Real-provider access assessment:** a HubSpot connector is present, but its connected user portal has not been designated as an isolated acceptance sandbox. No destructive or state-changing contact operation was made. Ask for a dedicated HubSpot developer test account/portal or explicitly identified, permitted QA-only portal, with a valid test connector, and verify it is not serving customers before any create/readback/delete test.


## Shared-ledger enforcement implementation (2026-11-09, certification pending)

The caller trace is `workflows.approve_run_alias` → `ChatConnectorExecutionService.execute_plan` → `ToolRegistry.execute_invoke_action` → `tool_service.invoke_tool`. The registry's write action path is the shared tool invoke service, not an independent provider adapter.

The approval route now forwards its immutable, tenant-scoped approval UUID as `_approval_queue_id` inside `approved_params` in addition to the binding fields. `ChatConnectorExecutionService._execute_plan` uses that ID as `ToolContext.turn_id` and sets `write_idempotency_required` for queue-approved writes. `tool_service.invoke_tool` includes this explicit requirement in its durable-ledger predicate even when the general `write_invoke_idempotency_enabled` feature flag is off. For recognized registered writes, this requires `claim_write_invoke_idempotency` before the connector executor; RPC errors or blocked claims fail closed. The frozen approval ID gives a stable replay key and differentiates two separately approved actions with identical arguments. Commits `628cfea`, `a8e435e`, `e1ea00e`, `5fd4211`, `b89c756`, `811a19d`.

**Certification scope:** static code trace and focused regression tests; latest exact-head tests and real QA database invocation evidence have not been certified yet. The existing queue crash harness deliberately fakes the connector execution method, so it only proves the outer approval-row claim, *not* that the lower-level ledger was claimed. A separate matched harness must exercise the actual `ToolRegistry → tool_service` path with a controlled provider adapter; then verify both `approvals.context.dispatch` and `write_invoke_idempotency` persistence and post-crash replay under concurrent decisions and revocation.

**External HubSpot readback:** the available connected HubSpot portal was not established as a dedicated QA account. No HubSpot write, readback, or cleanup was performed. The live-provider acceptance gate is **blocked by test portal designation**, not by synthetic acceptance.


## QA provider-account isolation blocker and ledger acceptance extension (2026-11-09)

**Provider isolation audit:** `scripts/provision-isolated-hubspot-slack-connectors.py` clones HubSpot and Slack OAuth tokens from the *operator* integration into an isolated Gravitre organization. Although this isolates Gravitre org rows, the underlying HubSpot account/portal is shared. It is **not** an independent HubSpot sandbox and must not be used for destructive/live CRM-write acceptance. The connected HubSpot account in ChatGPT is likewise not verified as a disposable QA portal. No real HubSpot record was created, read, or deleted.

**New canonical-ledger acceptance:** `backend/scripts/connector_chat_ledger_crash_acceptance.py` (commit `abca44b`) exercises the real PostgreSQL `claim_write_invoke_idempotency` RPC with `ToolContext` using a stable synthetic approval ID, a synthetic provider readback counter, abrupt worker process exit, fresh restart process, and independent ledger-row inspection. CI now runs it under the protected acceptance environment (commit `02efc69`). This is distinct from the approval-row death test and deliberately does not claim full real-provider adapter execution. The QA database has the necessary ledger claim/finalize RPCs and zero existing QA ledger rows at inspection time. Results pending exact-head Actions log.

**Required to close remaining live-provider gate:** a *separate* HubSpot test portal, demonstrably authorized for destructive disposable records, with a scoped test credential or OAuth install, exact portal ID checked at runtime, creation of a UUID-tagged contact, an independent GET/search readback of ID/fields and count, then deletion plus independent confirmation of absence. Preserve approval and ledger evidence and do not grant retries on ambiguous provider responses. Gate must stay open until there is actual provider-side evidence.


## Queue approval canonical ledger wiring and real-provider eligibility (2026-11-09)

At PR #611 head, `workflows.approve_run_alias` passes `approved_params` with `_approval_queue_id` and immutable tool/action/integration/arguments binding to `ChatConnectorExecutionService.execute_plan`. Its `_execute_plan` builds `ToolContext.turn_id` from the approval ID and forces `write_idempotency_required=True` for queued writes. That same context is passed to `registry.execute_invoke_action`; `tool_service` invokes `build_write_idempotency_key`, `claim_write_invoke` and `finalize_write_invoke` for write tools with the forced flag. An unavailable ledger must block rather than implicitly allow a provider write. Additional unit regressions in commit `8956d77` check tenant/argument identity separation and fail-closed ledger claim errors.

**Evidence boundary:** these are static caller-path findings and pure ledger-key/RPC tests. They do not prove the complete live queue route (including provider-specific adapter, provider consent and independent readback) was executed with a ledger claim. The existing synthetic `connector_chat` process-death test substitutes a fake execution service and therefore exercises the approval-row fence, not the actual underlying write-invoke RPC. A separate actual-adapter integration acceptance test remains required.

**Provider eligibility check:** The currently connected HubSpot account reported incomplete portal onboarding; it has not been confirmed as a disposable QA portal and must not be used for destructive/write certification without the user's explicit scoped authorization. No external CRM write, email send, or cleanup was attempted in this audit. Completion of the real-provider gate requires a designated QA provider account and explicit authorization for uniquely tagged disposable record creation/readback/deletion.


## Connected HubSpot QA contact readback — 2026-11-10

With explicit authorization, the connected HubSpot portal `343328749` created one disposable `CONTACT` record through its connected CRM action: ID `288809521110`, first name `Gravitre`, last name `PR611 QA Test`, email `support@gravitre.app`. HubSpot's create response reported `created=1, failed=0`. A separate CRM fetch by ID returned the exact properties and `archived=false`. A second, independent exact-email CRM search returned `total=1`, including the same ID. Record URL: https://app.hubspot.com/contacts/343328749/record/0-1/288809521110 .

**Certification limitation:** These calls were made through the connected HubSpot integration, **not** through the Gravitre `connector_chat` API and its canonical ledger. They validate provider write/read capability and one matching contact at readback, not full application-side exactly-once execution. The connected HubSpot CRM tool offers create/update but **no contact delete**, so cleanup has **not** been performed or verified. Authorized operator must delete the QA contact in HubSpot and verify absence through independent search; until then, the cleanup and full real-provider gates remain open. Avoid submitting this contact for marketing or triggering follow-up automation.
