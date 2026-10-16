-- Durable Stripe meter intents. NEW migration: do not modify historical applied SQL.
-- Explicitly requires operator approval before applying to production.
CREATE TABLE IF NOT EXISTS public.stripe_meter_outbox (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id uuid NOT NULL REFERENCES public.organizations(id) ON DELETE CASCADE,
  environment text NOT NULL CHECK (environment = 'production'),
  metric_type text NOT NULL CHECK (metric_type IN ('ai_credits', 'research_lookups', 'voice_minutes')),
  source_id uuid NOT NULL,
  period_start date NOT NULL,
  period_end date NOT NULL,
  included_snapshot integer NOT NULL DEFAULT 0 CHECK (included_snapshot >= 0),
  quantity integer NOT NULL CHECK (quantity >= 0),
  event_identifier text NOT NULL UNIQUE,
  status text NOT NULL DEFAULT 'pending' CHECK (status IN ('pending','sending','delivered','ambiguous','zero')),
  claim_token uuid,
  claimed_at timestamptz,
  delivered_at timestamptz,
  attempt_count integer NOT NULL DEFAULT 0,
  created_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (org_id, environment, metric_type, source_id),
  CHECK (period_end >= period_start)
);
CREATE INDEX IF NOT EXISTS idx_stripe_meter_outbox_pending
  ON public.stripe_meter_outbox (org_id, metric_type, status, created_at);
ALTER TABLE public.stripe_meter_outbox ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON public.stripe_meter_outbox FROM PUBLIC, anon, authenticated;
GRANT SELECT, INSERT, UPDATE ON public.stripe_meter_outbox TO service_role;

-- Stage independently of external Stripe calls, under a shared transaction lock.
-- The global period allowance is snapshotted and inconsistent later plan changes are rejected.
CREATE OR REPLACE FUNCTION public.stage_stripe_meter_intents(
  p_org_id uuid, p_metric text, p_period_start date, p_period_end date,
  p_included integer DEFAULT 0
) RETURNS integer
LANGUAGE plpgsql SECURITY INVOKER SET search_path = ''
AS $$
DECLARE
  v_rows integer := 0;
