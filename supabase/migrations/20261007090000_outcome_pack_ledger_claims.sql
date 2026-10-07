-- Outcome Pack platform: ledger claims, org metric semantics, capability availability.
--
-- 1. intelligence_outcome_events (the Play outcome ledger) stays append-only.
--    Two partial unique indexes make double counting impossible at the database:
--    - one counted VERIFIED SUCCESS per (org, metric, source record) claim;
--    - one decision per (ACTIONED result, metric, source record).
-- 2. org_metric_definitions gains a jsonb `definition` so an org can redefine
--    what counts for a canonical metric (for example its qualified-lead stages)
--    without code.
-- 3. connector_action_availability records provider limits observed at run
--    time (plan limit, expired auth, rate limit, outage) so the objective planner
--    replans onto an alternative provider instead of retrying a blocked one.

CREATE UNIQUE INDEX IF NOT EXISTS intelligence_outcome_events_play_claim_uniq
  ON public.intelligence_outcome_events (org_id, (metadata ->> 'claim_key'))
  WHERE outcome_event = 'play_business_result'
    AND metadata ->> 'verification_state' = 'VERIFIED SUCCESS'
    AND metadata ->> 'counted_in_total' = 'true';

CREATE UNIQUE INDEX IF NOT EXISTS intelligence_outcome_events_play_decision_uniq
  ON public.intelligence_outcome_events (org_id, (metadata ->> 'decision_key'))
  WHERE outcome_event = 'play_business_result'
    AND metadata ? 'decision_key';

CREATE INDEX IF NOT EXISTS intelligence_outcome_events_play_actioned_idx
  ON public.intelligence_outcome_events (org_id, created_at DESC)
  WHERE outcome_event = 'play_business_result'
    AND metadata ->> 'verification_state' = 'ACTIONED';

CREATE INDEX IF NOT EXISTS intelligence_outcome_events_play_metadata_gin
  ON public.intelligence_outcome_events USING gin (metadata jsonb_path_ops)
  WHERE outcome_event = 'play_business_result';

ALTER TABLE public.org_metric_definitions
  ADD COLUMN IF NOT EXISTS definition jsonb NOT NULL DEFAULT '{}'::jsonb;

CREATE TABLE IF NOT EXISTS public.connector_action_availability (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id uuid NOT NULL REFERENCES public.organizations(id) ON DELETE CASCADE,
  vendor text NOT NULL,
  action text NOT NULL DEFAULT '*',
  state text NOT NULL,
  reason text,
  observed_at timestamptz NOT NULL DEFAULT now(),
  expires_at timestamptz,
  UNIQUE (org_id, vendor, action)
);

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint
    WHERE conname = 'connector_action_availability_state_check'
      AND conrelid = 'public.connector_action_availability'::regclass
  ) THEN
    ALTER TABLE public.connector_action_availability
      ADD CONSTRAINT connector_action_availability_state_check
      CHECK (state IN ('plan_limit', 'auth_expired', 'permission_denied', 'rate_limited', 'unhealthy', 'available'));
  END IF;
END;
$$;

CREATE INDEX IF NOT EXISTS connector_action_availability_org_idx
  ON public.connector_action_availability (org_id, vendor);

ALTER TABLE public.connector_action_availability ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS connector_action_availability_org_scope
  ON public.connector_action_availability;
CREATE POLICY connector_action_availability_org_scope
  ON public.connector_action_availability
  FOR ALL
  TO authenticated
  USING (
    org_id IN (
      SELECT om.org_id
      FROM public.organization_members om
      WHERE om.user_id = (SELECT auth.uid())
    )
  )
  WITH CHECK (
    org_id IN (
      SELECT om.org_id
      FROM public.organization_members om
      WHERE om.user_id = (SELECT auth.uid())
    )
  );
