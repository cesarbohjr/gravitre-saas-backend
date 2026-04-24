-- Phase 8: Workflow versioning + active pointers

CREATE TABLE public.workflow_versions (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id uuid NOT NULL REFERENCES public.organizations(id) ON DELETE CASCADE,
  environment text NOT NULL,
  workflow_id uuid NOT NULL REFERENCES public.workflow_defs(id) ON DELETE CASCADE,
  version int NOT NULL,
  definition jsonb NOT NULL,
  schema_version text NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  created_by uuid REFERENCES auth.users(id) ON DELETE SET NULL
);

CREATE UNIQUE INDEX idx_workflow_versions_unique
  ON public.workflow_versions(org_id, environment, workflow_id, version);

CREATE INDEX idx_workflow_versions_org_env_workflow
  ON public.workflow_versions(org_id, environment, workflow_id, version DESC);

CREATE TABLE public.workflow_active_versions (
  org_id uuid NOT NULL REFERENCES public.organizations(id) ON DELETE CASCADE,
  environment text NOT NULL,
  workflow_id uuid NOT NULL REFERENCES public.workflow_defs(id) ON DELETE CASCADE,
  active_version_id uuid NOT NULL REFERENCES public.workflow_versions(id) ON DELETE CASCADE,
  updated_at timestamptz NOT NULL DEFAULT now(),
  updated_by uuid REFERENCES auth.users(id) ON DELETE SET NULL,
  PRIMARY KEY (org_id, environment, workflow_id)
);

ALTER TABLE public.workflow_runs
  ADD COLUMN IF NOT EXISTS workflow_version_id uuid REFERENCES public.workflow_versions(id) ON DELETE SET NULL;

CREATE INDEX IF NOT EXISTS idx_workflow_runs_org_env_workflow_created
  ON public.workflow_runs(org_id, environment, workflow_id, created_at DESC);

ALTER TABLE public.workflow_versions ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.workflow_active_versions ENABLE ROW LEVEL SECURITY;

CREATE POLICY "workflow_versions_org"
  ON public.workflow_versions FOR ALL
  USING (org_id = (SELECT org_id FROM public.organization_members WHERE user_id = auth.uid() LIMIT 1));

CREATE POLICY "workflow_active_versions_org"
  ON public.workflow_active_versions FOR ALL
  USING (org_id = (SELECT org_id FROM public.organization_members WHERE user_id = auth.uid() LIMIT 1));