BEGIN
  IF p_org_id IS NULL OR p_metric NOT IN ('ai_credits','research_lookups','voice_minutes')
     OR p_period_end < p_period_start OR p_included < 0 THEN
    RAISE EXCEPTION 'invalid_meter_intent_request';
  END IF;
  PERFORM pg_catalog.pg_advisory_xact_lock(pg_catalog.hashtextextended(
      p_org_id::text || ':' || p_metric || ':' || p_period_start::text, 0));
  IF EXISTS (
    SELECT 1 FROM public.stripe_meter_outbox
    WHERE org_id=p_org_id AND metric_type=p_metric AND period_start=p_period_start
      AND period_end=p_period_end AND included_snapshot<>p_included
  ) THEN
    RAISE EXCEPTION 'stripe_meter_allowance_changed_requires_reconciliation';
  END IF;
  -- Never rebill rows already sent by the legacy batch reporter. The
  -- cutover must start from an empty/unreported period or be reconciled by
  -- an explicit operator-approved migration of Stripe acceptance evidence.
  IF p_metric='ai_credits' AND EXISTS (
    SELECT 1 FROM public.usage_tracking u
    WHERE u.org_id=p_org_id AND u.environment='production'
      AND u.metric_type='ai_credits' AND u.period_start=p_period_start
      AND u.period_end=p_period_end AND u.stripe_reported_at IS NOT NULL
      AND NOT EXISTS (
        SELECT 1 FROM public.stripe_meter_outbox o
        WHERE o.org_id=u.org_id AND o.metric_type='ai_credits' AND o.source_id=u.id
      )
  ) THEN
    RAISE EXCEPTION 'stripe_meter_legacy_crossover_requires_reconciliation';
  END IF;
  IF p_metric<>'ai_credits' AND EXISTS (
    SELECT 1 FROM public.usage_records r
    WHERE r.org_id=p_org_id AND r.metric_type=p_metric
      AND r.recorded_at >= p_period_start::timestamp AT TIME ZONE 'UTC'
      AND r.recorded_at < (p_period_end+1)::timestamp AT TIME ZONE 'UTC'
      AND r.stripe_reported_at IS NOT NULL
      AND NOT EXISTS (
        SELECT 1 FROM public.stripe_meter_outbox o
        WHERE o.org_id=r.org_id AND o.metric_type=p_metric AND o.source_id=r.id
      )
  ) THEN
    RAISE EXCEPTION 'stripe_meter_legacy_crossover_requires_reconciliation';
  END IF;
  IF p_metric = 'ai_credits' THEN
    INSERT INTO public.stripe_meter_outbox(
       org_id,environment,metric_type,source_id,period_start,period_end,
       included_snapshot,quantity,event_identifier,status)
    SELECT u.org_id,'production','ai_credits',u.id,p_period_start,p_period_end,
           p_included,u.quantity,
           'gv_'||md5(p_org_id::text||':ai_credits:'||u.id::text),
           CASE WHEN u.quantity = 0 THEN 'zero' ELSE 'pending' END
      FROM public.usage_tracking u
     WHERE u.org_id=p_org_id AND u.metric_type='ai_credits'
       AND u.environment='production' AND u.period_start=p_period_start
       AND u.period_end=p_period_end AND u.stripe_reported_at IS NULL
    ON CONFLICT (org_id,environment,metric_type,source_id) DO NOTHING;
    GET DIAGNOSTICS v_rows = ROW_COUNT;
  ELSE
    -- The ordering includes every usage record in the period, even records
    -- already delivered, preventing included units from being charged twice.
    WITH ordered AS (
      SELECT r.id, r.org_id, r.quantity, r.recorded_at,
             SUM(r.quantity) OVER (ORDER BY r.recorded_at,r.id
               ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) AS cumulative
      FROM public.usage_records r
      WHERE r.org_id=p_org_id AND r.metric_type=p_metric
        AND r.recorded_at >= p_period_start::timestamp AT TIME ZONE 'UTC'
        AND r.recorded_at < (p_period_end+1)::timestamp AT TIME ZONE 'UTC'
    ), deltas AS (
      SELECT *, GREATEST(cumulative-p_included,0)
                -GREATEST(cumulative-quantity-p_included,0) AS billable
      FROM ordered
    )
    INSERT INTO public.stripe_meter_outbox(
      org_id,environment,metric_type,source_id,period_start,period_end,
      included_snapshot,quantity,event_identifier,status)
    SELECT d.org_id,'production',p_metric,d.id,p_period_start,p_period_end,
           p_included,d.billable,
           'gv_'||md5(p_org_id::text||':'||p_metric||':'||d.id::text),
           CASE WHEN d.billable=0 THEN 'zero' ELSE 'pending' END
    FROM deltas d
    WHERE NOT EXISTS (
      SELECT 1 FROM public.stripe_meter_outbox o
      WHERE o.org_id=p_org_id AND o.metric_type=p_metric AND o.source_id=d.id
    )
    ON CONFLICT (org_id,environment,metric_type,source_id) DO NOTHING;
    GET DIAGNOSTICS v_rows = ROW_COUNT;
  END IF;
  -- Zero-charge sources need no Stripe event and can be marked as processed.
  UPDATE public.usage_tracking u SET stripe_reported_at=now()
    FROM public.stripe_meter_outbox o
   WHERE p_metric='ai_credits' AND o.org_id=p_org_id AND o.metric_type=p_metric
     AND o.period_start=p_period_start AND o.status='zero' AND u.id=o.source_id
     AND u.stripe_reported_at IS NULL;
  UPDATE public.usage_records r SET stripe_reported_at=now()
    FROM public.stripe_meter_outbox o
   WHERE p_metric<>'ai_credits' AND o.org_id=p_org_id AND o.metric_type=p_metric
     AND o.period_start=p_period_start AND o.status='zero' AND r.id=o.source_id
     AND r.stripe_reported_at IS NULL;
  RETURN v_rows;
