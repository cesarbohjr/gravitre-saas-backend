-- ECO-014 / DEC-007 / DEC-019: refresh intentional projections from locked
-- canonical source rows. No caller-supplied status/snapshot, deletion or backfill.
CREATE OR REPLACE FUNCTION public.refresh_workflow_run_projection(p_run_id uuid)
RETURNS boolean LANGUAGE plpgsql SECURITY INVOKER SET search_path = '' AS $$
DECLARE
    v public.workflow_runs%ROWTYPE;
    v_status text;
    v_started timestamptz;
    v_approval text;
    v_name text;
    v_expected integer;
    v_written integer;
BEGIN
    -- All application refreshes take the source lock before contract row locks,
    -- the same order as the existing source status trigger.
    SELECT * INTO v FROM public.workflow_runs WHERE id=p_run_id FOR UPDATE;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'workflow run not found' USING ERRCODE='P0002';
    END IF;
    -- Production workflow_runs historically has created_at, not started_at.
    -- Preserve compatibility when an optional started_at column is present.
    v_started := (to_jsonb(v)->>'started_at')::timestamptz;
    v_status := CASE lower(trim(coalesce(v.status,'')))
        WHEN 'pending' THEN 'queued' WHEN 'queued' THEN 'queued'
        WHEN 'running' THEN 'running' WHEN 'verifying' THEN 'running'
        WHEN 'completed' THEN 'completed' WHEN 'success' THEN 'completed'
        WHEN 'failed' THEN 'failed' WHEN 'error' THEN 'failed'
        WHEN 'verification_inconclusive' THEN 'failed'
        WHEN 'cancelled' THEN 'cancelled' WHEN 'canceled' THEN 'cancelled'
        WHEN 'pending_approval' THEN 'needs_approval'
        WHEN 'awaiting_approval' THEN 'needs_approval' WHEN 'needs_approval' THEN 'needs_approval'
        WHEN 'partial_success' THEN 'partial_success'
        WHEN 'flagged_for_review' THEN 'flagged_for_review' WHEN 'paused' THEN 'paused'
        ELSE NULL END;
    IF v_status IS NULL THEN
        RAISE EXCEPTION 'unsupported source run status' USING ERRCODE='22023';
    END IF;
    v_approval := CASE lower(coalesce(nullif(v.approval_status,''),'not_required'))
        WHEN 'pending_approval' THEN 'pending' WHEN 'pending' THEN 'pending'
        WHEN 'approved' THEN 'approved' WHEN 'rejected' THEN 'rejected'
        ELSE 'not_required' END;
    SELECT coalesce(nullif(w.name,''),d.name) INTO v_name
      FROM (SELECT 1) seed
      LEFT JOIN public.workflows w ON w.id=v.workflow_id AND w.org_id=v.org_id
      LEFT JOIN public.workflow_defs d ON d.id=v.workflow_id AND d.org_id=v.org_id;
    IF EXISTS(SELECT 1 FROM public.workflow_steps s WHERE s.run_id=v.id AND s.org_id<>v.org_id) THEN
        RAISE EXCEPTION 'workflow step tenant mismatch' USING ERRCODE='23514';
    END IF;
    INSERT INTO public.runs AS target (
        id,org_id,workflow_id,workflow_name,status,trigger,approval_status,
        started_at,completed_at,duration_ms,error_message,metadata,updated_at)
    VALUES(v.id,v.org_id,v.workflow_id,v_name,v_status,
        coalesce(nullif(v.trigger_type,''),nullif(v.run_type,''),'manual'),v_approval,
        coalesce(v_started,v.created_at),v.completed_at,
        coalesce(nullif(v.duration_ms,0),
            CASE WHEN v_started IS NOT NULL AND v.completed_at IS NOT NULL THEN
                trunc(greatest(extract(epoch FROM (v.completed_at-v_started))*1000,0))::integer END),
        v.error_message,jsonb_build_object('run_type',v.run_type,'run_hash',v.run_hash,
            'environment',v.environment,'status_contract_version',2,
            'execution_lifecycle',lower(trim(v.status)),'mirrored_by','schema_sync'),now())
    ON CONFLICT(id) DO UPDATE SET workflow_id=excluded.workflow_id,
        workflow_name=excluded.workflow_name,status=excluded.status,trigger=excluded.trigger,
        approval_status=excluded.approval_status,started_at=excluded.started_at,
        completed_at=excluded.completed_at,duration_ms=excluded.duration_ms,
        error_message=excluded.error_message,
        metadata=(CASE WHEN jsonb_typeof(target.metadata)='object' THEN target.metadata ELSE '{}'::jsonb END)||excluded.metadata,updated_at=now()
    WHERE target.org_id=excluded.org_id;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'run projection tenant mismatch' USING ERRCODE='23514';
    END IF;

    -- Source logs are text; contract logs are text[] (not jsonb). Snapshots
    -- remain JSONB metadata and are not converted to lossy text.
    WITH source AS MATERIALIZED (
        SELECT s.* FROM public.workflow_steps s WHERE s.run_id=v.id
    ), written AS (
        INSERT INTO public.run_steps AS target (
            id,org_id,run_id,name,status,order_index,started_at,completed_at,
            duration_ms,logs,metadata,updated_at)
        SELECT s.id,coalesce(s.org_id,v.org_id),v.id,
            coalesce(nullif(s.step_name,''),nullif(s.step_id,''),'step'),
            CASE lower(coalesce(nullif(s.status,''),'pending'))
                WHEN 'running' THEN 'running' WHEN 'completed' THEN 'completed'
                WHEN 'success' THEN 'completed' WHEN 'failed' THEN 'failed'
                WHEN 'error' THEN 'failed' WHEN 'skipped' THEN 'skipped' ELSE 'pending' END,
            coalesce(s.step_index,0),s.started_at,s.completed_at,
            CASE WHEN s.started_at IS NOT NULL AND s.completed_at IS NOT NULL THEN
                trunc(greatest(extract(epoch FROM (s.completed_at-s.started_at))*1000,0))::integer END,
            CASE WHEN s.logs IS NULL OR s.logs='' THEN ARRAY[]::text[] ELSE ARRAY[s.logs] END,
            jsonb_build_object('step_id',s.step_id,'step_type',s.step_type,'error_code',s.error_code)
                ||CASE WHEN s.input_snapshot IS NOT NULL THEN jsonb_build_object('input_snapshot',s.input_snapshot) ELSE '{}'::jsonb END
                ||CASE WHEN s.output_snapshot IS NOT NULL THEN jsonb_build_object('output_snapshot',s.output_snapshot) ELSE '{}'::jsonb END,
            now() FROM source s WHERE true
        ON CONFLICT(id) DO UPDATE SET name=excluded.name,status=excluded.status,
            order_index=excluded.order_index,started_at=excluded.started_at,
            completed_at=excluded.completed_at,duration_ms=excluded.duration_ms,
            logs=excluded.logs,metadata=((CASE WHEN jsonb_typeof(target.metadata)='object' THEN target.metadata ELSE '{}'::jsonb END)-'input_snapshot'-'output_snapshot')||excluded.metadata,
            updated_at=now()
        WHERE target.org_id=excluded.org_id AND target.run_id=excluded.run_id
        RETURNING id
    ) SELECT (SELECT count(*) FROM source),(SELECT count(*) FROM written) INTO v_expected,v_written;
    IF v_expected<>v_written THEN
        RAISE EXCEPTION 'step projection tenant or parent mismatch' USING ERRCODE='23514';
    END IF;
    RETURN true;
