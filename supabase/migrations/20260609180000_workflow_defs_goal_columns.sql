-- Align workflow_defs with list_workflows / builder API (legacy phase16 columns).

ALTER TABLE public.workflow_defs
  ADD COLUMN IF NOT EXISTS goal text,
  ADD COLUMN IF NOT EXISTS stage text NOT NULL DEFAULT 'build',
  ADD COLUMN IF NOT EXISTS next_run_at timestamptz;

COMMENT ON COLUMN public.workflow_defs.goal IS 'Human-readable workflow objective for builder and Meson';
