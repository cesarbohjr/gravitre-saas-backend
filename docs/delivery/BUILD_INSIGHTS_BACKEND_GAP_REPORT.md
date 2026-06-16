# Gravitre BUILD/ACTIVITY/INSIGHTS Backend Audit — 2026-06-07

## Executive summary

Most backend surfaces for the nine audited pages **already exist**. Critical user-visible bugs were caused by **frontend hardcoded demo data**, **SWR fallback payloads masking API failures**, and a **billing entitlement misconfiguration** that blocked audit log reads on the Node plan.

---

## Gap report

### WORKFLOWS

| Item | Status |
|------|--------|
| Run execution engine | **EXISTS** — `workflow_runs`, `/api/workflows/execute`, worker dispatch |
| Success rate real data | **YES** — per-workflow from list API; footer now from `GET /api/workflows/stats` |
| Run count real data | **YES** — was **FAKE** in UI footer (`98%`, `4,690`); fixed |
| Workflow status transitions | **Working** — pause/resume/execute paths in `workflows.py` |
| Create from Goal | **Wired** — `POST /api/workflows/from-goal` |
| Build with Meson | **Wired** — `POST /api/meson/interpret` |
| Stats (Total/Active/Paused/Running) | **Real** — from workflow defs + runs |

### TRAINING HUB

| Item | Status |
|------|--------|
| Dataset CRUD | **YES** — `/api/training/datasets` |
| Training job execution | **YES** — `/api/training/jobs` |
| Instructions CRUD | **YES** — `/api/training/instructions` |
| Load starter examples | **Wired** — backend seed path exists |
| All zeros | **Real empty state** when org has no datasets/jobs (not a backend bug) |

### CONNECTORS

| Item | Status |
|------|--------|
| OAuth flow | **YES** — per-connector start/callback routes |
| Health monitoring | **YES** — `connection_health.py`, integration health snapshots |
| Throughput/latency real data | **Partial** — metrics from health snapshots when connected |
| Auto-reconnect | **Partial** — token refresh paths exist; no global 30s monitor in `main.py` yet |
| 0 connected | **Correct** when OAuth incomplete |

### DATA LANDSCAPE

| Item | Status |
|------|--------|
| Data source CRUD | **YES** — `/api/sources` |
| Schema discovery | **YES** — background discover + `schema_cache` |
| Record/table counts | **Real** when sources connected |
| Empty visualization | **Correct empty state** for orgs with no sources |

### EXECUTION TIMELINE

| Item | Status |
|------|--------|
| "Connection: error" cause | **SWR error** on `/api/runs` while `fallbackData` showed fake runs |
| Real-time updates | **Polling** — 10s refresh (no WebSocket required) |
| Auto-retry endpoint | **EXISTS** — `POST /api/runs/{id}/retry` |
| Run detail on click | **Wired** — `GET /api/runs/{id}` |

### APPROVALS

| Item | Status |
|------|--------|
| Approval queue endpoint | **EXISTS** — `/api/approvals` |
| Approve action | **Wired** |
| Reject action | **Wired** (STA-173 regression covered) |
| 0 pending | **Legitimate empty state** when no runs await approval |

### DASHBOARD (System Intelligence)

| Item | Status |
|------|--------|
| Metrics real data | **YES** from `/api/metrics/*` — UI was masking with fallbacks |
| 1,247 / 98.7% / 1.8M / 142ms | **Were FAKE** — removed from frontend fallbacks |
| Meson Insights | **Now derived** — `GET /api/metrics/insights` from runs + connectors |
| Live refresh | **YES** — 15s poll when Live enabled |
| Export | **Wired** — metrics export route |

### AUDIT TRAIL

| Item | Status |
|------|--------|
| "Failed to load" root cause | **403** — Node plan had `audit_logs: false` in `DEFAULT_PLANS` |
| Audit events written | **YES** — `write_audit_event` across workflows, connectors, tools |
| Export CSV/JSON | **Wired** — `/api/audit/export` |
| Filters | **YES** — action, entity_type, date range |

