-- SaaS schedules: one-shot + recurring + timezone on workflow_schedules

ALTER TABLE public.workflow_schedules
  ADD COLUMN IF NOT EXISTS timezone text NOT NULL DEFAULT 'UTC',
  ADD COLUMN IF NOT EXISTS schedule_type text NOT NULL DEFAULT 'recurring',
  ADD COLUMN IF NOT EXISTS run_at timestamptz,
  ADD COLUMN IF NOT EXISTS name text,
  ADD COLUMN IF NOT EXISTS ends_at timestamptz;

ALTER TABLE public.workflow_schedules
  DROP CONSTRAINT IF EXISTS workflow_schedules_schedule_type_check;

ALTER TABLE public.workflow_schedules
  ADD CONSTRAINT workflow_schedules_schedule_type_check
  CHECK (schedule_type IN ('recurring', 'once'));

-- One-shot rows may use the @once sentinel; keep cron_expression NOT NULL for legacy clients.
COMMENT ON COLUMN public.workflow_schedules.timezone IS 'IANA timezone for cron evaluation (recurring) and display';
COMMENT ON COLUMN public.workflow_schedules.schedule_type IS 'recurring = cron; once = single fire at run_at';
COMMENT ON COLUMN public.workflow_schedules.run_at IS 'Absolute fire time for schedule_type=once';
COMMENT ON COLUMN public.workflow_schedules.ends_at IS 'Optional end bound for recurring schedules';

CREATE INDEX IF NOT EXISTS idx_workflow_schedules_type
  ON public.workflow_schedules (org_id, schedule_type)
  WHERE enabled = true;
