-- Phase 2D: claim RAG ingest jobs for a named set of organisations only.
--
-- The in-process indexing pilot (RAG_WORKER_PILOT_ENABLED, default off) must touch the
-- pilot tenants' queue and nothing else. claim_rag_ingest_job takes any org's job, so
-- this adds an org-filtered twin with the same claim, lease and stale-reclaim rules.
-- claim_rag_ingest_job is unchanged.
--
-- Preflight (read-only):
--   SELECT proname FROM pg_proc WHERE pronamespace = 'public'::regnamespace
--     AND proname = 'claim_rag_ingest_job_for_orgs';                    -- expect 0 rows
--   SELECT org_id, status, count(*) FROM public.rag_ingest_jobs
--    GROUP BY 1, 2 ORDER BY 1, 2;                                       -- backlog the pilot would see
--
-- Rollback: DROP FUNCTION IF EXISTS public.claim_rag_ingest_job_for_orgs(text, integer, uuid[]);

CREATE OR REPLACE FUNCTION public.claim_rag_ingest_job_for_orgs(
  p_worker_id text,
  p_visibility_timeout_seconds int DEFAULT 300,
  p_org_ids uuid[] DEFAULT '{}'
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
SET search_path = public, pg_temp
AS $$
DECLARE
  v_job_id uuid;
  v_stale_before timestamptz;
BEGIN
  IF p_org_ids IS NULL OR cardinality(p_org_ids) = 0 THEN
    RETURN;  -- an empty allowlist claims nothing, never everything
  END IF;
  v_stale_before := now() - make_interval(secs => p_visibility_timeout_seconds);

  SELECT j.id
    INTO v_job_id
  FROM public.rag_ingest_jobs j
  WHERE j.org_id = ANY (p_org_ids)
    AND (
      j.status = 'queued'
      OR (
        j.status = 'running'
        AND COALESCE(j.heartbeat_at, j.updated_at, j.started_at, j.created_at) < v_stale_before
      )
    )
  ORDER BY j.created_at ASC
  LIMIT 1
  FOR UPDATE SKIP LOCKED;

  IF v_job_id IS NULL THEN
    RETURN;
  END IF;

  RETURN QUERY
  UPDATE public.rag_ingest_jobs AS u
     SET status = 'running',
         started_at = COALESCE(u.started_at, now()),
         updated_at = now(),
         worker_id = p_worker_id,
         heartbeat_at = now()
   WHERE u.id = v_job_id
  RETURNING u.id, u.org_id, u.source_id, u.external_id, u.created_by, u.environment, u.worker_id,
            u.request_payload;
END;
$$;

REVOKE ALL ON FUNCTION public.claim_rag_ingest_job_for_orgs(text, integer, uuid[]) FROM PUBLIC, anon, authenticated;
GRANT EXECUTE ON FUNCTION public.claim_rag_ingest_job_for_orgs(text, integer, uuid[]) TO service_role;
