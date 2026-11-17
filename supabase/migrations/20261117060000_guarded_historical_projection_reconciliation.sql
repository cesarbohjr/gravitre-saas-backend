-- ECO-014 / DEC-007 / DEC-019: explicit per-run projection repair and undo.
-- Additive operator API only. Installing this migration performs no backfill.
-- Default mode is read-only preview; mutations require scope, reviewed digests,
-- a batch identity and an external approval reference. Service-only/RLS-protected.
CREATE TABLE IF NOT EXISTS public.historical_projection_reconciliations (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    batch_id uuid NOT NULL,
    org_id uuid NOT NULL,
    run_id uuid NOT NULL,
    approval_ref text NOT NULL CHECK (length(trim(approval_ref)) BETWEEN 1 AND 200),
    source_digest text NOT NULL,
    before_digest text NOT NULL,
    after_digest text NOT NULL,
    before_projection jsonb NOT NULL,
    state text NOT NULL CHECK (state IN ('applied','undone')),
    created_at timestamptz NOT NULL DEFAULT now(),
    undone_at timestamptz,
    undo_approval_ref text,
    UNIQUE(batch_id,org_id,run_id)
);
ALTER TABLE public.historical_projection_reconciliations ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON TABLE public.historical_projection_reconciliations FROM PUBLIC,anon,authenticated;
GRANT SELECT,INSERT,UPDATE ON TABLE public.historical_projection_reconciliations TO service_role;

CREATE OR REPLACE FUNCTION public.historical_projection_snapshot(p_org_id uuid,p_run_id uuid)
RETURNS jsonb LANGUAGE plpgsql SECURITY INVOKER SET search_path = '' SET timezone = 'UTC' AS $$
DECLARE
    v_source public.workflow_runs%ROWTYPE;
    v_target public.runs%ROWTYPE;
    v_source_steps jsonb;
    v_target_steps jsonb;
    v_display_name text;
    v_fk_count integer;
