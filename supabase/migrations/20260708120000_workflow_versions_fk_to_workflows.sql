-- STA-271 follow-up: version tables reference contract workflows, not legacy workflow_defs.

-- Backfill contract rows for version pointers that only exist in legacy defs.
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
  SELECT workflow_id FROM public.workflow_versions
  UNION
  SELECT workflow_id FROM public.workflow_active_versions
)
AND NOT EXISTS (
  SELECT 1 FROM public.workflows w WHERE w.id = wd.id
)
ON CONFLICT (id) DO NOTHING;

ALTER TABLE public.workflow_versions
  DROP CONSTRAINT IF EXISTS workflow_versions_workflow_id_fkey;

ALTER TABLE public.workflow_active_versions
  DROP CONSTRAINT IF EXISTS workflow_active_versions_workflow_id_fkey;

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1
    FROM pg_constraint
    WHERE conname = 'workflow_versions_workflow_id_fkey'
      AND conrelid = 'public.workflow_versions'::regclass
  ) THEN
    ALTER TABLE public.workflow_versions
      ADD CONSTRAINT workflow_versions_workflow_id_fkey
      FOREIGN KEY (workflow_id) REFERENCES public.workflows(id) ON DELETE CASCADE;
  END IF;

  IF NOT EXISTS (
    SELECT 1
    FROM pg_constraint
    WHERE conname = 'workflow_active_versions_workflow_id_fkey'
      AND conrelid = 'public.workflow_active_versions'::regclass
  ) THEN
    ALTER TABLE public.workflow_active_versions
      ADD CONSTRAINT workflow_active_versions_workflow_id_fkey
      FOREIGN KEY (workflow_id) REFERENCES public.workflows(id) ON DELETE CASCADE;
  END IF;
END;
$$;

COMMENT ON CONSTRAINT workflow_versions_workflow_id_fkey ON public.workflow_versions IS
  'STA-271: version rows anchor to contract workflows (post-C.6 legacy writes off).';

COMMENT ON CONSTRAINT workflow_active_versions_workflow_id_fkey ON public.workflow_active_versions IS
  'STA-271: active version pointer anchors to contract workflows (post-C.6 legacy writes off).';
