-- Phase 6: DB-backed connector rate limits (distributed-safe)

CREATE TABLE public.connector_rate_limits (
  org_id uuid NOT NULL REFERENCES public.organizations(id) ON DELETE CASCADE,
  step_type text NOT NULL,
  connector_type text NOT NULL,
  connector_id uuid NOT NULL REFERENCES public.connectors(id) ON DELETE CASCADE,
  capacity numeric NOT NULL,
  refill_per_sec numeric NOT NULL,
  tokens numeric NOT NULL,
  last_refill timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (org_id, step_type, connector_type, connector_id)
);

CREATE INDEX idx_connector_rate_limits_org ON public.connector_rate_limits(org_id);

ALTER TABLE public.connector_rate_limits ENABLE ROW LEVEL SECURITY;

CREATE POLICY "connector_rate_limits_org"
  ON public.connector_rate_limits FOR ALL
  USING (org_id = (SELECT org_id FROM public.organization_members WHERE user_id = auth.uid() LIMIT 1));

CREATE OR REPLACE FUNCTION public.consume_connector_token(
  p_org_id uuid,
  p_step_type text,
  p_connector_type text,
  p_connector_id uuid,
  p_capacity numeric,
  p_refill_per_sec numeric
)
RETURNS boolean
LANGUAGE plpgsql
AS $$
DECLARE
  v_now timestamptz := now();
  v_tokens numeric;
  v_last_refill timestamptz;
  v_allowed boolean := false;
BEGIN
  INSERT INTO public.connector_rate_limits (
    org_id, step_type, connector_type, connector_id,
    capacity, refill_per_sec, tokens, last_refill, updated_at
  )
  VALUES (
    p_org_id, p_step_type, p_connector_type, p_connector_id,
    p_capacity, p_refill_per_sec, p_capacity, v_now, v_now
  )
  ON CONFLICT (org_id, step_type, connector_type, connector_id) DO NOTHING;

  SELECT tokens, last_refill
    INTO v_tokens, v_last_refill
  FROM public.connector_rate_limits
  WHERE org_id = p_org_id
    AND step_type = p_step_type
    AND connector_type = p_connector_type
    AND connector_id = p_connector_id
  FOR UPDATE;

  v_tokens := LEAST(p_capacity, v_tokens + (EXTRACT(EPOCH FROM (v_now - v_last_refill)) * p_refill_per_sec));
  IF v_tokens >= 1 THEN
    v_tokens := v_tokens - 1;
    v_allowed := true;
  END IF;

  UPDATE public.connector_rate_limits
    SET tokens = v_tokens,
        last_refill = v_now,
        capacity = p_capacity,
        refill_per_sec = p_refill_per_sec,
        updated_at = v_now
  WHERE org_id = p_org_id
    AND step_type = p_step_type
    AND connector_type = p_connector_type
    AND connector_id = p_connector_id;

  RETURN v_allowed;
END;
$$;
