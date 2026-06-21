-- STA-271 follow-up: execute runs anchor to contract workflows (contract-only path post-C.6).

INSERT INTO public.workflows (
  id,
  org_id,
  name,
  description,
  status,
  environment,
  nodes,
  edges,
  config,
  created_by,
  created_at,
  updated_at
)
SELECT
  wd.id,
  wd.org_id,
  COALESCE(NULLIF(wd.name, ''), 'Workflow'),
  wd.description,
  CASE lower(COALESCE(wd.status, 'draft'))
    WHEN 'enabled' THEN 'active'
    WHEN 'disabled' THEN 'paused'
    WHEN 'inactive' THEN 'paused'
    WHEN 'active' THEN 'active'
    WHEN 'draft' THEN 'draft'
    WHEN 'paused' THEN 'paused'
    WHEN 'archived' THEN 'archived'
    WHEN 'error' THEN 'error'
    ELSE 'draft'
  END,
  'production',
  '[]'::jsonb,
  '[]'::jsonb,
  COALESCE(wd.config, '{}'::jsonb),
  wd.created_by,
  COALESCE(wd.created_at, now()),
  COALESCE(wd.updated_at, now())
FROM public.workflow_defs wd
WHERE wd.id IN (
  SELECT workflow_id FROM public.workflow_runs WHERE workflow_id IS NOT NULL
)
AND NOT EXISTS (
  SELECT 1 FROM public.workflows w WHERE w.id = wd.id
)
ON CONFLICT (id) DO NOTHING;

ALTER TABLE public.workflow_runs
  DROP CONSTRAINT IF EXISTS workflow_runs_workflow_id_fkey;

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1
    FROM pg_constraint
    WHERE conname = 'workflow_runs_workflow_id_fkey'
      AND conrelid = 'public.workflow_runs'::regclass
  ) THEN
    ALTER TABLE public.workflow_runs
      ADD CONSTRAINT workflow_runs_workflow_id_fkey
      FOREIGN KEY (workflow_id) REFERENCES public.workflows(id) ON DELETE SET NULL;
  END IF;
END;
$$;

COMMENT ON CONSTRAINT workflow_runs_workflow_id_fkey ON public.workflow_runs IS
  'STA-271: execute runs reference contract workflows (post-C.6 legacy writes off).';