---

## Fixes applied

### P0 — Audit Trail

- **`backend/app/billing/service.py`**: Node plan `audit_logs: false` → `"basic"` so `require_feature` passes.
- **`apps/web/app/audit/page.tsx`**: clearer error copy for upgrade vs generic fetch failure.

### P0 — Execution Timeline

- **`apps/web/app/runs/page.tsx`**: removed demo `fallbackRuns` and SWR `fallbackData`; empty list on failure; softer connection banner with 10s poll.

### P0 — Fake workflow stats

- **`backend/app/routers/workflows.py`**: `GET /api/workflows/stats` (weekly runs, success rate from `workflow_runs`).
- **`apps/web/app/workflows/page.tsx`**: footer reads live stats; shows `—` when no runs.

### P0 — Fake dashboard metrics

- **`apps/web/app/metrics/page.tsx`**: removed hardcoded overview/insights/chart fallbacks; zeros + API-driven insights.
- **`backend/app/routers/metrics.py`**: `GET /api/metrics/insights` from operational data.

---

## Fake data eliminated

| Location | Was | Now |
|----------|-----|-----|
| `workflows/page.tsx` footer | `98%`, `4690 runs` | `/api/workflows/stats` |
| `metrics/page.tsx` overview | 1247 runs, 98.7%, 1.8M, 142ms | API or zeros |
| `metrics/page.tsx` insights | Hardcoded Meson copy | `/api/metrics/insights` |
| `metrics/page.tsx` charts | Demo time series | API series or empty |
| `runs/page.tsx` | 7 demo runs on error | Empty + poll |

---

## Database tables (existing — no new migration required for P0)

- `audit_logs` — migration `20260424_gravitre_frontend_contract_schema.sql`
- `workflow_runs`, `workflow_defs`
- `training_datasets`, `training_examples`, `training_jobs`, `training_instructions`
- `connectors`, integration health snapshots
- `data_sources` / sources registry

Optional future tables from the audit spec (`connector_health_snapshots`, `metric_snapshots`) can be added when background monitors land.

---

## Endpoints created/enhanced

- `GET /api/workflows/stats` — org workflow + weekly run aggregates
- `GET /api/metrics/insights` — operational insights (no hardcoded copy)

---

## Tests

Run the full BUILD/INSIGHTS regression bundle:

```bash
cd backend
python -m pytest \
  tests/test_audit_trail.py \
  tests/test_workflow_runs.py \
  tests/test_training.py \
  tests/test_connector_health.py \
  tests/test_metrics.py \
  tests/test_approvals.py \
  tests/routers/test_build_insights_endpoints.py \
  tests/metrics/test_weekly_throughput.py \
  tests/connectors/test_health_monitor.py \
  -q
```

**41 passed** (audit spec coverage):

| File | Tests |
|------|-------|
| `test_audit_trail.py` | list, action/entity/date filters, CSV/JSON export, entitlement 403, write_audit_event |
| `test_workflow_runs.py` | list runs, retry, workflow stats (zeros + calculated) |
| `test_training.py` | datasets list/create, records upload, job queue, instructions CRUD |
| `test_connector_health.py` | health check, skip non-OAuth, monitor persist, scheduler gate |
| `test_metrics.py` | overview, insights (no hardcoded copy), runs series, weekly throughput |
| `test_approvals.py` | queue, approve, reject, optional reject reason |

Shared helpers: `tests/support/build_insights.py`

---

## Manual actions

```
┌──────────────────────────────────────────┐
│ MANUAL ACTION REQUIRED                   │
│ Platform: Production deploy              │
│ Action: Deploy backend + frontend        │
│ Why: Billing + stats + UI fake-data fixes│
└──────────────────────────────────────────┘
```

No `supabase db push` required for these P0 fixes — schema already present.

---

## Audit events already written (sample)

`write_audit_event` is invoked for: workflow create/update/run, connector connect/disconnect, tool invoke, agent tasks, training jobs, approvals, settings changes, and vertical pack installs.
