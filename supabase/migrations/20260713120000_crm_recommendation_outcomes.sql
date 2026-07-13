-- Item 4: durable CRM outcome labels for future learning (no ML in this pass).
-- Capture contacted / replied / booked / won / lost against ICP or recommendation context.

CREATE TABLE IF NOT EXISTS public.crm_recommendation_outcomes (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id uuid NOT NULL REFERENCES public.organizations(id) ON DELETE CASCADE,
  outcome_type text NOT NULL CHECK (outcome_type IN (
    'contacted',
    'replied',
    'booked',
    'won',
    'lost'
  )),
  connector_type text,
  external_record_id text,
  recommendation_id text,
  icp_score numeric,
  metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
  occurred_at timestamptz NOT NULL DEFAULT now(),
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_crm_recommendation_outcomes_org_occurred
  ON public.crm_recommendation_outcomes (org_id, occurred_at DESC);

CREATE INDEX IF NOT EXISTS idx_crm_recommendation_outcomes_org_type
  ON public.crm_recommendation_outcomes (org_id, outcome_type);

ALTER TABLE public.crm_recommendation_outcomes ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "crm_recommendation_outcomes_org_scope"
  ON public.crm_recommendation_outcomes;
CREATE POLICY "crm_recommendation_outcomes_org_scope"
  ON public.crm_recommendation_outcomes FOR ALL
  USING (
    org_id IN (
      SELECT organization_members.org_id
      FROM public.organization_members
      WHERE organization_members.user_id = auth.uid()
    )
  )
  WITH CHECK (
    org_id IN (
      SELECT organization_members.org_id
      FROM public.organization_members
      WHERE organization_members.user_id = auth.uid()
    )
  );

COMMENT ON TABLE public.crm_recommendation_outcomes IS
  'Item 4: labeled CRM outcomes for future learning; ingest only from real connector/sync events — no synthetic labels.';
