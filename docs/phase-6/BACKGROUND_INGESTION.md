# Phase 6: Background Ingestion Jobs

## Risks
- Synchronous ingestion blocks API and can time out.
- Large embeddings increase response latency.
- Failed ingestion can leave partial documents.

## Current State
- POST `/api/rag/ingest` enqueues a job (status `queued`).
- Worker processes jobs and updates status to `running` → `completed`/`failed`.
- Job payload is stored in `rag_ingest_jobs.request_payload` and cleared on completion.

## Implementation Details
- Claim: `claim_rag_ingest_job()` (DB function) atomically marks a job `running`.
- Worker: `python -m backend.scripts.ingest_worker`
- Processing path:
  1. Validate payload (chunks vs text)
  2. Chunk text (if needed)
  3. Insert chunks + embeddings
  4. Activate document version (atomic RPC)
  5. Finalize job and clear payload

## API Contract
- `POST /api/rag/ingest` returns `ingest_id` + `status: queued` (no breaking response shape).
- `GET /api/rag/ingest/{id}` reports status and completion fields.

## Future Notes
- Add worker concurrency controls.
- Add retry policies for transient failures.
# Phase 6: Background Ingestion Jobs

## Risk
- Synchronous ingestion blocks request threads and is fragile under load.
- Failures during embedding should not block API responsiveness.

## Implementation Summary
- `/api/rag/ingest` now enqueues a job and returns `status=queued`.
- A worker claims queued jobs, performs chunking + embedding, and finalizes the job.
- Job payloads are stored in `rag_ingest_jobs.request_payload` and cleared on completion.

## Implementation Details
- Migration: `supabase/migrations/20250220000003_phase6_ingest_queue.sql`
  - Adds `request_payload` and `updated_at` to `rag_ingest_jobs`
  - Adds `claim_rag_ingest_job()` RPC for safe job claiming
- API enqueue: `backend/app/routers/rag_admin.py`
  - Returns `ingest_id` and `status=queued`
- Worker: `backend/app/rag/worker.py`
  - Run: `python -m app.rag.worker` (from `backend/`)

## Notes
- API contract kept stable by returning the same keys with `status=queued`.
- Worker uses service role key; no new dependencies.

## Future Scaling Notes
- Add retry/backoff with max attempts.
- Move payloads to dedicated queue table if job volume grows.
