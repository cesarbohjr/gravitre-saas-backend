-- Create the tracking run, canonical projection and queued job in one transaction.
-- No caller-supplied run identity, approval state or sealed write scope.
CREATE OR REPLACE FUNCTION public.create_assignment_tracking_job(p_job jsonb)
RETURNS jsonb LANGUAGE plpgsql SECURITY INVOKER SET search_path = '' AS $$
DECLARE
  j public.agent_jobs%ROWTYPE;
  v_run uuid := gen_random_uuid();
BEGIN
  j := jsonb_populate_record(NULL::public.agent_jobs, p_job);
  IF j.org_id IS NULL OR j.created_by IS NULL OR nullif(j.environment,'') IS NULL
     OR j.kind IS DISTINCT FROM 'operator_task' THEN
    RAISE EXCEPTION 'Invalid assignment tracking identity';
  END IF;
  INSERT INTO public.workflow_runs
    (id,org_id,triggered_by,environment,status,run_type,trigger_type,run_hash,
     definition_snapshot,parameters)
  VALUES (v_run,j.org_id,j.created_by,j.environment,'running','execute','api',
    replace(v_run::text,'-',''),
    '{"name":"Assignment","steps":[]}'::jsonb,
    '{"source":"assignment","assignment_tracking_only":true}'::jsonb);
  INSERT INTO public.agent_jobs
    (org_id,created_by,environment,kind,session_id,payload,status,max_attempts,
     queued_at,timeout_at,retry_count,goal_id,work_object_id,bound_run_id)
  VALUES (j.org_id,j.created_by,j.environment,j.kind,j.session_id,j.payload,'queued',
    j.max_attempts,j.queued_at,j.timeout_at,0,j.goal_id,j.work_object_id,v_run)
  RETURNING * INTO j;
  IF NOT public.refresh_workflow_run_projection(v_run) THEN
    RAISE EXCEPTION 'Tracking projection not acknowledged';
  END IF;
  RETURN to_jsonb(j);
END;
$$;
REVOKE ALL ON FUNCTION public.create_assignment_tracking_job(jsonb) FROM PUBLIC, anon, authenticated;
GRANT EXECUTE ON FUNCTION public.create_assignment_tracking_job(jsonb) TO service_role;
