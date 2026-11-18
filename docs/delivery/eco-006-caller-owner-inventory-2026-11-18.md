# ECO-006 — canonical execution ownership and caller/consumer inventory
**As-of source:** PR #611 branch `feat/master-qa-tranche27-orchestration`, 2026-11-18.

**Status:** SOURCE-TRACED / RUNTIME ACTIVITY AND RETIREMENT NOT CERTIFIED. This is a scoped graph from the real repository, not an assertion that every named route is deployed or receiving traffic. ECO-006 remains open in the original 43-finding register.

## Source-confirmed ownership chain

```
signed Chat HTTP (routers/assistant.py)
  -> ChatConnectorExecutionService (approval/revocation + pending state)
  -> ToolRegistry.execute_invoke_action (one action)
  -> tool_service.invoke_tool (canonical tool/authority/provider dispatch)
  -> write_invoke_idempotency (PostgreSQL claim + recovery bind + finalize)
  -> provider adapter -> independent receipt + outcome finalizer/outbox

Agent / ReAct (operators/react_engine.py, operators/agent_jobs.py)
  -> tool_service.invoke_tool [direct call sites exist]
  -> same canonical write fence, but complete runtime caller parity remains unproven

Workflow / Play (workers/workflow_worker.py -> workflows/execute.py
  -> workflows/handlers.py; plays/prospecting_authorized_writes.py)
  -> tool_service.invoke_tool [actual direct sources]
  -> same canonical provider/write owner; independent event/outbox readback pending

Voice PR #610 -> PR #611 governed dispatch contract [integration candidate]
  -> full device/runtime path NOT certified; do not reassign Voice implementation

Context and memory reads:
IntelligenceRouter -> ContextAssembler -> UnifiedRetrievalService
  -> org_context_service + agent_memory_service + RAG
Other direct UnifiedRetrievalService callers:
  routers/rag.py, routers/rag_enhanced.py, routers/search.py,
  workflows/handlers.py, operators/agent_intelligence.py,
  services/intelligence_orchestrator.py, services/assistant_tools.py,
  services/agent_knowledge_assignment_service.py
These are source call sites; they are not proof of active traffic or permission parity.
```

## Classification and retirement controls

| Component / caller | Observed source role | Current classification | Retirement |
| --- | --- | --- | --- |
| `tool_service.invoke_tool` | Shared canonical executor, authority and provider adapter | SOURCE-CONFIRMED OWNER | **PROHIBITED** |
| `tool_registry.execute_invoke_action` | Delegates to `invoke_tool`; provides Chat tool observation | ACTIVE-CANDIDATE ADAPTER | Keep; no independent writer proven |
| `chat_connector_execution_service` | Signs/claims Chat pending actions and selects exact tenant connector before provider dispatch | ACTIVE-CANDIDATE ORCHESTRATOR | Keep until signed-route and historical state parity |
| `workflows/handlers.py`, `workflows/execute.py` | Workflow step execution through governed tool service | ACTIVE-CANDIDATE CALLER | Keep until replay/approval/outbox parity |
| `operators/react_engine.py`, `operators/agent_jobs.py` | Direct tool-service call sites | ACTIVE-CANDIDATE CALLERS | Confirm runtime branches, not just static imports |
| `plays/prospecting_authorized_writes.py` | Direct invoke with separate Play approval wrapper | ACTIVE-CANDIDATE CALLER | Verify exact approval scope + same canonical ledger before retirement |
| `services/extension_bridge_service.py`, `services/compensation_service.py` | Additional tool-service call sites | UNKNOWN RUNTIME ACTIVITY | Inventory external triggers and persisted state |
| `services/sealed_read_execution.py` | Canonical compiled read wrapper with preflight | SOURCE-CONFIRMED READ OWNER | **PROHIBITED** without equivalent sealed read |
| `chat_tool_bridge.py` + `connector_execution_matrix.py` | Canonical dynamic tool catalog with registry-keyed cache | SOURCE-CONFIRMED DISCOVERY OWNER | Keep |
| `chat_tool_visibility.py::_dynamic_registry_keys` | Extra `lru_cache` over already registry-keyed canonical discovery | REDUNDANT CACHING LAYER; **REMOVED** | Removed cache only, not tool visibility logic |
| `ContextAssembler` + `UnifiedRetrievalService` | Canonical routed context bundle | SOURCE-CONFIRMED CONTEXT OWNER | Keep; multiple direct consumers need parity |
| `OrgContextService`, `agent_memory_service` | Existing tenant-scoped context/memory stores | SOURCE-CONFIRMED DATA ADAPTERS | No replacement cache until p50/p95 baseline |
| Voice ownership | PR #610 repair, PR #611 cross-surface integration | EXTERNAL OWNER / CONTRACT PENDING | No Voice algorithm changes here |

**Do not interpret ACTIVE-CANDIDATE as live/deployed.** To classify active/inactive, correlate deployed revision, route/worker logs, persisted historical caller IDs, feature flags and domain/outbox events. Do not delete a router, workflow or fallback on a source-only finding.

## Engineering repairs included

- ECO-005: Resolve approved Chat write provider account **before** consuming the pending Chat claim. Reject unambiguously disconnected/disabled/revoked explicit account rows; preserve provider-side OAuth, scopes and write-authority checks. See `backend/tests/services/test_chat_connector_execution.py`.
- ECO-006: Removed the competing zero-argument `lru_cache` in `chat_tool_visibility.py`. `build_dynamic_chat_tool_specs` already uses `registry_keyed_cache` tied to the actual registry fingerprint. Tool visibility can now observe one-for-one action swaps without process restart. See `backend/tests/services/test_chat_tool_visibility.py`.
- ECO-006: Named tool calls and exact-action calls now use the same connector read cache scope. The registry requires a context-bound caller and account and caches only when the provider response reports that account. Regression tests exercise both entry points with synthetic provider responses and check that a mismatched account cannot seed the cache. Deployed caller traces and revocation under live provider credentials remain unverified.

## Still unmet for ECO-005 and ECO-006

1. Actual **consented tenant-owned** provider read/write receipt plus independently verified account/scopes and missing-account branch. A synthetic local receiver is only development proof.
2. Full signed Chat / Agent / Voice / Play / Canvas active caller trace, historical claim/outbox migration, no-network negative acceptance and exact-SHA verification.
3. Determine active/inactive/unknown from real deployment and feature flag traces; retire only an unambiguously redundant implementation **after** equivalent routing, persistence, privacy, owner and rollback proof.
4. Deployment/rollback proof and owner acceptance at release certification. No merging/deployment or irreversible retirement in this source-only batch.

This document is an implementation inventory and not one of the twelve final QA gate certifications.
