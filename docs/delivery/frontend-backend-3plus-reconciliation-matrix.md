# Gravitre 3.0 Plus — MCP frontend/backend reconciliation matrix
Date: 2026-10-17
Scope: source-code audit of default branch after PR #494. **Not production owner-tenant acceptance.** 
Disposition vocabulary: IMPLEMENTED (code present), CONNECTED (client/API wired), FUNCTIONAL (demonstrated by relevant tests), PARTIAL (specific mapping or evidence missing), MISSING (confirmed absence in inspected surface), NOT VERIFIED (not inspected/tested). Do not conflate source presence with passing E2E.

| Surface | Backend source of truth | Current frontend evidence | Source-level disposition | Gap / next proof |
| --- | --- | --- | --- | --- |
| Connectors | `/api/connectors`, connector availability | `apps/web/app/(app)/connectors/page.tsx`; `apps/web/app/api/connectors/route.ts` | CONNECTED | Existing auth, health, sync, readiness, detail navigation. Verify owner-tenant lifecycle and MCP discovery linkage, not a new page. |
| MCP server/tool administration | `backend/app/routers/mcp_admin.py`: servers CRUD/enable, auth, discover, tools enable | `apps/web/app/(app)/marketplace/capabilities/page.tsx`; `apps/web/lib/api.ts` `mcpAdminApi` | CONNECTED | Existing capability-declared MCP controls incl. creds, discovery and enablement. Assess whether ordinary/manual MCP registrations are visible; no assumption that all admin servers appear (UI filters `portableMcpServers`). |
| Agent effective autonomy/read-write scopes | `backend/app/services/agent_tool_permissions.py`; agent capability/profile APIs | `apps/web/components/agents/agent-autonomy-panel.tsx` | CONNECTED (read presentation) | Shows effective `allowedConnectors` and available actions; does not prove editing of individual tool grants. |
| Agent explicit tool grant CRUD | `backend/app/routers/agent_tool_permissions.py`: GET/PUT `/api/agents/{agent_id}/tool-permissions`; DELETE `/{permission_id}`, require_admin | No `grantToolPermission`, `listToolPermissions`, or `revokeToolPermission` client symbol in indexed default-branch searches; `apps/web/lib/api.ts` inspected | PARTIAL / UNVERIFIED | Conduct exhaustive route/client traversal before claiming missing UI. If absent, add minimal admin-only grant/revoke controls in existing Agent settings and API proxy; verify scopes, expiry, audit, cross-org denials and fail-closed refresh. |
| Workflow run timeline | workflow runs/read and retry APIs | `apps/web/app/(app)/runs/[id]/page.tsx`; `apps/web/components/runs/execution-timeline.tsx` | CONNECTED | Polls in-progress states at 2s; step retry, run approvals, connector-linked `invoke_tool` output are present. No new timeline. |
| MCP approval and durable execution | `backend/app/services/mcp_approval_service.py`; `mcp_tool_executions`; `mcp_tool` approvals | Existing approval queue `apps/web/app/(app)/approvals/page.tsx`, run timeline, activity | PARTIAL / NOT VERIFIED | Trace approval context and MCP execution IDs to current frontend views; verify pending/rejected/approved/consumed/failed/rate_limited and verified provider receipt. Do not display 'completed' for an approval decision alone. |
| MCP rate limits | `backend/app/connectors/rate_limit.py`; migration `supabase/migrations/20261017010000_mcp_server_rate_limit.sql` | Generic failure/error displays in execution UI | NOT VERIFIED | Confirm DB migration applied, error payload and existing UI handling; show rate-limited (not success) using actual backend field; do not invent status. |
| Marketplace partner connectors | `marketplaceApi.listFederatedConnectors` | `apps/web/app/(app)/marketplace/connectors/page.tsx` | CONNECTED | Distinct from MCP admin; avoid duplicating admin UX here. |

## Specific source observations
- `apps/web/app/(app)/marketplace/capabilities/page.tsx` references `mcpAdminApi.listServers/listTools/configureServerAuth/discoverTools/patchServer/patchTool` and filters the rendered server list as `portableMcpServers`. **Question:** whether non-package MCP servers need management elsewhere. Validate current user journey first.
- `apps/web/components/agents/agent-autonomy-panel.tsx` renders `allowedConnectors` and effective permission descriptions. It is a policy visibility surface, not proven granular grant editor.
- `apps/web/components/runs/execution-timeline.tsx` parses generic `invoke_tool` metadata (`action`, `connector_id`, `retry_count`) and links to connector details. MCP execution records have a separate table; the crosswalk has not been demonstrated.
- `backend/app/services/mcp_approval_service.py` binds MCP approval to execution/tool IDs, input hash and target digest and rechecks agent permission before dispatch. Frontend must not collapse proposal approval into verified execution.
- PR #494, `docs/delivery/FRONTEND_BACKEND_3PLUS_RECONCILIATION_PLAN_2026-10-16.md`, explicitly forbids redesign and requires owner-tenant evidence. Release 1 sign-off `docs/delivery/RELEASE1_OWNER_SIGNOFF_2026-10-16.md` cites live MCP security checks but is not UI acceptance.

## Claude implementation handoff — conditional only
1. **First prove a missing interaction** using existing component, API proxy, backend endpoint and test inventory. Prefer **NO CODE CHANGE** where present.
2. P1 investigation: explicit Agent tool grant administration. Record actual frontend path and endpoint request/response; implement only if proven absent, within existing Agent detail/settings patterns. Do not weaken admin checks.
3. P1 investigation: MCP approvals and execution state crosswalk. Capture one authorized MCP read, one write awaiting approval, one legitimate approval, one denied forged approval, and one rate-limited attempt in isolated org. Compare backend `mcp_tool_executions` and approvals with current UI. Change only broken mapping / missing drilldown.
4. P2: ordinary MCP server management discoverability. Since package MCP admin already exists, avoid another MCP page. Link existing surfaces only if journey truly lacks a path.
5. For any correction require unit/contract tests, unauthorized/tenant negative tests, SWR invalidation, light/dark and reduced-motion check, and authenticated owner-tenant screenshots/network evidence. Do not merge/deploy until acceptance gates pass.

## Acceptance still NOT RUN in this audit
- Authenticated browser interactions for the real owner tenant across Connectors, Agent Detail, Approvals, Activity, Runs and Marketplace.
- Database migration verification on production for MCP server rate limit.
- Direct comparison of MCP execution API JSON with rendered UI and cross-route invalidation.
- Deployment SHA parity for current web/backend main.

**Audit-only deliverable. No product frontend/backend changes, feature-flag flips, migrations, or claims of live acceptance.**
