-- STA-121: Agent role marketplace — department pack install tracking

CREATE TABLE IF NOT EXISTS public.org_department_pack_installs (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id uuid NOT NULL REFERENCES public.organizations(id) ON DELETE CASCADE,
  pack_id text NOT NULL,
  department text NOT NULL,
  agent_ids jsonb NOT NULL DEFAULT '[]'::jsonb,
  workflow_ids jsonb NOT NULL DEFAULT '[]'::jsonb,
  rag_source_ids jsonb NOT NULL DEFAULT '[]'::jsonb,
  connector_checklist jsonb NOT NULL DEFAULT '[]'::jsonb,
  installed_by uuid REFERENCES auth.users(id) ON DELETE SET NULL,
  installed_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT org_department_pack_installs_unique UNIQUE (org_id, pack_id)
);

CREATE INDEX IF NOT EXISTS idx_org_department_pack_installs_org
  ON public.org_department_pack_installs (org_id, installed_at DESC);

ALTER TABLE public.org_department_pack_installs ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "org_department_pack_installs_tenant" ON public.org_department_pack_installs;
CREATE POLICY "org_department_pack_installs_tenant"
  ON public.org_department_pack_installs
  FOR SELECT
  USING (
    org_id IN (SELECT om.org_id FROM public.organization_members om WHERE om.user_id = auth.uid())
  );

COMMENT ON TABLE public.org_department_pack_installs IS
  'One-click department role pack installs — agents, RAG, workflows (STA-121).';
