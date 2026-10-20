# MCP frontend/backend integration audit — Gravitre 3.0 Plus
Date: 2026-10-16
Method: static source-code inspection on main; **not** owner-tenant browser acceptance.

## Verdict
**Existing functionality is substantial; no new top-level page is justified.** The review found MCP administration and governance already implemented under Marketplace → Capabilities, agent policy controls, and generic execution timeline. No unsupported claim that these are missing. Two narrow observability/discoverability gaps and one unproven cross-surface contract require targeted follow-up.

## Route and contract matrix
| Surface | Frontend evidence | Backend source | Classification | Follow-up |
|---|---|---|---|---|
| MCP administration | `apps/web/app/(app)/marketplace/capabilities/page.tsx` lines 232–238, 598–716, 2057–2245; `apps/web/lib/api.ts` lines 1542–1599 | `backend/app/routers/mcp_admin.py` `/api/admin/mcp/servers`, `/tools`, `/servers/{id}/discover`, PATCH server/tool/auth | **IMPLEMENTED / API WIRED** | Confirm in owner tenant |
| MCP transport/auth & discovery | Capabilities page calls `prepareMcp`, `discoverTools`, `configureServerAuth`, `patchServer`, `patchTool`. Credential input masked; server and tool activation separated | `mcp_admin.py`, `mcp_client_service.py` endpoint transport restrictions | **IMPLEMENTED / API WIRED** | Live failure-state inspection, permission roles |
| MCP tier & approval label | Capabilities page lists `capability_tier`, `requires_approval`, `risk_level`; server-level confirm prompt | `MCPAdminTool` DTO in `apps/web/lib/api.ts` lines 1555–1565, backend approval binding | **IMPLEMENTED** | Test mismatch/consumed approval states |
| Agent autonomy | `apps/web/components/agents/agent-autonomy-panel.tsx` (canonical policy + `allowedToolPatterns`, fail-closed approval label) | agent identity and `/api/agents/{id}/capabilities`, `/api/capabilities` | **IMPLEMENTED / API WIRED** | Prove effective MCP per-tool intersection with policy in live tenant; no MCP-specific tool grant assumed |
| Execution timeline | `apps/web/app/(app)/runs/[id]/page.tsx` mounts `ExecutionTimeline`; `apps/web/components/runs/execution-timeline.tsx` recognizes `awaiting_approval`, renders evidence/connector actions | `mcp_client_service.py` execution and audit; runs API | **GENERIC TIMELINE IMPLEMENTED** | Trace MCP execution ID → run step and provider receipt; not yet proven |
| Rate-limit display | `MCPAdminTool` and `MCPAdminServer` DTOs contain no quota remaining/reset/429 indicators; MCP review list does not show bucket state | `backend/app/connectors/rate_limit.py` `consume_mcp_server_token` RPC; migration `20261017010000_mcp_server_rate_limit.sql` | **OBSERVABILITY GAP CONFIRMED IN MCP ADMIN DTO** | Before UI work, decide if operational quota telemetry should be exposed and add safe read-only backend summary |
| Independently registered servers | `portableMcpServers = (...).filter(server => ...)` in Capabilities page, line ~270; portable MCP review iterates filtered subset | Backend MCP admin can register/list servers beyond portable package preparation | **DISCOVERABILITY GAP IN THIS SURFACE** | Check other admin/UI surfaces before adding a list/tab. Reuse same MCP API and existing page |
| Approval state consistency | `apps/web/app/(app)/approvals/page.tsx` uses live `/api/approvals` and history; timeline uses awaiting-approval state | MCP approval binding + approval execution | **PARTLY VERIFIED (SEPARATE WIRED SURFACES)** | Prove cross-view state invalidation on decision/consumption with real test |
  
## Safety and product requirements
1. **No broad redesign or duplicate MCP dashboard.** MCP review has real enable/disable controls and admin guard already.
2. Do not display the internal RPC name, secret material, or fabricated quota numbers. An MCP rate-limit banner should depend on a documented and authorized backend response.
3. Do not equate `tool.enabled` with effective permission. Effective access is the intersection of org policy, user/agent role, MCP server state, tool tier and approval requirements.
4. Do not imply external execution succeeded because a local run transitioned to completed; show provider receipt / trace evidence where supported.
5. Never weaken tenant filters, SSH/private-network restrictions, RLS, rate limiting, or human approval.

## Minimal targeted implementation sequence (not yet approved as verified missing behavior)
**MCP-01 [P1]** Inspect all existing connector/MCP surfaces for non-portable servers. If no discoverable route exists, add an *existing-page* tab or section listing admin-owned MCP servers with tool counts/state; use `mcpAdminApi.listServers/listTools`. Test role-denied, empty, disabled, and error states.

**MCP-02 [P1]** Trace live MCP execution and approval events from `MCPClientService` to `runsApi` / `ExecutionTimeline`. If the trace fails to map, fix the adapter rather than creating an activity page. Test completed, rate-limited, blocked, and awaiting-approval modes.

**MCP-03 [P2]** Only if actionable for customers, expose a read-only, org-scoped quota/error summary. First add a safe backend contract and tests. Do not expose raw rows or internal configuration.

**MCP-04 [P1 acceptance]** Owner-tenant live path: verify server discovery/enable → tool grant → read execution → write approval → execution/receipt → run timeline, and negative states. Record network evidence without credentials. Static source inspection does not satisfy this.

## Current release decision
**Audit complete; implementation pending targeted contract verification.** No application code changes in this audit. Existing MCP review is functional in source and not to be rebuilt. Link to production MCP execution/SSRF proof: https://github.com/cesarbohjr/gravitre-saas-backend/actions/runs/38994473914 (read-only execution; not owner-browser UI acceptance).
