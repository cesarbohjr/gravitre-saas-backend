-- Serialize allowance-bearing usage from every app writer with the assistant
-- model-call RPC. Expand-only; existing ledger rows are never rewritten.
-- Preflight: verify 20260531000000, 20260531000100 and 20261015032117
-- are applied; inspect privileges and unique indexes for both ledger tables.
-- Staging acceptance: concurrent generic + assistant writers, duplicate and
-- changed-payload replay, rollback after overage failure, service-role grants.
-- Rollback: DROP FUNCTION public.record_usage_with_overage_atomic(
--   uuid, text, text, int, date, date, int, text, text, int, int, int, text, text);

CREATE FUNCTION public.record_usage_with_overage_atomic(
  p_org_id uuid, p_environment text, p_metric_type text, p_quantity int,
  p_period_start date, p_period_end date, p_included int,
  p_idempotency_key text, p_model_name text DEFAULT NULL,
  p_input_tokens int DEFAULT NULL, p_output_tokens int DEFAULT NULL,
  p_credits int DEFAULT NULL, p_source text DEFAULT NULL,
  p_source_id text DEFAULT NULL
) RETURNS text
LANGUAGE plpgsql SECURITY INVOKER SET search_path = ''
AS $$
DECLARE
  v_before bigint;
  v_overage bigint;
  v_existing public.usage_tracking%ROWTYPE;
  v_inserted uuid;
BEGIN
  IF p_org_id IS NULL OR p_environment IS NULL OR p_environment = ''
     OR p_metric_type NOT IN ('ai_credits', 'workflow_runs', 'operator_usage', 'rag_usage')
     OR p_metric_type IS NULL OR p_quantity IS NULL OR p_quantity <= 0
     OR p_period_start IS NULL OR p_period_end IS NULL
     OR p_period_end < p_period_start OR p_included IS NULL OR p_included < 0
     OR p_idempotency_key IS NULL OR p_idempotency_key = ''
     OR (p_metric_type NOT IN ('ai_credits', 'workflow_runs') AND p_included > 0) THEN
    RAISE EXCEPTION 'Invalid usage billing arguments' USING ERRCODE = '22023';
  END IF;

  -- Identical key to record_assistant_model_usage, including UTC period.
  PERFORM pg_catalog.pg_advisory_xact_lock(
    pg_catalog.hashtextextended(
      p_org_id::text || ':' || p_metric_type || ':' || p_environment || ':' || p_period_start::text, 0)
  );
  SELECT * INTO v_existing FROM public.usage_tracking
    WHERE org_id = p_org_id AND idempotency_key = p_idempotency_key;
  IF FOUND THEN
    IF v_existing.environment IS DISTINCT FROM p_environment
       OR v_existing.metric_type IS DISTINCT FROM p_metric_type
       OR v_existing.quantity IS DISTINCT FROM p_quantity
       OR v_existing.period_start IS DISTINCT FROM p_period_start
       OR v_existing.period_end IS DISTINCT FROM p_period_end
       OR v_existing.model_name IS DISTINCT FROM p_model_name
       OR v_existing.input_tokens IS DISTINCT FROM p_input_tokens
       OR v_existing.output_tokens IS DISTINCT FROM p_output_tokens
       OR v_existing.credits IS DISTINCT FROM p_credits
       OR v_existing.source IS DISTINCT FROM p_source
       OR v_existing.source_id IS DISTINCT FROM p_source_id THEN
      RAISE EXCEPTION 'Usage mismatch on replay' USING ERRCODE = '22023';
    END IF;
    RETURN 'duplicate';
  END IF;

  SELECT coalesce(sum(quantity), 0) INTO v_before FROM public.usage_tracking
    WHERE org_id = p_org_id AND environment = p_environment
      AND metric_type = p_metric_type AND period_start = p_period_start
      AND period_end = p_period_end;
  INSERT INTO public.usage_tracking
    (org_id, environment, metric_type, quantity, period_start, period_end,
     model_name, input_tokens, output_tokens, credits, source, source_id, idempotency_key)
  VALUES (p_org_id, p_environment, p_metric_type, p_quantity, p_period_start, p_period_end,
          p_model_name, p_input_tokens, p_output_tokens, p_credits, p_source,
          p_source_id, p_idempotency_key)
  ON CONFLICT (org_id, idempotency_key) DO NOTHING RETURNING id INTO v_inserted;
  IF v_inserted IS NULL THEN
    RAISE EXCEPTION 'Usage conflict outside transaction' USING ERRCODE = '40001';
  END IF;
  IF p_included > 0 THEN
    v_overage := greatest(0::bigint, v_before + p_quantity - p_included)
      - greatest(0::bigint, v_before - p_included);
    IF v_overage > 0 THEN
      INSERT INTO public.overage_usage
        (org_id, environment, metric_type, quantity, period_start, period_end, idempotency_key)
      VALUES (p_org_id, p_environment, p_metric_type, v_overage::int,
              p_period_start, p_period_end, p_idempotency_key || ':overage');
    END IF;
  END IF;
  RETURN 'inserted';
END;
$$;

REVOKE ALL ON FUNCTION public.record_usage_with_overage_atomic(
  uuid, text, text, int, date, date, int, text, text, int, int, int, text, text)
  FROM PUBLIC, anon, authenticated;
GRANT EXECUTE ON FUNCTION public.record_usage_with_overage_atomic(
  uuid, text, text, int, date, date, int, text, text, int, int, int, text, text)
  TO service_role;
