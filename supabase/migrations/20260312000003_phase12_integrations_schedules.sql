-- Phase 12: Integrations + schedules

CREATE TABLE public.workflow_schedules (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id uuid NOT NULL REFERENCES public.organizations(id) ON DELETE CASCADE,
  workflow_id uuid NOT NULL REFERENCES public.workflow_defs(id) ON DELETE CASCADE,
  environment text NOT NULL DEFAULT 'default',
  cron_expression text NOT NULL,
  enabled boolean NOT NULL DEFAULT true,
  next_run_at timestamptz,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  created_by uuid REFERENCES auth.users(id) ON DELETE SET NULL,
  updated_by uuid REFERENCES auth.users(id) ON DELETE SET NULL
);

CREATE INDEX idx_workflow_schedules_org_id ON public.workflow_schedules(org_id);
CREATE INDEX idx_workflow_schedules_workflow_id ON public.workflow_schedules(workflow_id);
CREATE INDEX idx_workflow_schedules_org_env ON public.workflow_schedules(org_id, environment);

ALTER TABLE public.workflow_schedules ENABLE ROW LEVEL SECURITY;

CREATE POLICY "workflow_schedules_org"
  ON public.workflow_schedules FOR ALL
  USING (org_id = (SELECT org_id FROM public.organization_members WHERE user_id = auth.uid() LIMIT 1));

ALTER TABLE public.workflow_runs
  ADD COLUMN IF NOT EXISTS trigger_type text NOT NULL DEFAULT 'manual';

ALTER TABLE public.workflow_runs
  DROP CONSTRAINT IF EXISTS workflow_runs_trigger_type_check;

ALTER TABLE public.workflow_runs
  ADD CONSTRAINT workflow_runs_trigger_type_check
  CHECK (trigger_type IN ('manual', 'schedule', 'rollback'));

ALTER TABLE public.workflow_runs
  ADD COLUMN IF NOT EXISTS schedule_id uuid REFERENCES public.workflow_schedules(id) ON DELETE SET NULL;

ALTER TABLE public.workflow_runs
  ADD COLUMN IF NOT EXISTS rollback_of_run_id uuid REFERENCES public.workflow_runs(id) ON DELETE SET NULL;
