-- Assistant model-call usage and overage are one transaction. Expand-only.
-- Preflight: verify 20260531000000, 20260531000100 and 20261013080000
-- are applied; verify uq_usage_tracking_org_idempotency and
-- uq_overage_usage_org_idempotency exist. Do not apply to production without
-- approval for this exact file. Existing ledger rows are not rewritten.
-- Rollback: DROP FUNCTION public.record_assistant_model_usage(uuid, uuid, int, int, text);

CREATE OR REPLACE FUNCTION public.record_assistant_model_usage(
  p_org_id uuid,
  p_model_call_id uuid,
  p_quantity int,
  p_included int,
  p_environment text DEFAULT 'production'
) RETURNS text
LANGUAGE plpgsql
SECURITY INVOKER
SET search_path = ''
AS $$
DECLARE
  v_call public.model_calls%ROWTYPE;
  v_start date;
  v_end date;
  v_key text;
  v_before bigint;
  v_existing public.usage_tracking%ROWTYPE;
  v_overage int;
  v_inserted uuid;
BEGIN
  IF p_quantity IS NULL OR p_quantity < 1 OR p_included IS NULL OR p_included < 0
     OR p_environment IS NULL OR p_environment = '' THEN
    RAISE EXCEPTION 'Invalid assistant billing arguments' USING ERRCODE = '22023';
  END IF;
  SELECT * INTO v_call FROM public.model_calls
    WHERE id = p_model_call_id AND org_id = p_org_id
      AND turn_id LIKE 'assistant:%';
  IF NOT FOUND THEN
    RAISE EXCEPTION 'Attributable assistant model call not found' USING ERRCODE = '22023';
  END IF;
  IF v_call.created_at IS NULL THEN
    RAISE EXCEPTION 'Assistant model call has no billing timestamp' USING ERRCODE = '22023';
  END IF;
  IF coalesce(v_call.input_tokens, 0) + coalesce(v_call.output_tokens, 0) <= 0 THEN
    RETURN 'zero_tokens';
  END IF;
  v_start := date_trunc('month', v_call.created_at AT TIME ZONE 'UTC')::date;
  v_end := (v_start + interval '1 month' - interval '1 day')::date;
  v_key := p_org_id::text || ':assistant:' || p_model_call_id::text || ':' || v_start::text;

  -- Serialize both total calculation and inserts for this org/period/metric.
  -- The lock is transaction-scoped, including a failure after the INSERT.
  PERFORM pg_catalog.pg_advisory_xact_lock(
    pg_catalog.hashtextextended(p_org_id::text || ':ai_credits:' || p_environment || ':' || v_start::text, 0)
  );
  SELECT * INTO v_existing FROM public.usage_tracking
    WHERE org_id = p_org_id AND idempotency_key = v_key;
  IF FOUND THEN
    IF v_existing.quantity IS DISTINCT FROM p_quantity
       OR v_existing.environment IS DISTINCT FROM p_environment
       OR v_existing.metric_type IS DISTINCT FROM 'ai_credits'
       OR v_existing.period_start IS DISTINCT FROM v_start
       OR v_existing.period_end IS DISTINCT FROM v_end
       OR v_existing.source IS DISTINCT FROM 'assistant'
       OR v_existing.source_id IS DISTINCT FROM p_model_call_id::text
       OR v_existing.model_name IS DISTINCT FROM v_call.model_name
       OR v_existing.input_tokens IS DISTINCT FROM v_call.input_tokens
       OR v_existing.output_tokens IS DISTINCT FROM v_call.output_tokens THEN
      RAISE EXCEPTION 'Assistant usage mismatch on replay' USING ERRCODE = '22023';
    END IF;
    RETURN 'duplicate';
  END IF;
  SELECT coalesce(sum(quantity), 0) INTO v_before FROM public.usage_tracking
    WHERE org_id = p_org_id AND environment = p_environment
      AND metric_type = 'ai_credits' AND period_start = v_start AND period_end = v_end;

  INSERT INTO public.usage_tracking
    (org_id, environment, metric_type, quantity, period_start, period_end,
     model_name, input_tokens, output_tokens, credits, source, source_id, idempotency_key)
  VALUES (p_org_id, p_environment, 'ai_credits', p_quantity, v_start, v_end,
          v_call.model_name, v_call.input_tokens, v_call.output_tokens,
          p_quantity, 'assistant', p_model_call_id::text, v_key)
  ON CONFLICT (org_id, idempotency_key) DO NOTHING RETURNING id INTO v_inserted;
  IF v_inserted IS NULL THEN
    -- Another writer outside this RPC inserted the same key. Treat this as
    -- uncertain until the exact row can be inspected; do not double charge.
    RAISE EXCEPTION 'Assistant usage conflict outside transaction' USING ERRCODE = '40001';
  END IF;
  IF p_included > 0 THEN
    v_overage := greatest(0, v_before + p_quantity - p_included)
      - greatest(0, v_before - p_included);
    IF v_overage > 0 THEN
      INSERT INTO public.overage_usage
        (org_id, environment, metric_type, quantity, period_start, period_end, idempotency_key)
      VALUES (p_org_id, p_environment, 'ai_credits', v_overage, v_start, v_end, v_key || ':overage');
    END IF;
  END IF;
  RETURN 'inserted';
END;
$$;

REVOKE ALL ON FUNCTION public.record_assistant_model_usage(uuid, uuid, int, int, text)
  FROM PUBLIC, anon, authenticated;
GRANT EXECUTE ON FUNCTION public.record_assistant_model_usage(uuid, uuid, int, int, text)
  TO service_role;
