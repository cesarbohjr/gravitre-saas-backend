# Phase 6: Retention + Rollups (Implementation)

## Risks
- Large audit/log tables slow metrics and increase storage costs.
- Without rollups, dashboard metrics can degrade as data grows.
- Retention deletes must be explicit and safe.

## Current State
- Rollup tables and SQL functions are now implemented in `supabase/migrations/20250220000001_phase6_rollups.sql`.
- Retention purge helpers exist in `supabase/migrations/20250220000004_phase6_retention.sql`.
- Metrics can read from rollups when `METRICS_ROLLUP_ENABLED=true`.

## Implementation Details
### Rollup Tables
- `audit_events_daily` (per org + day + action)
- `workflow_runs_daily` (per org + day + run_type + status)
- `connector_sends_daily` (per org + day + connector_type + status)
- `rag_retrieval_daily` (per org + day totals + latency p95 + avg result count)

### Rollup Functions
- `rollup_audit_events_daily(start_at, end_at)`
- `rollup_workflow_runs_daily(start_at, end_at)`
- `rollup_connector_sends_daily(start_at, end_at)`
- `rollup_rag_retrieval_daily(start_at, end_at)`
- `rollup_all_daily(start_at, end_at)` — orchestrates all rollups

### Retention Functions
- `retention_purge(p_cutoff, p_org_id DEFAULT NULL)` — scoped by org (global only with NULL)
- `purge_rag_retrieval_logs_before(cutoff, p_org_id DEFAULT NULL)` — optional retrieval log purge
  - Global purge requires `--global` in the runner (explicit only)

## Scheduling (Required)
Choose one of:

### Option A: External Runner (recommended for beta)
- Rollups:
  - `python -m backend.scripts.rollup_daily --days 1`
- Retention purge (explicit, org-scoped by default):
  - `python -m backend.scripts.retention_purge --cutoff-days 180 --org-id <org_uuid> --include-rag`
  - Global purge: add `--global` (mutually exclusive with `--org-id`)

### Option B: Supabase pg_cron
Schedule SQL to call `rollup_all_daily` and optional purge functions.

## Metrics Read Path
- Metrics endpoints use rollup tables when `METRICS_ROLLUP_ENABLED=true`.
- Raw tables remain the fallback when rollups are disabled or empty.

## Future Notes
- Add rollups for ingestion jobs if needed.
- Add per-org retention windows for regulated tenants.
# Phase 6: Retention + Rollups (Implementation)

## Risk
- Raw audit + retrieval logs grow without bounds, slowing metrics queries and increasing storage costs.
- Daily metrics queries repeatedly scan large tables without rollups.

## Implementation Summary
- Added daily rollup tables and SQL functions for audit events, workflow runs, connector sends, and RAG retrievals.
- Added a retention helper for audit events.
- Added a runner script to execute rollups (and optional retention purge).
- Metrics endpoints can read from rollups when enabled.

## Implementation Details
- Migration: `supabase/migrations/20250220000001_phase6_rollups.sql`
  - Tables: `audit_events_daily`, `workflow_runs_daily`, `connector_sends_daily`, `rag_retrieval_daily`
  - Functions: `rollup_audit_events_daily`, `rollup_workflow_runs_daily`, `rollup_connector_sends_daily`, `rollup_rag_retrieval_daily`, `rollup_all_daily`
- Migration: `supabase/migrations/20250220000004_phase6_retention.sql`
  - Function: `purge_audit_events_before(cutoff)`
- Runner: `backend/scripts/rollup_daily.py`
  - Example: `python backend/scripts/rollup_daily.py --days 1`
  - Optional purge: `python backend/scripts/rollup_daily.py --days 1 --purge-days 180`
- Metrics toggle: `METRICS_ROLLUP_ENABLED=true`

## Scheduling Options
- Supabase/pg_cron: schedule `rollup_all_daily(start_at, end_at)` for the previous day.
- External runner: use cron/systemd to call `backend/scripts/rollup_daily.py`.

## Future Scaling Notes
- Move to partitioned tables + rollups for larger datasets.
- Add ingestion rollups if ingest volumes grow.
- Consider materialized views if rollup windows require frequent recomputation.
