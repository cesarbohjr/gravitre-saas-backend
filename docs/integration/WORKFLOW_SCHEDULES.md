# Workflow schedule / cron worker (STA-47 + SaaS calendar)

Cron-based and one-time workflow triggers: poll due schedules, start runs via the merged executor, advance `next_run_at`.

## Flow

```text
Cron (GitHub Actions or in-process loop)
  → POST /api/internal/workflows/schedules/dispatch-due
    → list workflow_schedules where enabled and next_run_at <= now
    → idempotency check (schedule_window in run parameters)
    → _execute_workflow_with_context (trigger_type=schedule)
    → update last_run_at + next_run_at (recurring) OR disable (one-shot)
```

## Schedule types

| `schedule_type` | Behavior |
|-----------------|----------|
| `recurring` | Standard 5-field cron (or `@hourly` / `@daily` / …) evaluated in `timezone` (IANA). Optional `ends_at` stops further fires. |
| `once` | Single fire at `run_at`. Stored cron sentinel `@once`. After successful/idempotent dispatch, schedule is **disabled** and `next_run_at` cleared. |

Additional columns: `name`, `timezone` (default `UTC`), `run_at`, `ends_at`.

## Admin API

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/workflows/{id}/schedules` | List schedules (camelCase + snake_case fields) |
| `POST` | `/api/workflows/{id}/schedules` | Create — body may include `scheduleType`, `runAt`, `timezone`, `cronExpression` / `cron_expression`, `name`, `endsAt`, `enabled` |
| `PATCH` | `/api/workflows/schedules/{id}` | Update cron / once / enabled / timezone |
| `DELETE` | `/api/workflows/schedules/{id}` | Delete schedule |
| `GET` | `/api/schedules?from&to&kinds&workflow_id` | Org calendar aggregation (read-only) |
| `POST` | `/api/workflows/schedules/dispatch` | Org-scoped manual dispatch (admin) |

## UI

- Org calendar: `/schedules` — **New schedule**, edit/delete/reschedule (reschedule → one-time `runAt`)
- Per-workflow: `/workflows/{id}/schedules`
- Builder settings: **Schedule this workflow** opens the shared editor

## Chat / AI

Assistant tool `schedules_list` (`assistant_schedules_list` in ToolRegistry) wraps `list_scheduled_items` for the current month (or “next week” / “today” from the query). Prompt guidance: **call the tool — do not invent calendar entries.** FAST mode escalates to standard when the user asks about schedules.

Meson Schedules page context includes upcoming occurrence summaries.

## Agent delete guard

`DELETE /api/agents/{id}` returns **409** `AGENT_IN_WORKFLOW_SEQUENCE` when the agent appears in an active workflow definition (`agent_id` / `next_agent_id` / council `agent_ids`). Schedules themselves remain deletable.

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

Each fire window uses `parameters.schedule_window = "{schedule_id}:{next_run_at}"`. If a schedule-triggered run already exists for that window, the worker skips execution and still advances (or disables one-shot).

## Operator cron (GitHub Actions)

`.github/workflows/workflow-schedules.yml` runs every 5 minutes against production.

## Code

- `backend/app/workflows/cron.py` — next fire + occurrence expand (timezone / once)
- `backend/app/services/workflow_schedule_service.py` — dispatch worker
- `backend/app/services/schedules_aggregation_service.py` — calendar aggregation
- `backend/app/services/assistant_tools.py` — `tool_schedules_list`
- `apps/web/components/schedules/schedule-editor-dialog.tsx` — shared create/edit UI
- Migration: `supabase/migrations/20260801060750_workflow_schedules_once_timezone.sql`

## Related

- [KNOWLEDGE_SYNC.md](./KNOWLEDGE_SYNC.md) — same internal-cron pattern (STA-45)
- [WORKFLOW_BUILDER.md](./WORKFLOW_BUILDER.md)
