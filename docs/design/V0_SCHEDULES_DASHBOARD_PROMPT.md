# v0 prompt — Schedules dashboard polish (`/schedules`)

Paste into v0 on branch `v0/cesarbohorquezjr-4251-c5e410cc` (synced from `main`). **UI polish only** — data layer is live; extend existing components under `apps/web/app/schedules/`.

---

## What's already shipped (do not rebuild)

- **Backend:** `GET /api/schedules` — org-scoped aggregation (workflow cron + runs + training jobs)
- **Hook:** `useSchedules()` in `apps/web/lib/use-schedules.ts` — calls unified API, legacy fan-out fallback, sample data when empty
- **Page shell:** `apps/web/app/schedules/page.tsx` with `SchedulesView`
- **Views:** calendar, gantt, list tabs in `_components/` (`schedules-view.tsx`, `calendar-view.tsx`, `gantt-view.tsx`, `list-view.tsx`, `detail-sheet.tsx`)
- **Sidebar:** Schedules → `/schedules` under ACTIVITY

---

## Your task — wire live data + filters

Enhance the existing Schedules dashboard so it uses **real API params** instead of only client-side filtering.

### 1. Pass hook params from the page

Lift filter state to `page.tsx` (or a small wrapper) and call:

```typescript
useSchedules({
  workflowId,   // optional
  from,         // ISO — calendar month start
  to,           // ISO — calendar month end
  kinds,        // ("workflow" | "task" | "job")[] | undefined = all
})
```

When filters change, the hook refetches automatically (SWR key includes params).

### 2. Kind + workflow filters

- Kind chips in `SchedulesView` should set `kinds` on `useSchedules`, not only filter in-memory.
- Optional workflow select → set `workflowId` (populate from distinct `workflowId` on items or `workflowsApi.list()`).

### 3. Calendar month navigation

- Month prev/next should set `from` / `to` to that month's bounds and pass through to `useSchedules`.
- Prefer server `occurrences[]` on workflow items when present; fall back to `buildOccurrences()` / `expandCron()` only when missing.

### 4. Sample data banner

- Keep the existing `isSample` banner on the page when no live items exist.
- Remove sample fallback once the org has at least one real schedule/run/job (already handled in hook).

### 5. Deep links (verify / fix)

| Kind | Target |
|------|--------|
| workflow | `/workflows/{workflowId}/schedules` |
| task | `/runs/{id}` |
| job | `/training` |

### 6. UX polish

- Loading skeletons while `isLoading`
- Error state with retry (use `WorkSectionErrorCard` from `@/components/gravitre/*`)
- Mobile: collapse filters into a sheet
- Match Gravitre admin aesthetic (dark, chart-1/2/3 kind colors already in `KIND_STYLES`)

---

## Constraints

- **Do not** reimplement N+1 fetching in the page — use `useSchedules()` only.
- **Do not** add Next.js API routes — `/api/*` rewrites to Railway.
- **Do not** change backend contracts unless types need narrowing in `apps/web/types/api.ts`.

---

## Types reference (`ScheduledItem`)

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
progress?: number
occurrences?: string[]   // server-projected cron fires in window
```

---

## Acceptance checklist

- [ ] Changing kind chips refetches via `useSchedules({ kinds })`
- [ ] Calendar month changes set `from`/`to` and list/calendar update
- [ ] Live org data replaces sample banner when items exist
- [ ] Detail sheet + row links navigate correctly
- [ ] No console errors on `/schedules` when logged in with org selected
