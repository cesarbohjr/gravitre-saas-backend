-- Preserve disjoint graph, approval and outcome patches under concurrent writers.
-- Function-only migration: deploy before the corresponding backend revision.
CREATE OR REPLACE FUNCTION public.merge_workflow_run_parameters(
    p_run_id uuid, p_patch jsonb
) RETURNS jsonb
LANGUAGE plpgsql SECURITY INVOKER SET search_path = '' AS $$
DECLARE
    v_current jsonb;
    v_merged jsonb;
BEGIN
    IF p_patch IS NULL OR jsonb_typeof(p_patch) <> 'object' THEN
        RAISE EXCEPTION 'run parameter patch must be an object' USING ERRCODE = '22023';
    END IF;

    -- Lock before reading: subsequent writers merge against the committed result.
    SELECT wr.parameters INTO v_current
      FROM public.workflow_runs AS wr WHERE wr.id = p_run_id FOR UPDATE;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'workflow run not found' USING ERRCODE = 'P0002';
    END IF;

    -- Match safe_normalize_stored_dict for historical string-encoded objects.
    IF jsonb_typeof(v_current) = 'string' THEN
        BEGIN
            v_current := (v_current #>> '{}')::jsonb;
        EXCEPTION WHEN invalid_text_representation THEN
            v_current := '{}'::jsonb;
        END;
    END IF;
    IF v_current IS NULL OR jsonb_typeof(v_current) <> 'object' THEN
        v_current := '{}'::jsonb;
    END IF;
    v_merged := v_current || p_patch;
    UPDATE public.workflow_runs SET parameters = v_merged WHERE id = p_run_id;
    RETURN v_merged;
END;
$$;

-- Internal service mutation only; invoker privileges/RLS remain in effect.
REVOKE ALL ON FUNCTION public.merge_workflow_run_parameters(uuid, jsonb)
    FROM PUBLIC, anon, authenticated;
GRANT EXECUTE ON FUNCTION public.merge_workflow_run_parameters(uuid, jsonb)
    TO service_role;
