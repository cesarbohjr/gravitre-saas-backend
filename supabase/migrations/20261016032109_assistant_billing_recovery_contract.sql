-- Durable assistant billing evidence, extending model_calls and the usage ledger.
-- Preflight: 20261013080000, 20261015032117 and 20261015222156 must be applied;
-- inspect model_calls member write policies and any direct client writers first.
-- No historical rows are tagged or charged. New recovery flag defaults off.
-- Stage: concurrent settlement, allowance mismatch, rollback, poison backoff,
-- grants and model-call mutation denial. Exact production approval required.
-- Rollback: turn ASSISTANT_BILLING_RECOVERY_ENABLED off first; leave expand-only
-- columns/table in place pending a separately reviewed cleanup migration.

ALTER TABLE public.model_calls
  ADD COLUMN billing_credits int CHECK (billing_credits >= 0),
  ADD COLUMN billing_included int CHECK (billing_included >= 0),
  ADD COLUMN billing_environment text,
  ADD COLUMN billing_settled_at timestamptz,
  ADD COLUMN billing_attempts int NOT NULL DEFAULT 0,
  ADD COLUMN billing_retry_at timestamptz NOT NULL DEFAULT now(),
  ADD COLUMN billing_last_error text;

-- Cost and billing evidence is server-owned. Tenant admins cannot forge charges.
DROP POLICY IF EXISTS "Org admins can manage model calls" ON public.model_calls;
REVOKE INSERT, UPDATE, DELETE, TRUNCATE ON public.model_calls FROM anon, authenticated;
GRANT SELECT, INSERT, UPDATE ON public.model_calls TO service_role;

CREATE INDEX idx_model_calls_billing_pending
  ON public.model_calls (created_at, billing_retry_at, id)
  WHERE billing_credits IS NOT NULL AND billing_settled_at IS NULL AND billing_attempts < 8;

CREATE TABLE public.billing_period_allowances (
  org_id uuid NOT NULL REFERENCES public.organizations(id) ON DELETE CASCADE,
  environment text NOT NULL,
  metric_type text NOT NULL CHECK (metric_type IN ('ai_credits', 'workflow_runs')),
  period_start date NOT NULL,
  period_end date NOT NULL,
  included int NOT NULL CHECK (included >= 0),
  created_at timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (org_id, environment, metric_type, period_start, period_end),
  CHECK (period_end >= period_start)
);
ALTER TABLE public.billing_period_allowances ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON public.billing_period_allowances FROM PUBLIC, anon, authenticated;
GRANT SELECT, INSERT ON public.billing_period_allowances TO service_role;

CREATE FUNCTION public.lock_billing_allowance(
  p_org_id uuid, p_environment text, p_metric_type text,
  p_period_start date, p_period_end date, p_included int
) RETURNS void LANGUAGE plpgsql SECURITY INVOKER SET search_path = '' AS $$
DECLARE v_included int;
BEGIN
  IF p_org_id IS NULL OR p_environment IS NULL OR p_environment = ''
     OR p_metric_type IS NULL OR p_metric_type NOT IN ('ai_credits', 'workflow_runs')
     OR p_period_start IS NULL OR p_period_end IS NULL OR p_period_end < p_period_start
     OR p_included IS NULL OR p_included < 0 THEN
    RAISE EXCEPTION 'Invalid billing allowance contract' USING ERRCODE = '22023';
  END IF;
  PERFORM pg_catalog.pg_advisory_xact_lock(pg_catalog.hashtextextended(
    p_org_id::text || ':' || p_metric_type || ':' || p_environment || ':' || p_period_start::text, 0));
  INSERT INTO public.billing_period_allowances
    (org_id, environment, metric_type, period_start, period_end, included)
  VALUES (p_org_id, p_environment, p_metric_type, p_period_start, p_period_end, p_included)
  ON CONFLICT DO NOTHING;
  SELECT included INTO v_included FROM public.billing_period_allowances
    WHERE org_id = p_org_id AND environment = p_environment AND metric_type = p_metric_type
      AND period_start = p_period_start AND period_end = p_period_end;
  IF v_included IS DISTINCT FROM p_included THEN
    RAISE EXCEPTION 'Billing allowance changed; review required' USING ERRCODE = '22023';
  END IF;
END;
$$;

CREATE FUNCTION public.record_usage_with_allowance_contract(
  p_org_id uuid, p_environment text, p_metric_type text, p_quantity int,
  p_period_start date, p_period_end date, p_included int,
  p_idempotency_key text, p_model_name text DEFAULT NULL,
  p_input_tokens int DEFAULT NULL, p_output_tokens int DEFAULT NULL,
  p_credits int DEFAULT NULL, p_source text DEFAULT NULL, p_source_id text DEFAULT NULL
) RETURNS text LANGUAGE plpgsql SECURITY INVOKER SET search_path = '' AS $$
BEGIN
  IF p_metric_type IN ('ai_credits', 'workflow_runs') THEN
    PERFORM public.lock_billing_allowance(p_org_id, p_environment, p_metric_type,
      p_period_start, p_period_end, p_included);
  END IF;
  RETURN public.record_usage_with_overage_atomic(p_org_id, p_environment, p_metric_type,
    p_quantity, p_period_start, p_period_end, p_included, p_idempotency_key,
    p_model_name, p_input_tokens, p_output_tokens, p_credits, p_source, p_source_id);
