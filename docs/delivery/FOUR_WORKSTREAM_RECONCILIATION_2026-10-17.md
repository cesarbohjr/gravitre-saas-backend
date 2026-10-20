# 3.0 Plus frontend–backend reconciliation: targeted changes and remaining gates
Date: 2026-10-17
Scope: Existing UI only. No new control center, activity center, approvals interface or intelligence dashboard.

## 1. MCP execution — partially accepted
**Existing UI:** `apps/web/app/(app)/marketplace/capabilities/page.tsx` uses `mcpAdminApi.listServers/listTools/discoverTools/patchServer/patchTool`; `apps/web/components/agents/agent-autonomy-panel.tsx` reads capabilities and tool patterns; `apps/web/components/runs/execution-timeline.tsx` presents execution and awaiting-approval states.
**Backend:** `backend/app/routers/mcp_admin.py` and `backend/app/services/mcp_client_service.py` enforce server/tool state and approvals. Live isolated-org run 39014000610 passed authenticated listing, discovery, read-only provider execution, disable cascade, SSRF/stdio rejection and forged-approval denial. Frontend server disable now revalidates both server and tool lists (PR #497).
**Not yet accepted:** No safe per-server remaining-quota/reset contract in admin DTO; do not invent counters. Actual authenticated browser status transitions and MCP run-step provider receipt correlation are not established by API-only smoke. These require separate test/evidence before code changes.

## 2. Source and memory revocation — correction implemented
**Backend truth:** `backend/app/routers/sources.py::delete_source_route` soft-deletes `rag_sources` via `deleted_at`, invalidates retrieval caches and relies on DB trigger to deactivate source documents. This is **not evidence of physical permanent purge**. `backend/app/services/memory_source_liveness.py` excludes memories/observations from revoked/disconnected/deleted connectors even before purge completes.
**Correction:** Existing source detail removal dialog now explicitly distinguishes removal from active retrieval from permanent data erasure. Source deletion invalidates cached Sources and Intelligence data. No invented purge-complete badge.
**Further work:** Backend should expose separate authorized lifecycle/provenance fields before UI claims `excluded` or `permanently deleted`. Connector disconnect is distinct from source soft delete; no equivalence is implied.

## 3. Governance consistency — correction implemented
**Existing UI:** Approvals uses `/api/approvals` and `/api/approvals?status=history`; the queue already checks pending before enabling decisions. Agent autonomy and timeline show separate policy/run views.
**Correction:** Approval refresh now also revalidates mounted run, agent and session SWR caches after approve/reject and already-decided conflicts. This reduces stale actionable state across existing views without optimistic success or new UI.
**Further work:** Verify exact run/approval ID correlation, expiry/consumption and provider receipt in an authenticated browser with two actors. Backend must remain the authority for rejection of stale approvals; cache invalidation is not authorization.

## 4. Intelligence and ROI — existing provenance support confirmed
**Existing UI:** `apps/web/lib/intelligence/performance-display.ts` distinguishes `measured`, `estimate`, `operational`, `insufficient_data`, `not_configured`. `apps/web/components/intelligence/impact/certainty.tsx` visually distinguishes measured, estimated and no evidence. `apps/web/app/(app)/intelligence/page.tsx` reads page context, outcome attribution and trust summaries. `backend/app/services/outcome_attribution_service.py` records measurement windows and `measured_at`.
**Regression guard:** tests assert estimated vs measured vs unknown ROI remain distinguishable.
**Not yet accepted:** End-to-end mapping of context/sentiment/usage provenance, attribution confidence, and measured-vs-estimated figures from the actual owner tenant; avoid any blanket claim that every metric is verified.

## Acceptance requirements
- Web unit tests, lint/typecheck/build, backend CI; no merge on failing checks.
- Authenticated owner-tenant browser checks of Connectors/Agents/Runs, Sources/Intelligence and Approvals/AI Workspace. Use isolated fixtures and separate roles; no customer data mutations.
- Document exact request/response and evidence IDs for every state transition.
- Do not activate quota telemetry or permanent-deletion labels without backend-supported, tenant-scoped contract.
