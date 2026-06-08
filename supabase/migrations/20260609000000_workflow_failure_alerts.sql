-- STA-122: Predictive workflow failure alerts (auth expiry, rate limits, missing scopes)

CREATE TABLE IF NOT EXISTS public.workflow_failure_alerts (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id uuid NOT NULL REFERENCES public.organizations(id) ON DELETE CASCADE,
  workflow_id uuid NOT NULL REFERENCES public.workflow_defs(id) ON DELETE CASCADE,
  step_id text,
  connector_id uuid REFERENCES public.connectors(id) ON DELETE SET NULL,
  alert_type text NOT NULL,
  severity text NOT NULL,
  title text NOT NULL,
  message text NOT NULL,
  evidence jsonb NOT NULL DEFAULT '{}'::jsonb,
  confidence numeric,
  status text NOT NULL DEFAULT 'open',
  predicted_at timestamptz NOT NULL DEFAULT now(),
  dismissed_at timestamptz,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint
    WHERE conname = 'workflow_failure_alerts_alert_type_check'
      AND conrelid = 'public.workflow_failure_alerts'::regclass
  ) THEN
    ALTER TABLE public.workflow_failure_alerts
      ADD CONSTRAINT workflow_failure_alerts_alert_type_check
      CHECK (alert_type IN (
        'auth_expiry',
        'auth_disconnected',
        'rate_limit_trend',
        'missing_scope',
        'step_failure_risk',
        'connector_missing'
      ));
  END IF;
END;
$$;

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint
    WHERE conname = 'workflow_failure_alerts_severity_check'
      AND conrelid = 'public.workflow_failure_alerts'::regclass
  ) THEN
    ALTER TABLE public.workflow_failure_alerts
      ADD CONSTRAINT workflow_failure_alerts_severity_check
      CHECK (severity IN ('low', 'medium', 'high', 'critical'));
  END IF;
END;
$$;

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint
    WHERE conname = 'workflow_failure_alerts_status_check'
      AND conrelid = 'public.workflow_failure_alerts'::regclass
  ) THEN
    ALTER TABLE public.workflow_failure_alerts
      ADD CONSTRAINT workflow_failure_alerts_status_check
      CHECK (status IN ('open', 'dismissed', 'resolved'));
  END IF;
END;
$$;

CREATE INDEX IF NOT EXISTS idx_workflow_failure_alerts_org
  ON public.workflow_failure_alerts (org_id, status, predicted_at DESC);

CREATE INDEX IF NOT EXISTS idx_workflow_failure_alerts_workflow
  ON public.workflow_failure_alerts (workflow_id, status, predicted_at DESC);

ALTER TABLE public.workflow_failure_alerts ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "workflow_failure_alerts_org_scope" ON public.workflow_failure_alerts;
CREATE POLICY "workflow_failure_alerts_org_scope"
  ON public.workflow_failure_alerts FOR ALL
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

DROP TRIGGER IF EXISTS trg_workflow_failure_alerts_updated_at ON public.workflow_failure_alerts;
CREATE TRIGGER trg_workflow_failure_alerts_updated_at
BEFORE UPDATE ON public.workflow_failure_alerts
FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();

COMMENT ON TABLE public.workflow_failure_alerts IS
  'Heuristic pre-failure alerts for workflows — auth, rate limits, scopes (STA-122).';