END;
$$;
REVOKE ALL ON FUNCTION public.refresh_workflow_run_projection(uuid) FROM PUBLIC,anon,authenticated;
GRANT EXECUTE ON FUNCTION public.refresh_workflow_run_projection(uuid) TO service_role;

-- Keep terminal proof, source status, outbox and projection in one transaction.
CREATE OR REPLACE FUNCTION public.persist_workflow_run_outcome(
    p_run_id uuid, p_org_id uuid, p_status text, p_patch jsonb,
    p_completed_at timestamptz, p_error_message text, p_approval_status text,
    p_completion_proven boolean, p_actor_id text
) RETURNS jsonb
LANGUAGE plpgsql SECURITY INVOKER SET search_path = '' AS $$
DECLARE
    v_run public.workflow_runs%ROWTYPE;
    v_params jsonb;
BEGIN
    IF p_status IS NULL OR p_status NOT IN ('completed','failed','cancelled',
        'partial_success','flagged_for_review','verification_inconclusive')
        OR p_patch IS NULL OR jsonb_typeof(p_patch) <> 'object' THEN
        RAISE EXCEPTION 'invalid outcome mutation' USING ERRCODE='22023';
    END IF;
    SELECT * INTO v_run FROM public.workflow_runs
      WHERE id=p_run_id AND org_id=p_org_id FOR UPDATE;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'workflow run not found' USING ERRCODE='P0002';
    END IF;
    IF (v_run.status IN ('completed','failed','cancelled','partial_success') AND v_run.status<>p_status)
       OR (v_run.status IN ('verification_inconclusive','flagged_for_review')
           AND p_status='completed' AND p_completion_proven IS DISTINCT FROM true) THEN
        RETURN jsonb_build_object('accepted',false,'status',v_run.status);
    END IF;
    -- Keep the first committed proof/actor for an outcome; retries cannot replace
    -- it with another summary or recipient while resuming delivery.
    IF v_run.status=p_status AND v_run.parameters->>'terminal_outcome_version'='2' THEN
        PERFORM public.refresh_workflow_run_projection(p_run_id);
        RETURN jsonb_build_object('accepted',true,'status',v_run.status,
            'parameters',v_run.parameters,'error_message',v_run.error_message);
    END IF;
    IF p_status='completed' AND p_completion_proven IS DISTINCT FROM true
       AND (v_run.parameters->'requires_outcome_verification'='true'::jsonb
            OR p_patch->'requires_outcome_verification'='true'::jsonb) THEN
        RAISE EXCEPTION 'completion requires verification' USING ERRCODE='23514';
    END IF;
    -- The helper and status write share this transaction and row lock. Failure
    -- of status/outbox constraints rolls back the proof mutation as well.
    v_params := public.merge_workflow_run_parameters(p_run_id,
        (p_patch - 'outcome_fanout' - 'notification_emitted' - 'outcome_finalized') ||
        jsonb_build_object('terminal_outcome_version',2,'outcome_actor_id',p_actor_id,
            'outcome_actor_required',coalesce(length(trim(p_actor_id))>0,false),
            'outcome_fanout_version',1,'outcome_fanout',
            CASE WHEN v_run.status=p_status
                AND v_run.parameters->>'outcome_fanout_version'='1'
                AND v_run.parameters->'outcome_fanout'->>'status'=p_status
                THEN v_run.parameters->'outcome_fanout'
                ELSE jsonb_build_object('status',p_status) END,
            'notification_emitted',coalesce(v_run.status=p_status
                AND v_run.parameters->'outcome_fanout'->'notification_emitted'='true'::jsonb,false),
            'outcome_finalized',coalesce(v_run.status=p_status
                AND v_run.parameters->'outcome_fanout'->'complete'='true'::jsonb,false)));
    UPDATE public.workflow_runs SET status=p_status, completed_at=p_completed_at,
        error_message=p_error_message,
        approval_status=coalesce(p_approval_status,approval_status)
      WHERE id=p_run_id AND org_id=p_org_id;
    PERFORM public.refresh_workflow_run_projection(p_run_id);
    RETURN jsonb_build_object('accepted',true,'status',p_status,
        'parameters',v_params,'error_message',p_error_message);
END;
$$;

REVOKE ALL ON FUNCTION public.persist_workflow_run_outcome(uuid,uuid,text,jsonb,timestamptz,text,text,boolean,text) FROM PUBLIC,anon,authenticated;
GRANT EXECUTE ON FUNCTION public.persist_workflow_run_outcome(uuid,uuid,text,jsonb,timestamptz,text,text,boolean,text) TO service_role;
