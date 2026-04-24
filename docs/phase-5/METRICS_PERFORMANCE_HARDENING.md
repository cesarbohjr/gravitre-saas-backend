# Metrics Performance Hardening

## Risk identified
- In-memory percentile computation can be slow and memory-heavy for large datasets.
- Full-row scans without proper indexes can degrade performance and increase latency.

## Current state
- Metrics queries filter by `org_id` and `created_at`.
- Percentiles are now computed via SQL `percentile_cont` functions.
- Required indexes already exist on core tables.

## Recommended fix
- Use SQL `percentile_cont` for p95 metrics.
- Ensure indexes exist on:
  - `workflow_runs(org_id, created_at)`
  - `rag_retrieval_logs(org_id, created_at)`
  - `audit_events(org_id, created_at)`
  - `rag_ingest_jobs(org_id, created_at)`

## Implementation details
- Added SQL functions:
  - `metrics_rag_latency_p95(org_id, start_at)`
  - `metrics_exec_duration_p95(org_id, start_at)`
  - `metrics_ingest_chunks_p95(org_id, start_at)`
- Metrics service calls these functions via RPC and no longer computes percentiles in memory.
- Existing indexes:
  - `idx_workflow_runs_org_created`
  - `idx_rag_retrieval_logs_org_created`
  - `idx_audit_events_org_created`
  - `idx_rag_ingest_jobs_org_created`

## Future scaling notes
- Add materialized views for daily aggregates.
- Consider retention-aware partitions to speed time-range filters.
