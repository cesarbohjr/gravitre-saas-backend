-- STA-120: Workflow digital twin — connector fixtures + digital_twin run type

CREATE TABLE IF NOT EXISTS public.connector_fixtures (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id uuid NOT NULL REFERENCES public.organizations(id) ON DELETE CASCADE,
  environment text NOT NULL DEFAULT 'production',
  connector_type text NOT NULL,
  action text NOT NULL,
  label text,
  request_fingerprint jsonb NOT NULL DEFAULT '{}'::jsonb,
  response jsonb NOT NULL,
  source_run_id uuid REFERENCES public.workflow_runs(id) ON DELETE SET NULL,
  created_by uuid REFERENCES auth.users(id) ON DELETE SET NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_connector_fixtures_lookup
  ON public.connector_fixtures (org_id, environment, connector_type, action);

ALTER TABLE public.connector_fixtures ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "connector_fixtures_tenant" ON public.connector_fixtures;
CREATE POLICY "connector_fixtures_tenant"
  ON public.connector_fixtures
  FOR SELECT
  USING (
    org_id IN (SELECT om.org_id FROM public.organization_members om WHERE om.user_id = auth.uid())
  );

COMMENT ON TABLE public.connector_fixtures IS
  'Recorded connector responses for workflow digital-twin simulation (STA-120).';

ALTER TABLE public.workflow_runs DROP CONSTRAINT IF EXISTS workflow_runs_run_type_check;
ALTER TABLE public.workflow_runs
  ADD CONSTRAINT workflow_runs_run_type_check
  CHECK (run_type IN ('dry_run', 'execute', 'digital_twin'));
