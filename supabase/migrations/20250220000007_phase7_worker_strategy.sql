-- Phase 7: Horizontal worker strategy for ingestion jobs

ALTER TABLE public.rag_ingest_jobs
  ADD COLUMN IF NOT EXISTS worker_id text,
  ADD COLUMN IF NOT EXISTS heartbeat_at timestamptz;

CREATE INDEX IF NOT EXISTS idx_rag_ingest_jobs_status_heartbeat
  ON public.rag_ingest_jobs(status, heartbeat_at);

CREATE OR REPLACE FUNCTION public.claim_rag_ingest_job(
  p_worker_id text,
  p_visibility_timeout_seconds int DEFAULT 300
)
RETURNS TABLE (
  id uuid,
  org_id uuid,
  source_id uuid,
  external_id text,
  created_by uuid,
  environment text,
  worker_id text,
  request_payload jsonb
)
LANGUAGE plpgsql
AS $$
DECLARE
  v_job_id uuid;
  v_stale_before timestamptz;
BEGIN
  v_stale_before := now() - make_interval(secs => p_visibility_timeout_seconds);

  SELECT j.id
    INTO v_job_id
  FROM public.rag_ingest_jobs j
  WHERE j.status = 'queued'
     OR (
       j.status = 'running'
       AND COALESCE(j.heartbeat_at, j.updated_at, j.started_at, j.created_at) < v_stale_before
     )
  ORDER BY j.created_at ASC
  LIMIT 1
  FOR UPDATE SKIP LOCKED;

  IF v_job_id IS NULL THEN
    RETURN;
  END IF;

  RETURN QUERY
  UPDATE public.rag_ingest_jobs
     SET status = 'running',
         started_at = COALESCE(started_at, now()),
         updated_at = now(),
         worker_id = p_worker_id,
         heartbeat_at = now()
   WHERE id = v_job_id
  RETURNING id, org_id, source_id, external_id, created_by, environment, worker_id, request_payload;
END;
$$;

CREATE OR REPLACE FUNCTION public.heartbeat_rag_ingest_job(
  p_job_id uuid,
  p_worker_id text
)
RETURNS boolean
LANGUAGE plpgsql
AS $$
BEGIN
  UPDATE public.rag_ingest_jobs
     SET heartbeat_at = now(),
         updated_at = now()
   WHERE id = p_job_id
     AND worker_id = p_worker_id
     AND status = 'running';
  RETURN FOUND;
END;
$$;
