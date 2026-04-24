-- Phase 6: Ingestion job payload + claim function

ALTER TABLE public.rag_ingest_jobs
  ADD COLUMN IF NOT EXISTS request_payload jsonb,
  ADD COLUMN IF NOT EXISTS updated_at timestamptz NOT NULL DEFAULT now();

CREATE INDEX IF NOT EXISTS idx_rag_ingest_jobs_status_created
  ON public.rag_ingest_jobs(status, created_at);

CREATE OR REPLACE FUNCTION public.claim_rag_ingest_job()
RETURNS TABLE (
  id uuid,
  org_id uuid,
  source_id uuid,
  external_id text,
  created_by uuid,
  request_payload jsonb
)
LANGUAGE plpgsql
AS $$
DECLARE
  v_job_id uuid;
BEGIN
  SELECT j.id
    INTO v_job_id
  FROM public.rag_ingest_jobs j
  WHERE j.status = 'queued'
  ORDER BY j.created_at ASC
  LIMIT 1
  FOR UPDATE SKIP LOCKED;

  IF v_job_id IS NULL THEN
    RETURN;
  END IF;

  RETURN QUERY
  UPDATE public.rag_ingest_jobs
     SET status = 'running',
         started_at = now(),
         updated_at = now()
   WHERE id = v_job_id
  RETURNING id, org_id, source_id, external_id, created_by, request_payload;
END;
$$;
