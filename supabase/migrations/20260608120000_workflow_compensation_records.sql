-- STA-107: Compensating transactions for workflow tool actions

CREATE TABLE IF NOT EXISTS public.workflow_compensation_records (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id uuid NOT NULL REFERENCES public.organizations(id) ON DELETE CASCADE,
  run_id uuid NOT NULL REFERENCES public.workflow_runs(id) ON DELETE CASCADE,
  step_id text,
  forward_action text NOT NULL,
  compensating_action text NOT NULL,
  connector_id uuid REFERENCES public.connectors(id) ON DELETE SET NULL,
  forward_params jsonb NOT NULL DEFAULT '{}'::jsonb,
  compensating_params jsonb NOT NULL DEFAULT '{}'::jsonb,
  status text NOT NULL DEFAULT 'pending'
    CHECK (status IN ('pending', 'compensated', 'failed', 'skipped')),
  error_message text,
  created_at timestamptz NOT NULL DEFAULT now(),
  compensated_at timestamptz
);

CREATE INDEX IF NOT EXISTS idx_workflow_compensation_run
  ON public.workflow_compensation_records (org_id, run_id, status);

ALTER TABLE public.workflow_compensation_records ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "workflow_compensation_records_org" ON public.workflow_compensation_records;
CREATE POLICY "workflow_compensation_records_org"
  ON public.workflow_compensation_records FOR ALL
  USING (org_id = (SELECT org_id FROM public.organization_members WHERE user_id = auth.uid() LIMIT 1));
