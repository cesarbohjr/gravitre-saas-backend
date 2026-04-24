# FE-11 — Audit Timeline for Runs

**Authority:** Gravitre_Brand_Alignment_Spec.md, BE-12 (docs/phase-1/BE-12_AUDIT_QUERY_API.md), FE-10 run viewer.

## Scope

- Add an **Audit Timeline** panel to the run viewer (`/runs/[id]`).
- Fetch audit events via BE-12 API (`resource_type=workflow_run`, `resource_id=run_id`, `action_prefix=workflow.dry_run.`).
- Render events in reverse-chronological order with human-readable action labels.
- Cursor-based "Load more" pagination.

## Non-goals

- No new backend code.
- No direct FastAPI calls from browser (same-origin proxy only).
- No new libraries.
- No audit UI on other routes (e.g. workflows list).

## Deliverables

| Item | Description |
|------|-------------|
| `app/api/audit/route.ts` | GET proxy to FastAPI /api/audit; forwards Authorization and query params. 500 if FASTAPI_BASE_URL missing; 503 on fetch failure. |
| `lib/audit-api.ts` | `fetchAuditEvents(token, resource_type, resource_id, options)`; `getActionLabel(action)`; `AUDIT_ACTION_LABELS`. |
| `app/runs/[id]/page.tsx` | Audit section beneath step detail; timeline with status-colored left border; empty/error/loading states; Load more. |
| `lib/backend-proxy.ts` | Added `proxyAuditToBackend(request, queryString)` for audit. |

## UX

- Timeline items: Card/list with `border-border`; left border color by action type (started=primary, completed=success, failed=destructive, step=warning, default=muted).
- Empty: "No audit events available."
- Error: safe message only; no stack traces.
- Load more: disabled during fetch; appends older events.
