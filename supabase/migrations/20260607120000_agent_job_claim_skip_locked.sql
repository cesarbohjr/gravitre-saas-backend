-- STA-275: atomic agent job claiming for multi-instance workers (SKIP LOCKED).

CREATE OR REPLACE FUNCTION public.claim_agent_job()
RETURNS SETOF public.agent_jobs
LANGUAGE plpgsql
AS $$
DECLARE
  v_job_id uuid;
BEGIN
  SELECT j.id
    INTO v_job_id
  FROM public.agent_jobs j
  WHERE j.status = 'queued'
  ORDER BY j.created_at ASC
  LIMIT 1
  FOR UPDATE SKIP LOCKED;

  IF v_job_id IS NULL THEN
    RETURN;
  END IF;

  RETURN QUERY
  UPDATE public.agent_jobs
     SET status = 'running',
         started_at = COALESCE(started_at, now()),
         attempts = COALESCE(attempts, 0) + 1,
         updated_at = now()
   WHERE id = v_job_id
  RETURNING *;
END;
$$;

CREATE OR REPLACE FUNCTION public.claim_agent_job_by_id(p_job_id uuid)
RETURNS SETOF public.agent_jobs
LANGUAGE plpgsql
AS $$
BEGIN
  RETURN QUERY
  UPDATE public.agent_jobs
     SET status = 'running',
         started_at = COALESCE(started_at, now()),
         attempts = COALESCE(attempts, 0) + 1,
         updated_at = now()
   WHERE id = p_job_id
     AND status = 'queued'
  RETURNING *;
END;
$$;
