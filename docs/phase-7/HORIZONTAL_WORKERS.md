# Phase 7: Horizontal Worker Strategy (Ingestion)

## Current Architectural Limitation
- Background ingestion assumes a single worker loop.
- Stuck jobs cannot be safely reclaimed by another worker.

## Target Architecture
- Multiple workers can claim jobs safely without external queues.
- Stale jobs are reclaimed after a visibility timeout.
- Workers emit heartbeats while processing long-running jobs.

## Minimal Implementation Plan
- Add `worker_id` and `heartbeat_at` to `rag_ingest_jobs`.
- Update `claim_rag_ingest_job` RPC:
  - claim queued jobs
  - or reclaim stale running jobs
  - assign `worker_id` and set `heartbeat_at`
- Add `heartbeat_rag_ingest_job` RPC.
- Update worker loop to pass a worker id and visibility timeout.

## Required Migrations
- `supabase/migrations/20250220000007_phase7_worker_strategy.sql`

## Integration Changes
- `backend/app/rag/worker.py`:
  - claims with `worker_id` and timeout
  - sends heartbeats during ingestion
- `backend/scripts/ingest_worker.py`:
  - adds `--worker-id` and `--visibility-timeout`

## Risks
- Visibility timeout too short may cause duplicate work.
- Heartbeats require periodic calls during embedding work.

## Future Scaling Notes
- Add metrics for stale reclaim count and heartbeat latency.
- Add per-org concurrency caps if needed.