BEGIN
    SELECT * INTO v_source FROM public.workflow_runs WHERE id=p_run_id AND org_id=p_org_id;
    IF NOT FOUND THEN RAISE EXCEPTION 'scoped source not found' USING ERRCODE='P0002'; END IF;
    IF v_source.run_type IS DISTINCT FROM 'execute' OR lower(trim(v_source.status)) NOT IN
        ('completed','success','failed','error','cancelled','canceled','partial_success',
         'verification_inconclusive','flagged_for_review') THEN
        RAISE EXCEPTION 'only known terminal execute runs may be reconciled' USING ERRCODE='22023';
    END IF;
    SELECT * INTO v_target FROM public.runs WHERE id=p_run_id;
    IF NOT FOUND THEN RAISE EXCEPTION 'existing projection required' USING ERRCODE='P0002'; END IF;
    IF v_target.org_id IS DISTINCT FROM p_org_id THEN
        RAISE EXCEPTION 'projection tenant conflict' USING ERRCODE='23514';
    END IF;
    -- Parent FOR UPDATE locks fence inserts via these validated immediate FKs;
    -- existing child rows are locked separately by the mutation function.
    SELECT count(DISTINCT c.conrelid) INTO v_fk_count FROM pg_catalog.pg_constraint c
    WHERE c.contype='f' AND c.convalidated AND NOT c.condeferrable AND (
      (c.conrelid='public.workflow_steps'::regclass AND c.confrelid='public.workflow_runs'::regclass
       AND c.conkey=ARRAY[(SELECT attnum FROM pg_catalog.pg_attribute WHERE attrelid=c.conrelid AND attname='run_id')]
       AND c.confkey=ARRAY[(SELECT attnum FROM pg_catalog.pg_attribute WHERE attrelid=c.confrelid AND attname='id')]) OR
      (c.conrelid='public.run_steps'::regclass AND c.confrelid='public.runs'::regclass
       AND c.conkey=ARRAY[(SELECT attnum FROM pg_catalog.pg_attribute WHERE attrelid=c.conrelid AND attname='run_id')]
       AND c.confkey=ARRAY[(SELECT attnum FROM pg_catalog.pg_attribute WHERE attrelid=c.confrelid AND attname='id')])
    );
    IF v_fk_count<>2 THEN
        RAISE EXCEPTION 'validated immediate parent foreign keys required' USING ERRCODE='23514';
    END IF;
    IF EXISTS(SELECT 1 FROM public.workflow_steps s WHERE s.run_id=p_run_id AND s.org_id IS DISTINCT FROM p_org_id)
       OR EXISTS(SELECT 1 FROM public.run_steps s WHERE s.run_id=p_run_id AND s.org_id IS DISTINCT FROM p_org_id)
       OR EXISTS(SELECT s.id FROM public.workflow_steps s WHERE s.run_id=p_run_id
                 EXCEPT SELECT t.id FROM public.run_steps t WHERE t.run_id=p_run_id)
       OR EXISTS(SELECT t.id FROM public.run_steps t WHERE t.run_id=p_run_id
                 EXCEPT SELECT s.id FROM public.workflow_steps s WHERE s.run_id=p_run_id) THEN
        RAISE EXCEPTION 'existing step identity parity required' USING ERRCODE='23514';
    END IF;
    SELECT coalesce(jsonb_agg(to_jsonb(s) ORDER BY s.id),'[]'::jsonb) INTO v_source_steps
      FROM public.workflow_steps s WHERE s.run_id=p_run_id;
    SELECT coalesce(jsonb_agg(to_jsonb(s) ORDER BY s.id),'[]'::jsonb) INTO v_target_steps
      FROM public.run_steps s WHERE s.run_id=p_run_id;
    SELECT coalesce(nullif(w.name,''),d.name) INTO v_display_name
      FROM (SELECT 1) seed
      LEFT JOIN public.workflows w ON w.id=v_source.workflow_id AND w.org_id=p_org_id
      LEFT JOIN public.workflow_defs d ON d.id=v_source.workflow_id AND d.org_id=p_org_id;
    RETURN jsonb_build_object('source',jsonb_build_object('run',to_jsonb(v_source),'steps',v_source_steps,
        'workflow_display_name',v_display_name),
        'projection',jsonb_build_object('run',to_jsonb(v_target),'steps',v_target_steps));
END $$;
REVOKE ALL ON FUNCTION public.historical_projection_snapshot(uuid,uuid) FROM PUBLIC,anon,authenticated;
GRANT EXECUTE ON FUNCTION public.historical_projection_snapshot(uuid,uuid) TO service_role;

CREATE OR REPLACE FUNCTION public.reconcile_historical_run_projection(
    p_org_id uuid,p_run_id uuid,p_batch_id uuid DEFAULT NULL,
    p_source_digest text DEFAULT NULL,p_projection_digest text DEFAULT NULL,
    p_approval_ref text DEFAULT NULL,p_mode text DEFAULT 'preview'
) RETURNS jsonb LANGUAGE plpgsql SECURITY INVOKER SET search_path = '' SET timezone = 'UTC' AS $$
DECLARE
    v_snapshot jsonb;
    v_after jsonb;
    v_source_digest text;
    v_target_digest text;
    v_after_digest text;
    v_journal public.historical_projection_reconciliations%ROWTYPE;
    v_before public.runs%ROWTYPE;
    v_written integer;
