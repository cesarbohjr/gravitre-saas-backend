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
