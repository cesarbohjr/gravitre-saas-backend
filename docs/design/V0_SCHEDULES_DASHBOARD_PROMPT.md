# v0 prompt — Schedules dashboard (`/schedules`)

Paste into v0 on branch `v0/cesarbohorquezjr-4251-c5e410cc` (synced from `main`). **UI only** — do not reimplement data fetching; wire to existing hooks/API.

---

## Context

Gravitre needs a **Schedules dashboard** at `/schedules` that replaces the current stub page. Backend aggregation is **live**:

- `GET /api/schedules` — org-scoped, returns `{ items: ScheduledItem[] }`
- Client: `useSchedules()` in `apps/web/lib/use-schedules.ts` (falls back to legacy fan-out only if endpoint missing)
- Types: `ScheduledItem`, `SchedulesListParams` in `apps/web/types/api.ts`
- Stub page: `apps/web/app/schedules/page.tsx` (simple list — replace entirely)

Query params the hook supports (pass through to `useSchedules({ ... })`):

| Param | Type | Purpose |
|-------|------|---------|
| `workflowId` | string | Filter to one workflow |
| `from`, `to` | ISO string | Cron projection window |
| `kinds` | `("workflow"\|"task"\|"job")[]` | Filter item types |

Each `ScheduledItem`:

```typescript
kind: "workflow" | "task" | "job"
id: string
title: string
subtitle?: string
status: "enabled" | "disabled" | "running" | "queued" | "completed" | "failed" | "scheduled"
cron?: string
nextRunAt?: string
lastRunAt?: string
startedAt?: string
completedAt?: string
workflowId?: string
progress?: number        // 0-100 for training jobs
occurrences?: string[]   // server-projected cron fires in window
```

Sidebar link **Schedules → `/schedules`** already exists under ACTIVITY.

---

## Design direction

Match Gravitre admin console aesthetic (dark, duotone Phosphor icons, violet/emerald accents) — same family as `/runs`, `/goals`, `/admin/intelligence`.

### Layout (single page, no new routes required)

1. **Page header** — title “Schedules”, subtitle explaining unified cron + runs + training jobs; primary actions: Refresh, optional “New schedule” → `/workflows` (or workflow picker modal linking to `/workflows/[id]/schedules`).

2. **Filter bar**
   - Kind chips: All | Workflows | Task runs | Training jobs → sets `kinds` on `useSchedules`
   - Optional workflow select (populate from `workflowsApi.list()` or distinct `workflowId` on items)
   - Date range control for calendar month → sets `from` / `to` (defaults handled by API)

3. **Main content — two complementary views (tabs or split)**

   **A. Timeline / list (default)**  
   - Group items by day using `nextRunAt` || `startedAt` || `lastRunAt`
   - Row shows: kind badge, title, subtitle (cron or status), status pill, next/last time
   - Deep links:
     - workflow → `/workflows/{workflowId}/schedules`
     - task → `/runs/{id}`
     - job → `/training`

   **B. Calendar month grid (optional second tab)**  
   - Plot `occurrences[]` for workflow items + one-off task/job timestamps
   - Click day → filter list to that day
   - If client-side cron expansion needed for disabled rows, keep `cron` field and use existing cron helper pattern — prefer server `occurrences` when present

4. **Empty states** — no items vs filtered-empty; link to Automations and Training hub.

5. **Loading / error** — use existing `Skeleton`, `WorkSectionErrorCard`, `EmptyState` from `@/components/gravitre/*`.

---

## Constraints

- **Use `useSchedules()`** — do not call `workflowsApi.listSchedules` per workflow from the page.
- **Do not add Next.js API routes** — `/api/*` rewrites to Railway already.
- **Do not change** `apps/web/lib/api.ts` contract unless adding typed helpers; `schedulesApi.list()` already exists.
- Remove the dashed “v0 stub” banner when shipping the real UI.
- Keep page as `"use client"` with `AppShell`.

---

## Acceptance checklist

- [ ] `/schedules` renders without console errors when logged in with org selected
- [ ] Filters update `useSchedules` params and list refreshes
- [ ] Workflow / task / job rows link to correct detail pages
- [ ] Calendar or timeline shows projected cron occurrences when API returns `occurrences`
- [ ] Mobile: filters collapse into sheet; list remains readable
- [ ] Matches sidebar active state for `/schedules`

---

## Out of scope (backend already done)

- Creating/editing cron expressions (stay on `/workflows/[id]/schedules`)
- New API endpoints
- Client-side N+1 aggregation (legacy fallback only)
