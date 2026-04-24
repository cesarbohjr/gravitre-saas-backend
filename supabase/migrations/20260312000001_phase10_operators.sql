-- Phase 10: Operators (Agents) + sessions + action plans
-- Authority: docs/phase-10/AGENT_ARCHITECTURE_PLAN.md

CREATE TABLE public.operators (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id uuid NOT NULL REFERENCES public.organizations(id) ON DELETE CASCADE,
  name text NOT NULL,
  description text,
  status text NOT NULL CHECK (status IN ('draft', 'active', 'inactive')),
  system_prompt text,
  allowed_environments text[] NOT NULL DEFAULT '{}',
  requires_admin boolean NOT NULL DEFAULT false,
  requires_approval boolean NOT NULL DEFAULT false,
  approval_roles text[] NOT NULL DEFAULT '{admin}',
  created_by uuid REFERENCES auth.users(id) ON DELETE SET NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX idx_operators_org_id ON public.operators(org_id);
CREATE INDEX idx_operators_org_status ON public.operators(org_id, status);

CREATE TABLE public.operator_connector_bindings (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id uuid NOT NULL REFERENCES public.organizations(id) ON DELETE CASCADE,
  operator_id uuid NOT NULL REFERENCES public.operators(id) ON DELETE CASCADE,
  connector_id uuid NOT NULL REFERENCES public.connectors(id) ON DELETE CASCADE,
  created_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (operator_id, connector_id)
);

CREATE INDEX idx_operator_bindings_org_id ON public.operator_connector_bindings(org_id);
CREATE INDEX idx_operator_bindings_operator_id ON public.operator_connector_bindings(operator_id);

CREATE TABLE public.operator_sessions (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id uuid NOT NULL REFERENCES public.organizations(id) ON DELETE CASCADE,
  operator_id uuid NOT NULL REFERENCES public.operators(id) ON DELETE CASCADE,
  environment text NOT NULL,
  title text NOT NULL,
  status text NOT NULL CHECK (status IN ('idle', 'planning', 'review', 'awaiting_approval', 'executing', 'paused', 'completed', 'failed')),
  current_task text,
  created_by uuid REFERENCES auth.users(id) ON DELETE SET NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX idx_operator_sessions_org_id ON public.operator_sessions(org_id);
CREATE INDEX idx_operator_sessions_operator_id ON public.operator_sessions(operator_id);
CREATE INDEX idx_operator_sessions_created_by ON public.operator_sessions(created_by);

CREATE TABLE public.operator_action_plans (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id uuid NOT NULL REFERENCES public.organizations(id) ON DELETE CASCADE,
  operator_id uuid NOT NULL REFERENCES public.operators(id) ON DELETE CASCADE,
  session_id uuid NOT NULL REFERENCES public.operator_sessions(id) ON DELETE CASCADE,
  environment text NOT NULL,
  title text NOT NULL,
  summary text,
  prompt text,
  primary_context jsonb NOT NULL,
  related_contexts jsonb NOT NULL DEFAULT '[]'::jsonb,
  steps jsonb NOT NULL,
  guardrails jsonb NOT NULL,
  status text NOT NULL CHECK (status IN ('draft', 'pending_approval', 'approved', 'executing', 'completed', 'failed', 'cancelled')),
  created_by uuid REFERENCES auth.users(id) ON DELETE SET NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX idx_operator_plans_org_id ON public.operator_action_plans(org_id);
CREATE INDEX idx_operator_plans_session_id ON public.operator_action_plans(session_id);

CREATE TABLE public.operator_actions (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id uuid NOT NULL REFERENCES public.organizations(id) ON DELETE CASCADE,
  operator_id uuid NOT NULL REFERENCES public.operators(id) ON DELETE CASCADE,
  session_id uuid NOT NULL REFERENCES public.operator_sessions(id) ON DELETE CASCADE,
  plan_id uuid NOT NULL REFERENCES public.operator_action_plans(id) ON DELETE CASCADE,
  step_id text NOT NULL,
  action_type text NOT NULL,
  status text NOT NULL CHECK (status IN ('requested', 'pending_approval', 'running', 'completed', 'failed', 'cancelled')),
  workflow_run_id uuid REFERENCES public.workflow_runs(id) ON DELETE SET NULL,
  created_by uuid REFERENCES auth.users(id) ON DELETE SET NULL,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX idx_operator_actions_org_id ON public.operator_actions(org_id);
CREATE INDEX idx_operator_actions_plan_id ON public.operator_actions(plan_id);
CREATE INDEX idx_operator_actions_session_id ON public.operator_actions(session_id);

ALTER TABLE public.operators ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.operator_connector_bindings ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.operator_sessions ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.operator_action_plans ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.operator_actions ENABLE ROW LEVEL SECURITY;

CREATE POLICY "operators_org"
  ON public.operators FOR ALL
  USING (org_id = (SELECT org_id FROM public.organization_members WHERE user_id = auth.uid() LIMIT 1));

CREATE POLICY "operator_connector_bindings_org"
  ON public.operator_connector_bindings FOR ALL
  USING (org_id = (SELECT org_id FROM public.organization_members WHERE user_id = auth.uid() LIMIT 1));

CREATE POLICY "operator_sessions_org"
  ON public.operator_sessions FOR ALL
  USING (org_id = (SELECT org_id FROM public.organization_members WHERE user_id = auth.uid() LIMIT 1));

CREATE POLICY "operator_action_plans_org"
  ON public.operator_action_plans FOR ALL
  USING (org_id = (SELECT org_id FROM public.organization_members WHERE user_id = auth.uid() LIMIT 1));

CREATE POLICY "operator_actions_org"
  ON public.operator_actions FOR ALL
  USING (org_id = (SELECT org_id FROM public.organization_members WHERE user_id = auth.uid() LIMIT 1));
