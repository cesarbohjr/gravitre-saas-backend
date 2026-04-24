-- Phase 11: Operator versioning
-- Authority: docs/phase-11/OPERATOR_VERSIONING_PLAN.md

CREATE TABLE public.operator_versions (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id uuid NOT NULL REFERENCES public.organizations(id) ON DELETE CASCADE,
  operator_id uuid NOT NULL REFERENCES public.operators(id) ON DELETE CASCADE,
  environment text NOT NULL,
  version int NOT NULL,
  name text NOT NULL,
  description text,
  system_prompt text,
  allowed_environments text[] NOT NULL DEFAULT '{}',
  requires_admin boolean NOT NULL DEFAULT false,
  requires_approval boolean NOT NULL DEFAULT false,
  approval_roles text[] NOT NULL DEFAULT '{admin}',
  connector_ids uuid[] NOT NULL DEFAULT '{}',
  created_by uuid REFERENCES auth.users(id) ON DELETE SET NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (org_id, operator_id, environment, version)
);

CREATE INDEX idx_operator_versions_org_id ON public.operator_versions(org_id);
CREATE INDEX idx_operator_versions_operator_env ON public.operator_versions(operator_id, environment);

CREATE TABLE public.operator_active_versions (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id uuid NOT NULL REFERENCES public.organizations(id) ON DELETE CASCADE,
  operator_id uuid NOT NULL REFERENCES public.operators(id) ON DELETE CASCADE,
  environment text NOT NULL,
  active_version_id uuid NOT NULL REFERENCES public.operator_versions(id) ON DELETE CASCADE,
  updated_by uuid REFERENCES auth.users(id) ON DELETE SET NULL,
  updated_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (org_id, operator_id, environment)
);

CREATE INDEX idx_operator_active_versions_org_id ON public.operator_active_versions(org_id);
CREATE INDEX idx_operator_active_versions_operator_env ON public.operator_active_versions(operator_id, environment);

ALTER TABLE public.operator_sessions
  ADD COLUMN IF NOT EXISTS operator_version_id uuid REFERENCES public.operator_versions(id) ON DELETE SET NULL;

ALTER TABLE public.operator_action_plans
  ADD COLUMN IF NOT EXISTS operator_version_id uuid REFERENCES public.operator_versions(id) ON DELETE SET NULL;

ALTER TABLE public.operator_actions
  ADD COLUMN IF NOT EXISTS operator_version_id uuid REFERENCES public.operator_versions(id) ON DELETE SET NULL;

ALTER TABLE public.operator_versions ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.operator_active_versions ENABLE ROW LEVEL SECURITY;

CREATE POLICY "operator_versions_org"
  ON public.operator_versions FOR ALL
  USING (org_id = (SELECT org_id FROM public.organization_members WHERE user_id = auth.uid() LIMIT 1));

CREATE POLICY "operator_active_versions_org"
  ON public.operator_active_versions FOR ALL
  USING (org_id = (SELECT org_id FROM public.organization_members WHERE user_id = auth.uid() LIMIT 1));
