-- Company intelligence learning loop snapshots and run logs

CREATE TABLE IF NOT EXISTS public.org_intelligence_snapshots (
  org_id uuid PRIMARY KEY REFERENCES public.organizations(id) ON DELETE CASCADE,
  context_markdown text NOT NULL DEFAULT '',
  signals_json jsonb NOT NULL DEFAULT '{}'::jsonb,
  intent_model_id uuid REFERENCES public.trained_models(id) ON DELETE SET NULL,
  anomaly_model_id uuid REFERENCES public.trained_models(id) ON DELETE SET NULL,
  forecaster_model_id uuid REFERENCES public.trained_models(id) ON DELETE SET NULL,
  success_model_id uuid REFERENCES public.trained_models(id) ON DELETE SET NULL,
  source_counts jsonb NOT NULL DEFAULT '{}'::jsonb,
  updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS public.org_intelligence_runs (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id uuid NOT NULL REFERENCES public.organizations(id) ON DELETE CASCADE,
  status text NOT NULL CHECK (status IN ('running', 'completed', 'failed', 'skipped')),
  stats_json jsonb NOT NULL DEFAULT '{}'::jsonb,
  error text,
  started_at timestamptz NOT NULL DEFAULT now(),
  completed_at timestamptz
);

CREATE INDEX IF NOT EXISTS idx_org_intelligence_runs_org_started
  ON public.org_intelligence_runs (org_id, started_at DESC);

ALTER TABLE public.org_intelligence_snapshots ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.org_intelligence_runs ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS org_intelligence_snapshots_isolation ON public.org_intelligence_snapshots;
CREATE POLICY org_intelligence_snapshots_isolation
  ON public.org_intelligence_snapshots FOR ALL
  USING (
    org_id IN (
      SELECT org_id FROM public.organization_members WHERE user_id = auth.uid()
    )
  );

DROP POLICY IF EXISTS org_intelligence_runs_isolation ON public.org_intelligence_runs;
CREATE POLICY org_intelligence_runs_isolation
  ON public.org_intelligence_runs FOR ALL
  USING (
    org_id IN (
      SELECT org_id FROM public.organization_members WHERE user_id = auth.uid()
    )
  );

COMMENT ON TABLE public.org_intelligence_snapshots IS
  'Latest synthesized company-intelligence markdown injected into agent prompts.';
COMMENT ON TABLE public.org_intelligence_runs IS
  'Append-only log of company intelligence orchestrator executions per org.';
