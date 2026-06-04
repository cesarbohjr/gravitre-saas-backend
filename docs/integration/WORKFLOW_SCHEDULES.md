# Workflow schedule / cron worker (STA-47)

Cron-based workflow triggers: poll due schedules, start runs via the merged executor, advance `next_run_at`.

## Flow

```text
Cron (GitHub Actions or in-process loop)
  → POST /api/internal/workflows/schedules/dispatch-due
    → list workflow_schedules where enabled and next_run_at <= now
    → idempotency check (schedule_window in run parameters)
    → _execute_workflow_with_context (trigger_type=schedule)
    → update last_run_at + next_run_at (APScheduler cron parsing)
```

## Admin API (existing)

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/workflows/{id}/schedules` | List schedules with `nextRunAt`, `lastRunAt` |
| POST | `/api/workflows/{id}/schedules` | Create schedule (computes initial `nextRunAt`) |
| PATCH | `/api/workflows/schedules/{id}` | Update cron / enabled |
| POST | `/api/workflows/schedules/dispatch` | Org-scoped manual dispatch (admin) |

## Internal cron

```http
POST /api/internal/workflows/schedules/dispatch-due
X-Internal-Secret: {INTERNAL_API_SECRET}
```

## Env

```env
INTERNAL_API_SECRET=...
WORKFLOW_SCHEDULE_INTERVAL_SECONDS=60
```

Set `WORKFLOW_SCHEDULE_INTERVAL_SECONDS=0` to disable the in-process loop (use GitHub Actions / Railway cron only).

## Idempotency

Each fire window uses `parameters.schedule_window = "{schedule_id}:{next_run_at}"`. If a schedule-triggered run already exists for that window, the worker skips execution and still advances `next_run_at`.

## Operator cron (GitHub Actions)

`.github/workflows/workflow-schedules.yml` runs every 5 minutes against production.

## Code

- `backend/app/workflows/cron.py` — `compute_next_run_at` (APScheduler)
- `backend/app/services/workflow_schedule_service.py` — dispatch worker
- `backend/app/workflows/schedule_scheduler.py` — in-process loop
- `backend/app/routers/workflow_schedules_internal.py` — internal endpoint

## Related

- [KNOWLEDGE_SYNC.md](./KNOWLEDGE_SYNC.md) — same internal-cron pattern (STA-45)
- [WORKFLOW_BUILDER.md](./WORKFLOW_BUILDER.md)
