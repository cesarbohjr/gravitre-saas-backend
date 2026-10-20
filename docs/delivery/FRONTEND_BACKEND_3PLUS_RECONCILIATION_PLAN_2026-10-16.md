# Gravitre 3.0 Plus — Backend-to-Frontend Reconciliation Implementation Plan
Date: 2026-10-16
Status: **PLAN / NOT IMPLEMENTATION**
Scope: Existing production routes/components only; no broad redesign or new navigation.

## Definition of done
For each feature, show (1) backend contract and source of truth, (2) existing UI component, (3) authorization and state mapping, (4) captured successful and negative owner-tenant evidence, (5) automated regression covering transitions. Do not describe a component's presence as proof of functional acceptance. Never use fixture screenshots as production acceptance.

## Inventory already confirmed in source
| Capability | Current frontend entry point | Evidence / initial disposition |
| --- | --- | --- |
| Approval queue and history | `apps/web/app/(app)/approvals/page.tsx` | Present, reads `/api/approvals`, status=history, calls `approvalsApi`; **verify states and cross-route invalidation** |
| HITL governance configuration | `apps/web/app/(app)/settings/approvals/page.tsx` | Present, reads `/api/settings/hitl-policies`; **verify effective policy** |
| Agent autonomy | `apps/web/components/agents/agent-autonomy-panel.tsx` | Present, reads agent identity, capabilities and policies; **verify fail-closed labels** |
| Activity and evidence | `apps/web/app/(app)/activity/page.tsx` | Present, live SWR-backed outcome/work-object inspector; **verify event completeness** |
| AI Workspace activity | `apps/web/app/(app)/ai/_components/live-activity-rail.tsx` | Present, SWR-backed runs and assistant activity; **verify event ordering** |
| Run execution timeline | `apps/web/components/runs/execution-timeline.tsx` | Present; **verify event semantics and links** |
| Workflow execution | `apps/web/app/(app)/workflows/[id]/page.tsx` | Present, workflow API, run/cancel; **verify canceled/rejected state** |
| Sources lifecycle | `apps/web/app/(app)/sources/[id]/page.tsx` | Present, sync, history, source delete; **verify memory-retrieval revocation state** |
| Connectors marketplace | `apps/web/app/(app)/marketplace/connectors/page.tsx` | Present, federated connector API; **verify MCP discovery/permissions in existing catalog** |
| Intelligence / attribution | `apps/web/components/intelligence/brain/intelligence-brain.tsx`, `apps/web/components/intelligence/impact/latest-outcome-card.tsx` | Present, flow model and attribution; **verify measured-vs-estimated labelling** |

## Implementation workstream A — MCP tool state and safety
Backend source: `backend/app/services/mcp_client_service.py`, `backend/app/connectors/rate_limit.py`, SQL migration `supabase/migrations/20261017010000_mcp_server_rate_limit.sql`.
1. Trace existing connector detail, Agent tool permissions and Runs/Activity components to canonical server/tool execution API contracts.
2. Compare read vs write tier, approval-required status, disabled/disconnected state, server rate limiting, last execution, errors and retries. Record exact route/API/value for every field.
3. **Only if absent**: add small inline status/help/detail affordance to an existing component. Never expose internal credentials or unapproved execution controls.
4. Test: unauthorized cross-org tool is invisible, denied write cannot dispatch, over-limit shows rate-limited (not completed), valid read execution resolves; cross-route status updates consistently.

## Workstream B — Source and memory provenance
Backend: `backend/app/services/memory_source_liveness.py`, `backend/app/services/source_lifecycle.py`, `backend/app/routers/sources.py`.
1. Trace source disconnect, deactivation and delete responses through Source Detail, Intelligence and AI Workspace retrieval attribution.
2. Specify **distinct** `connected`, `disconnected`, `excluded from retrieval`, `purge pending`, `deleted` labels, but use only statuses actually supported by backend; do not invent a `purged` state.
3. Ensure stale cached UI responses are invalidated after revocation and no inaccessible source snippet is shown.
4. Test: synthetic canary before and after revoke in isolated org, verify presentation and return paths, including negative direct-link behavior.

## Workstream C — Approval state convergence
Backend: `backend/app/services/approval_record_service.py` and MCP approval execution contract.
1. Trace queue → decision → agent/run detail → AI Workspace activity and policy view.
2. Check canonical transitions: pending, approved, rejected, consumed, expired, canceled (only if supported). Mark retry/outcome states explicitly.
3. Update only missing SWR/cache invalidations or status presentation; no optimistic `completed` before provider receipt.
4. Test: forged/mismatched approval denied; legitimate approval updates all mounted surfaces without stale action buttons; tenant isolation preserved.

## Workstream D — Intelligence, sentiment/context and ROI proof
Backend: `backend/app/services/outcome_attribution_service.py`, source and agent activity endpoints.
1. Inventory exact context/sentiment and outcomes fields consumed by existing Intelligence/Activity UI and whether confidence and provenance exist.
2. Explicitly tag measured vs estimated outcomes using authoritative backend fields; never manufacture time saved or ROI.
3. Verify empty state/insufficient data. Reuse existing Intelligence cards/inspector only.
4. Test: attribution graph/evidence links are resolvable, source revocation removes citations, missing values show unknown rather than zero.

## Workstream E — Owner-tenant acceptance and rollout
1. Build a single per-route matrix: Dashboard, AI Workspace, Agents, Agent Detail, Approvals, Activity, Connectors, Sources, Workflows, Intelligence and Settings.
2. For each, capture real owner-tenant account network response and action flow, not only fixture screenshots/CI. No real customer data in CI logs or evidence.
3. Gate release on web lint, typecheck/build, backend contract tests, role and tenant tests, existing production smoke. Billing and customer onboarding are separate launch gates.
4. PR sequencing: A audit + focused correction; B focused correction; C focused correction; D focused correction; E acceptance evidence. If an audit finds no gap, record **NO CODE CHANGE**.
5. Require each implementation PR to include screenshot before/after if visual impact, API evidence, test results, rollback note, and accessible reduced-motion/dark/light behavior where applicable.
6. Production activation only after owner-tenant acceptance; no automatic feature-flag activation, credential changes, or billing bypass.

## First executable actions
- Produce `docs/delivery/frontend-backend-3plus-reconciliation-matrix.md` with each route, API, source file, status, proof link, and missing evidence.
- Audit MCP source contract first; file minimal issues only for verified missing data or interaction.
- Audit Sources revoke state second; compare against passing chat/voice revocation E2E.
- Validate approvals concurrency and intelligence attribution as separate PRs.
- Preserve the product's current 3.0 Plus design language, spacing, components, information architecture and copy tone.