END;
$$;

CREATE FUNCTION public.settle_assistant_model_usage(p_org_id uuid, p_model_call_id uuid)
RETURNS text LANGUAGE plpgsql SECURITY INVOKER SET search_path = '' AS $$
DECLARE v_call public.model_calls%ROWTYPE; v_start date; v_end date; v_result text;
BEGIN
  SELECT * INTO v_call FROM public.model_calls
    WHERE org_id = p_org_id AND id = p_model_call_id FOR UPDATE;
  IF NOT FOUND OR v_call.turn_id IS NULL OR v_call.turn_id NOT LIKE 'assistant:%'
     OR v_call.created_at IS NULL OR v_call.billing_credits IS NULL
     OR v_call.billing_included IS NULL OR v_call.billing_environment IS NULL THEN
    RAISE EXCEPTION 'Assistant billing evidence missing' USING ERRCODE = '22023';
  END IF;
  v_start := date_trunc('month', v_call.created_at AT TIME ZONE 'UTC')::date;
  v_end := (v_start + interval '1 month' - interval '1 day')::date;
  PERFORM public.lock_billing_allowance(p_org_id, v_call.billing_environment,
    'ai_credits', v_start, v_end, v_call.billing_included);
  IF coalesce(v_call.input_tokens, 0) + coalesce(v_call.output_tokens, 0) <= 0 THEN
    IF v_call.billing_credits <> 0 THEN
      RAISE EXCEPTION 'Zero-token billing evidence mismatch' USING ERRCODE = '22023';
    END IF;
    v_result := 'zero_tokens';
  ELSE
    v_result := public.record_assistant_model_usage(p_org_id, p_model_call_id,
      v_call.billing_credits, v_call.billing_included, v_call.billing_environment);
  END IF;
  UPDATE public.model_calls SET billing_settled_at = now(), billing_last_error = NULL
    WHERE id = p_model_call_id AND org_id = p_org_id;
  RETURN v_result;
END;
$$;

CREATE FUNCTION public.recover_assistant_model_usage(p_limit int DEFAULT 100)
RETURNS jsonb LANGUAGE plpgsql SECURITY INVOKER SET search_path = '' AS $$
DECLARE v_row record; v_scanned int := 0; v_settled int := 0; v_errors int := 0;
BEGIN
  IF p_limit IS NULL OR p_limit < 1 OR p_limit > 500 THEN
    RAISE EXCEPTION 'Recovery batch must be 1..500' USING ERRCODE = '22023';
  END IF;
  -- Legacy calls have no billing contract and can never enter this sweep.
  -- Closed billing months remain an operator-reviewed reconciliation task.
  FOR v_row IN SELECT id, org_id, billing_attempts FROM public.model_calls
    WHERE billing_credits IS NOT NULL AND billing_settled_at IS NULL
      AND billing_attempts < 8 AND billing_retry_at <= now()
      AND created_at < now() - interval '10 minutes'
      AND created_at >= date_trunc('month', now() AT TIME ZONE 'UTC') AT TIME ZONE 'UTC'
    ORDER BY created_at, billing_retry_at, id LIMIT p_limit FOR UPDATE SKIP LOCKED
  LOOP
    v_scanned := v_scanned + 1;
    BEGIN
      PERFORM public.settle_assistant_model_usage(v_row.org_id, v_row.id);
      v_settled := v_settled + 1;
    EXCEPTION WHEN OTHERS THEN
      -- Subtransaction rolls back any usage insert before recording the retry.
      UPDATE public.model_calls SET billing_attempts = billing_attempts + 1,
        billing_last_error = SQLSTATE,
        billing_retry_at = now() + make_interval(secs => least(3600, 60 * (2 ^ v_row.billing_attempts)::int))
        WHERE org_id = v_row.org_id AND id = v_row.id;
      v_errors := v_errors + 1;
    END;
  END LOOP;
  RETURN jsonb_build_object('scanned', v_scanned, 'settled', v_settled, 'errors', v_errors);
END;
$$;

REVOKE ALL ON FUNCTION public.lock_billing_allowance(uuid, text, text, date, date, int)
  FROM PUBLIC, anon, authenticated;
GRANT EXECUTE ON FUNCTION public.lock_billing_allowance(uuid, text, text, date, date, int)
  TO service_role;
REVOKE ALL ON FUNCTION public.record_usage_with_allowance_contract(
  uuid, text, text, int, date, date, int, text, text, int, int, int, text, text)
  FROM PUBLIC, anon, authenticated;
GRANT EXECUTE ON FUNCTION public.record_usage_with_allowance_contract(
  uuid, text, text, int, date, date, int, text, text, int, int, int, text, text)
  TO service_role;
REVOKE ALL ON FUNCTION public.settle_assistant_model_usage(uuid, uuid)
  FROM PUBLIC, anon, authenticated;
GRANT EXECUTE ON FUNCTION public.settle_assistant_model_usage(uuid, uuid) TO service_role;
REVOKE ALL ON FUNCTION public.recover_assistant_model_usage(int) FROM PUBLIC, anon, authenticated;
GRANT EXECUTE ON FUNCTION public.recover_assistant_model_usage(int) TO service_role;
