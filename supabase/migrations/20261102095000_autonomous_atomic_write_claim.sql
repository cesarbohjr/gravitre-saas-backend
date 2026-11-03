-- Atomic authorization and durable claim for explicitly autonomous connector writes.
-- The workflow run row is locked so revocation and authorization serialize.
-- A committed claim is the dispatch linearization point; revocations committed
-- afterward cannot undo an already dispatched external provider side effect.
CREATE OR REPLACE FUNCTION public.claim_approved_autonomous_write(
  p_org_id uuid,
  p_run_id uuid,
  p_key text,
  p_invoke_action text,
  p_logical_action_id text,
  p_lease_seconds int DEFAULT 300
)
RETURNS jsonb
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
  v_run record;
BEGIN
  IF auth.role() IS DISTINCT FROM 'service_role' THEN
    RETURN jsonb_build_object('outcome', 'blocked', 'reason', 'service_role_required');
  END IF;
  IF p_org_id IS NULL OR p_run_id IS NULL OR NULLIF(trim(p_key), '') IS NULL THEN
    RETURN jsonb_build_object('outcome', 'blocked', 'reason', 'invalid_scope');
  END IF;
  SELECT id, approval_status, required_approvals INTO v_run
  FROM public.workflow_runs
  WHERE id = p_run_id AND org_id = p_org_id
  FOR UPDATE;
  IF NOT FOUND
     OR lower(coalesce(v_run.approval_status, '')) <> 'approved'
     OR coalesce(v_run.required_approvals, 0) < 1 THEN
    RETURN jsonb_build_object('outcome', 'blocked', 'reason', 'approval_revoked_or_missing');
  END IF;
  RETURN public.claim_write_invoke_idempotency(
    p_org_id, p_key, p_invoke_action, p_logical_action_id, p_lease_seconds
  );
END;
$$;
REVOKE ALL ON FUNCTION public.claim_approved_autonomous_write(uuid,uuid,text,text,text,int) FROM PUBLIC;
REVOKE ALL ON FUNCTION public.claim_approved_autonomous_write(uuid,uuid,text,text,text,int) FROM anon;
REVOKE ALL ON FUNCTION public.claim_approved_autonomous_write(uuid,uuid,text,text,text,int) FROM authenticated;
GRANT EXECUTE ON FUNCTION public.claim_approved_autonomous_write(uuid,uuid,text,text,text,int) TO service_role;
