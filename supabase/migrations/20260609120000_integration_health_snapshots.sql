-- STA-124: Customer integration health score snapshots (CS dashboard)

CREATE TABLE IF NOT EXISTS public.integration_health_snapshots (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id uuid NOT NULL REFERENCES public.organizations(id) ON DELETE CASCADE,
  score integer NOT NULL,
  grade text NOT NULL,
  dimensions jsonb NOT NULL DEFAULT '{}'::jsonb,
  risks jsonb NOT NULL DEFAULT '[]'::jsonb,
  lookback_days integer NOT NULL DEFAULT 30,
  recorded_at timestamptz NOT NULL DEFAULT now()
);

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint
    WHERE conname = 'integration_health_snapshots_grade_check'
      AND conrelid = 'public.integration_health_snapshots'::regclass
  ) THEN
    ALTER TABLE public.integration_health_snapshots
      ADD CONSTRAINT integration_health_snapshots_grade_check
      CHECK (grade IN ('healthy', 'at_risk', 'critical'));
  END IF;
END;
$$;

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint
    WHERE conname = 'integration_health_snapshots_score_check'
      AND conrelid = 'public.integration_health_snapshots'::regclass
  ) THEN
    ALTER TABLE public.integration_health_snapshots
      ADD CONSTRAINT integration_health_snapshots_score_check
      CHECK (score >= 0 AND score <= 100);
  END IF;
END;
$$;

CREATE INDEX IF NOT EXISTS idx_integration_health_snapshots_org
  ON public.integration_health_snapshots (org_id, recorded_at DESC);

ALTER TABLE public.integration_health_snapshots ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "integration_health_snapshots_org_scope" ON public.integration_health_snapshots;
CREATE POLICY "integration_health_snapshots_org_scope"
  ON public.integration_health_snapshots FOR ALL
  USING (
    org_id IN (
      SELECT org_id
      FROM public.organization_members
      WHERE user_id = auth.uid()
    )
  )
  WITH CHECK (
    org_id IN (
      SELECT org_id
      FROM public.organization_members
      WHERE user_id = auth.uid()
    )
  );

COMMENT ON TABLE public.integration_health_snapshots IS
  'Composite integration health score snapshots for CS dashboards (STA-124).';
