-- Vertical-pack workflows store demo defaults on workflow_defs.config (legal, healthcare, devops, etc.).

ALTER TABLE public.workflow_defs
  ADD COLUMN IF NOT EXISTS config jsonb NOT NULL DEFAULT '{}'::jsonb;
