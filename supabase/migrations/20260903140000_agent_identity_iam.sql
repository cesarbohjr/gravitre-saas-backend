-- Agent Identity IAM — governed principal records extending write-authority (Phase 1–2).
-- Reuses org-scoped RLS; enforcement lives in react_write_gate + agent_tool_permissions.

CREATE TABLE IF NOT EXISTS public.agent_identity_records (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id uuid NOT NULL REFERENCES public.organizations(id) ON DELETE CASCADE,
  agent_id uuid NOT NULL REFERENCES public.agents(id) ON DELETE CASCADE,
  department_id uuid REFERENCES public.departments(id) ON DELETE SET NULL,
  agent_role text NOT NULL DEFAULT 'specialist',
  trust_level text NOT NULL DEFAULT 'write_with_approval'
    CHECK (trust_level IN ('read_only', 'write_with_approval', 'autonomous')),
  allowed_tool_patterns text[] NOT NULL DEFAULT '{}',
  allowed_action_kinds text[] NOT NULL DEFAULT ARRAY['read', 'write']::text[],
  allowed_data_scopes text[] NOT NULL DEFAULT '{}',
  max_actions_per_day integer,
  max_tokens_per_day bigint,
  max_spend_usd_per_day numeric(12, 4),
  can_delegate boolean NOT NULL DEFAULT false,
  approval_rule_overrides jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (org_id, agent_id)
);

CREATE INDEX IF NOT EXISTS agent_identity_records_org_idx
  ON public.agent_identity_records (org_id);

CREATE TABLE IF NOT EXISTS public.agent_identity_usage_daily (
  org_id uuid NOT NULL REFERENCES public.organizations(id) ON DELETE CASCADE,
  agent_id uuid NOT NULL REFERENCES public.agents(id) ON DELETE CASCADE,
  usage_date date NOT NULL,
  action_count integer NOT NULL DEFAULT 0,
  token_count bigint NOT NULL DEFAULT 0,
  spend_usd numeric(12, 4) NOT NULL DEFAULT 0,
  updated_at timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (org_id, agent_id, usage_date)
);

CREATE TABLE IF NOT EXISTS public.agent_delegation_grants (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id uuid NOT NULL REFERENCES public.organizations(id) ON DELETE CASCADE,
  grantor_agent_id uuid REFERENCES public.agents(id) ON DELETE SET NULL,
  grantor_user_id uuid,
  grantee_agent_id uuid REFERENCES public.agents(id) ON DELETE CASCADE,
  grantee_user_id uuid,
  delegated_permissions jsonb NOT NULL DEFAULT '{}'::jsonb,
  reason text,
  expires_at timestamptz NOT NULL,
  revoked_at timestamptz,
  created_at timestamptz NOT NULL DEFAULT now(),
  created_by uuid,
  CHECK (grantee_agent_id IS NOT NULL OR grantee_user_id IS NOT NULL)
);

CREATE INDEX IF NOT EXISTS agent_delegation_grants_org_grantee_idx
  ON public.agent_delegation_grants (org_id, grantee_agent_id)
  WHERE revoked_at IS NULL;

ALTER TABLE public.agent_identity_records ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.agent_identity_usage_daily ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.agent_delegation_grants ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS agent_identity_records_org_scope ON public.agent_identity_records;
CREATE POLICY agent_identity_records_org_scope
  ON public.agent_identity_records FOR ALL
  USING (
    org_id IN (
      SELECT org_id FROM public.organization_members WHERE user_id = auth.uid()
    )
  )
  WITH CHECK (
    org_id IN (
      SELECT org_id FROM public.organization_members WHERE user_id = auth.uid()
    )
  );

DROP POLICY IF EXISTS agent_identity_usage_daily_org_scope ON public.agent_identity_usage_daily;
CREATE POLICY agent_identity_usage_daily_org_scope
  ON public.agent_identity_usage_daily FOR ALL
  USING (
    org_id IN (
      SELECT org_id FROM public.organization_members WHERE user_id = auth.uid()
    )
  )
  WITH CHECK (
    org_id IN (
      SELECT org_id FROM public.organization_members WHERE user_id = auth.uid()
    )
  );

DROP POLICY IF EXISTS agent_delegation_grants_org_scope ON public.agent_delegation_grants;
CREATE POLICY agent_delegation_grants_org_scope
  ON public.agent_delegation_grants FOR ALL
  USING (
    org_id IN (
      SELECT org_id FROM public.organization_members WHERE user_id = auth.uid()
    )
  )
  WITH CHECK (
    org_id IN (
      SELECT org_id FROM public.organization_members WHERE user_id = auth.uid()
    )
  );