BEGIN
    IF p_org_id IS NULL OR p_run_id IS NULL OR p_mode IS NULL OR p_mode NOT IN ('preview','apply','undo') THEN
        RAISE EXCEPTION 'explicit scope and known mode required' USING ERRCODE='22023';
    END IF;
    IF p_mode<>'preview' THEN
        IF p_batch_id IS NULL OR p_approval_ref IS NULL OR length(trim(p_approval_ref)) NOT BETWEEN 1 AND 200
           OR p_source_digest IS NULL OR p_source_digest !~ '^[a-f0-9]{64}$'
           OR p_projection_digest IS NULL OR p_projection_digest !~ '^[a-f0-9]{64}$' THEN
            RAISE EXCEPTION 'reviewed digests, batch and approval reference required' USING ERRCODE='22023';
        END IF;
        -- Same lock order as canonical terminal persistence and projection refresh.
        PERFORM 1 FROM public.workflow_runs WHERE id=p_run_id AND org_id=p_org_id FOR UPDATE;
        IF NOT FOUND THEN RAISE EXCEPTION 'scoped source not found' USING ERRCODE='P0002'; END IF;
        PERFORM 1 FROM public.workflow_steps WHERE run_id=p_run_id ORDER BY id FOR UPDATE;
        PERFORM w.id FROM public.workflows w JOIN public.workflow_runs r ON r.workflow_id=w.id
          WHERE r.id=p_run_id AND r.org_id=p_org_id AND w.org_id=p_org_id FOR SHARE OF w;
        PERFORM d.id FROM public.workflow_defs d JOIN public.workflow_runs r ON r.workflow_id=d.id
          WHERE r.id=p_run_id AND r.org_id=p_org_id AND d.org_id=p_org_id FOR SHARE OF d;
        PERFORM 1 FROM public.runs WHERE id=p_run_id FOR UPDATE;
        PERFORM 1 FROM public.run_steps WHERE run_id=p_run_id ORDER BY id FOR UPDATE;
    END IF;
    v_snapshot:=public.historical_projection_snapshot(p_org_id,p_run_id);
    v_source_digest:=encode(sha256(convert_to((v_snapshot->'source')::text,'UTF8')),'hex');
    v_target_digest:=encode(sha256(convert_to((v_snapshot->'projection')::text,'UTF8')),'hex');
    IF p_mode='preview' THEN
        RETURN jsonb_build_object('mode','preview','org_id',p_org_id,'run_id',p_run_id,
            'source_digest',v_source_digest,'projection_digest',v_target_digest,
            'source_status',v_snapshot#>>'{source,run,status}',
            'projection_status',v_snapshot#>>'{projection,run,status}',
            'proposed_status',CASE lower(trim(v_snapshot#>>'{source,run,status}'))
                WHEN 'success' THEN 'completed' WHEN 'error' THEN 'failed'
                WHEN 'canceled' THEN 'cancelled' WHEN 'verification_inconclusive' THEN 'failed'
                ELSE lower(trim(v_snapshot#>>'{source,run,status}')) END,
            'proposed_status_contract_version',2,
            'step_count',jsonb_array_length(v_snapshot#>'{source,steps}'));
    END IF;
    SELECT * INTO v_journal FROM public.historical_projection_reconciliations
      WHERE batch_id=p_batch_id AND org_id=p_org_id AND run_id=p_run_id FOR UPDATE;
    IF p_mode='apply' AND FOUND THEN
        IF v_journal.state<>'applied' OR v_journal.source_digest<>p_source_digest
           OR v_source_digest<>p_source_digest OR v_journal.before_digest<>p_projection_digest
           OR v_target_digest<>v_journal.after_digest OR v_journal.approval_ref<>trim(p_approval_ref) THEN
            RAISE EXCEPTION 'batch replay differs from reviewed state' USING ERRCODE='40001';
        END IF;
        RETURN jsonb_build_object('state','applied','journal_id',v_journal.id,
            'source_digest',v_source_digest,'projection_digest',v_target_digest,'replayed',true);
    ELSIF p_mode='undo' THEN
        IF NOT FOUND THEN RAISE EXCEPTION 'scoped reconciliation journal not found' USING ERRCODE='P0002'; END IF;
        IF v_journal.source_digest<>p_source_digest OR v_source_digest<>p_source_digest
           OR v_journal.after_digest<>p_projection_digest THEN
            RAISE EXCEPTION 'undo source or reviewed checkpoint changed' USING ERRCODE='40001';
        END IF;
        IF v_journal.state='undone' THEN
            IF v_target_digest<>v_journal.before_digest THEN
                RAISE EXCEPTION 'projection changed after undo' USING ERRCODE='40001';
            END IF;
            RETURN jsonb_build_object('state','undone','journal_id',v_journal.id,'replayed',true,
                'source_digest',v_source_digest,'projection_digest',v_target_digest);
        END IF;
        IF v_target_digest<>v_journal.after_digest THEN
            RAISE EXCEPTION 'projection changed after reconciliation' USING ERRCODE='40001';
        END IF;
        SELECT * INTO v_before FROM jsonb_populate_record(NULL::public.runs,v_journal.before_projection->'run');
        UPDATE public.runs SET workflow_id=v_before.workflow_id,workflow_name=v_before.workflow_name,
            status=v_before.status,trigger=v_before.trigger,approval_status=v_before.approval_status,
            started_at=v_before.started_at,completed_at=v_before.completed_at,duration_ms=v_before.duration_ms,
            error_message=v_before.error_message,metadata=v_before.metadata,updated_at=v_before.updated_at
          WHERE id=p_run_id AND org_id=p_org_id;
        UPDATE public.run_steps t SET name=b.name,status=b.status,order_index=b.order_index,
            started_at=b.started_at,completed_at=b.completed_at,duration_ms=b.duration_ms,
            logs=b.logs,metadata=b.metadata,updated_at=b.updated_at
          FROM jsonb_populate_recordset(NULL::public.run_steps,v_journal.before_projection->'steps') b
          WHERE t.id=b.id AND t.run_id=p_run_id AND t.org_id=p_org_id;
        GET DIAGNOSTICS v_written=ROW_COUNT;
        IF v_written<>jsonb_array_length(v_journal.before_projection->'steps') THEN
            RAISE EXCEPTION 'undo step identity changed' USING ERRCODE='23514';
        END IF;
        v_after:=public.historical_projection_snapshot(p_org_id,p_run_id);
        v_after_digest:=encode(sha256(convert_to((v_after->'projection')::text,'UTF8')),'hex');
        IF v_after_digest<>v_journal.before_digest THEN
            RAISE EXCEPTION 'undo did not restore exact projection checkpoint' USING ERRCODE='23514';
        END IF;
        UPDATE public.historical_projection_reconciliations SET state='undone',
            undone_at=now(),undo_approval_ref=trim(p_approval_ref) WHERE id=v_journal.id;
        RETURN jsonb_build_object('state','undone','journal_id',v_journal.id,'replayed',false,
            'source_digest',v_source_digest,'projection_digest',v_after_digest);
    END IF;
    IF v_source_digest<>p_source_digest OR v_target_digest<>p_projection_digest THEN
        RAISE EXCEPTION 'reviewed source or projection changed' USING ERRCODE='40001';
    END IF;
    IF public.refresh_workflow_run_projection(p_run_id) IS DISTINCT FROM true THEN
        RAISE EXCEPTION 'canonical refresh not acknowledged' USING ERRCODE='23514';
    END IF;
    v_after:=public.historical_projection_snapshot(p_org_id,p_run_id);
    IF encode(sha256(convert_to((v_after->'source')::text,'UTF8')),'hex')<>v_source_digest THEN
        RAISE EXCEPTION 'canonical source changed during reconciliation' USING ERRCODE='40001';
    END IF;
    v_after_digest:=encode(sha256(convert_to((v_after->'projection')::text,'UTF8')),'hex');
    INSERT INTO public.historical_projection_reconciliations
        (batch_id,org_id,run_id,approval_ref,source_digest,before_digest,after_digest,before_projection,state)
      VALUES(p_batch_id,p_org_id,p_run_id,trim(p_approval_ref),v_source_digest,v_target_digest,
             v_after_digest,v_snapshot->'projection','applied') RETURNING * INTO v_journal;
    RETURN jsonb_build_object('state','applied','journal_id',v_journal.id,'replayed',false,
        'source_digest',v_source_digest,'projection_digest',v_after_digest);
END $$;
REVOKE ALL ON FUNCTION public.reconcile_historical_run_projection(uuid,uuid,uuid,text,text,text,text) FROM PUBLIC,anon,authenticated;
GRANT EXECUTE ON FUNCTION public.reconcile_historical_run_projection(uuid,uuid,uuid,text,text,text,text) TO service_role;
