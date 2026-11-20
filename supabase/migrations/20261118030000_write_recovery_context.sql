-- ECO-002: durable original-request identity and connector binding.
-- The write claim remains non-dispatchable until this service-role fenced bind succeeds.
ALTER TABLE public.write_invoke_idempotency
  ADD COLUMN IF NOT EXISTS original_args jsonb,
  ADD COLUMN IF NOT EXISTS connector_id text,
  ADD COLUMN IF NOT EXISTS recovery_context_bound_at timestamptz;

CREATE OR REPLACE FUNCTION public.bind_write_recovery_context(
  p_org_id uuid,
  p_key text,
  p_claim_token uuid,
  p_invoke_action text,
  p_connector_id text,
  p_original_args jsonb
) RETURNS jsonb
LANGUAGE plpgsql SECURITY DEFINER SET search_path = public
AS $$
DECLARE v_row public.write_invoke_idempotency%ROWTYPE;
BEGIN
  IF auth.role() IS DISTINCT FROM 'service_role' THEN
    RETURN jsonb_build_object('outcome','rejected','reason','service_role_required');
  END IF;
  IF NULLIF(trim(p_connector_id),'') IS NULL OR
     p_original_args IS NULL OR jsonb_typeof(p_original_args) <> 'object' OR
     p_claim_token IS NULL THEN
    RETURN jsonb_build_object('outcome','rejected','reason','invalid_context');
  END IF;
  SELECT * INTO v_row FROM public.write_invoke_idempotency
    WHERE org_id=p_org_id AND idempotency_key=p_key FOR UPDATE;
  IF NOT FOUND OR v_row.status <> 'in_progress'
     OR v_row.claim_token IS DISTINCT FROM p_claim_token
     OR v_row.invoke_action IS DISTINCT FROM p_invoke_action THEN
    RETURN jsonb_build_object('outcome','rejected','reason','stale_or_mismatched_claim');
  END IF;
  IF v_row.recovery_context_bound_at IS NOT NULL AND
     (v_row.connector_id IS DISTINCT FROM p_connector_id OR
      v_row.original_args IS DISTINCT FROM p_original_args) THEN
    RETURN jsonb_build_object('outcome','rejected','reason','context_already_bound');
  END IF;
  UPDATE public.write_invoke_idempotency
     SET original_args=p_original_args, connector_id=p_connector_id,
         recovery_context_bound_at=coalesce(recovery_context_bound_at,now()),
         updated_at=now()
   WHERE id=v_row.id;
  RETURN jsonb_build_object('outcome','bound');
END;
$$;
REVOKE ALL ON FUNCTION public.bind_write_recovery_context(uuid,text,uuid,text,text,jsonb) FROM PUBLIC, anon, authenticated;
GRANT EXECUTE ON FUNCTION public.bind_write_recovery_context(uuid,text,uuid,text,text,jsonb) TO service_role;