END;
$$;

CREATE OR REPLACE FUNCTION public.claim_stripe_meter_intents(
  p_org_id uuid,p_metric text,p_limit integer DEFAULT 100
) RETURNS SETOF public.stripe_meter_outbox
LANGUAGE plpgsql SECURITY INVOKER SET search_path = ''
AS $$
BEGIN
  IF p_org_id IS NULL OR p_metric NOT IN ('ai_credits','research_lookups','voice_minutes')
     OR p_limit NOT BETWEEN 1 AND 100 THEN
    RAISE EXCEPTION 'invalid_meter_claim_request';
  END IF;
  RETURN QUERY WITH claimed AS (
    SELECT id FROM public.stripe_meter_outbox
    WHERE org_id=p_org_id AND metric_type=p_metric AND status='pending'
    ORDER BY created_at,id LIMIT p_limit FOR UPDATE SKIP LOCKED
  )
  UPDATE public.stripe_meter_outbox o
  SET status='sending',claim_token=gen_random_uuid(),claimed_at=now(),
      attempt_count=attempt_count+1
  FROM claimed c WHERE o.id=c.id RETURNING o.*;
END;
$$;

-- A successful Stripe response and local source-mark must commit together.
CREATE OR REPLACE FUNCTION public.ack_stripe_meter_intent(
  p_id uuid,p_claim_token uuid
) RETURNS boolean
LANGUAGE plpgsql SECURITY INVOKER SET search_path = ''
AS $$
DECLARE v public.stripe_meter_outbox%ROWTYPE;
BEGIN
  UPDATE public.stripe_meter_outbox o
     SET status='delivered',delivered_at=now(),claim_token=NULL
   WHERE o.id=p_id AND o.claim_token=p_claim_token AND o.status='sending'
   RETURNING * INTO v;
  IF NOT FOUND THEN RETURN false; END IF;
  IF v.metric_type='ai_credits' THEN
    UPDATE public.usage_tracking SET stripe_reported_at=now() WHERE id=v.source_id AND org_id=v.org_id;
  ELSE
    UPDATE public.usage_records SET stripe_reported_at=now() WHERE id=v.source_id AND org_id=v.org_id;
  END IF;
  RETURN true;
END;
$$;

-- Ambiguous network failures must not be automatically replayed, even when
-- Stripe's server-side deduplication window expires.
CREATE OR REPLACE FUNCTION public.mark_stripe_meter_ambiguous(
  p_id uuid,p_claim_token uuid
) RETURNS boolean
LANGUAGE sql SECURITY INVOKER SET search_path = ''
AS $$
  WITH changed AS (
    UPDATE public.stripe_meter_outbox
    SET status='ambiguous',claim_token=NULL
    WHERE id=p_id AND claim_token=p_claim_token AND status='sending'
    RETURNING id
  ) SELECT EXISTS(SELECT 1 FROM changed);
$$;

REVOKE ALL ON FUNCTION public.stage_stripe_meter_intents(uuid,text,date,date,integer) FROM PUBLIC, anon, authenticated;
REVOKE ALL ON FUNCTION public.claim_stripe_meter_intents(uuid,text,integer) FROM PUBLIC, anon, authenticated;
REVOKE ALL ON FUNCTION public.ack_stripe_meter_intent(uuid,uuid) FROM PUBLIC, anon, authenticated;
REVOKE ALL ON FUNCTION public.mark_stripe_meter_ambiguous(uuid,uuid) FROM PUBLIC, anon, authenticated;
GRANT EXECUTE ON FUNCTION public.stage_stripe_meter_intents(uuid,text,date,date,integer) TO service_role;
GRANT EXECUTE ON FUNCTION public.claim_stripe_meter_intents(uuid,text,integer) TO service_role;
GRANT EXECUTE ON FUNCTION public.ack_stripe_meter_intent(uuid,uuid) TO service_role;
GRANT EXECUTE ON FUNCTION public.mark_stripe_meter_ambiguous(uuid,uuid) TO service_role;
