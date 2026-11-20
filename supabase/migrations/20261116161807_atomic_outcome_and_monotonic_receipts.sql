-- Canonical finalizer transactions. Apply after atomic_workflow_run_parameters
-- and before activating the corresponding backend. No new tables or services.
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
    RETURN jsonb_build_object('accepted',true,'status',p_status,
        'parameters',v_params,'error_message',p_error_message);
END;
$$;

CREATE OR REPLACE FUNCTION public.checkpoint_workflow_run_outcome(
    p_run_id uuid, p_org_id uuid, p_status text, p_receipt jsonb,
    p_finalize boolean, p_actor_required boolean
) RETURNS jsonb
LANGUAGE plpgsql SECURITY INVOKER SET search_path = '' AS $$
DECLARE
    v_run public.workflow_runs%ROWTYPE;
    v_old jsonb := '{}'::jsonb;
    v_receipt jsonb := '{}'::jsonb;
    v_key text;
    v_actor_required boolean;
    v_requested boolean;
    v_complete boolean;
BEGIN
    IF p_receipt IS NULL OR jsonb_typeof(p_receipt)<>'object' THEN
        RAISE EXCEPTION 'invalid outcome receipt' USING ERRCODE='22023';
    END IF;
    SELECT * INTO v_run FROM public.workflow_runs
      WHERE id=p_run_id AND org_id=p_org_id FOR UPDATE;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'workflow run not found' USING ERRCODE='P0002';
    END IF;
    IF p_status IS NULL OR p_status NOT IN ('completed','failed','cancelled',
        'partial_success','flagged_for_review','verification_inconclusive')
        OR v_run.status<>p_status THEN
        RETURN jsonb_build_object('accepted',false,'status',v_run.status);
    END IF;
    IF v_run.parameters->>'outcome_fanout_version'='1'
       AND v_run.parameters->'outcome_fanout'->>'status'=p_status THEN
        v_old := v_run.parameters->'outcome_fanout';
    END IF;
    FOREACH v_key IN ARRAY ARRAY['run_persisted','audit_written','notification_emitted','learning_recorded'] LOOP
        IF p_receipt ? v_key AND jsonb_typeof(p_receipt->v_key)<>'boolean' THEN
            RAISE EXCEPTION 'receipt acknowledgements must be boolean' USING ERRCODE='22023';
        END IF;
        v_receipt := v_receipt || jsonb_build_object(v_key,
            coalesce(v_old->v_key='true'::jsonb,false) OR coalesce(p_receipt->v_key='true'::jsonb,false));
    END LOOP;
    -- A retry without an actor cannot weaken the original delivery requirements.
    v_actor_required := coalesce(v_run.parameters->'outcome_actor_required'='true'::jsonb,false)
        OR coalesce(v_old->'actor_required'='true'::jsonb,false) OR coalesce(p_actor_required,false);
    v_requested := coalesce(v_old->'finalize_requested'='true'::jsonb,false)
        OR coalesce(v_old->'complete'='true'::jsonb,false) OR coalesce(p_finalize,false);
    v_complete := v_requested AND v_receipt->'run_persisted'='true'::jsonb
        AND v_receipt->'learning_recorded'='true'::jsonb
        AND (NOT v_actor_required OR (v_receipt->'audit_written'='true'::jsonb
            AND v_receipt->'notification_emitted'='true'::jsonb));
    v_receipt := v_receipt || jsonb_build_object('status',p_status,
        'actor_required',v_actor_required,'finalize_requested',v_requested,'complete',v_complete);
    PERFORM public.merge_workflow_run_parameters(p_run_id,jsonb_build_object(
        'outcome_fanout_version',1,'outcome_fanout',v_receipt,
        'notification_emitted',v_receipt->'notification_emitted','outcome_finalized',v_complete));
    RETURN jsonb_build_object('accepted',true,'status',p_status,'receipt',v_receipt);
END;
$$;

REVOKE ALL ON FUNCTION public.persist_workflow_run_outcome(uuid,uuid,text,jsonb,timestamptz,text,text,boolean,text) FROM PUBLIC,anon,authenticated;
REVOKE ALL ON FUNCTION public.checkpoint_workflow_run_outcome(uuid,uuid,text,jsonb,boolean,boolean) FROM PUBLIC,anon,authenticated;
GRANT EXECUTE ON FUNCTION public.persist_workflow_run_outcome(uuid,uuid,text,jsonb,timestamptz,text,text,boolean,text) TO service_role;
GRANT EXECUTE ON FUNCTION public.checkpoint_workflow_run_outcome(uuid,uuid,text,jsonb,boolean,boolean) TO service_role;
