-- Wave C1+C2: domain alignment fields on agent knowledge assignments

ALTER TABLE public.agent_knowledge_assignments
  ADD COLUMN IF NOT EXISTS department text,
  ADD COLUMN IF NOT EXISTS subdomain text,
  ADD COLUMN IF NOT EXISTS confidence_weight numeric(5, 4) NOT NULL DEFAULT 1.0;

CREATE INDEX IF NOT EXISTS idx_agent_knowledge_assignments_domain
  ON public.agent_knowledge_assignments (org_id, agent_id, department, subdomain)
  WHERE department IS NOT NULL;

COMMENT ON COLUMN public.agent_knowledge_assignments.department IS
  'Domain department key (marketing, sales, support, msp, …) for retrieval alignment.';
COMMENT ON COLUMN public.agent_knowledge_assignments.subdomain IS
  'Domain subdomain key (seo, pipeline_management, rmm, …) for retrieval alignment.';
COMMENT ON COLUMN public.agent_knowledge_assignments.confidence_weight IS
  'Retrieval boost multiplier (0.5–2.0). Distinct from confidence_score.';

-- Safe backfill from owning_department and agent config hints
UPDATE public.agent_knowledge_assignments aka
SET department = COALESCE(aka.department, aka.owning_department)
WHERE aka.department IS NULL AND aka.owning_department IS NOT NULL;

UPDATE public.agent_knowledge_assignments aka
SET department = lower(coalesce(a.config->>'department', a.config->'departmentPack'->>0, ''))
FROM public.agents a
WHERE aka.agent_id = a.id
  AND aka.org_id = a.org_id
  AND aka.department IS NULL
  AND coalesce(a.config->>'department', '') <> '';
