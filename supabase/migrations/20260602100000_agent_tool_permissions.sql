-- STA-11: Per-agent connector tool scopes (read/write authorization).

CREATE TABLE IF NOT EXISTS public.agent_tool_permissions (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id uuid NOT NULL REFERENCES public.organizations(id) ON DELETE CASCADE,
  agent_id uuid NOT NULL REFERENCES public.agents(id) ON DELETE CASCADE,
  connector_id uuid REFERENCES public.connectors(id) ON DELETE CASCADE,
  connector_type text,
  scopes text[] NOT NULL DEFAULT '{}'::text[],
  granted_by uuid REFERENCES auth.users(id) ON DELETE SET NULL,
  granted_at timestamptz NOT NULL DEFAULT now(),
  expires_at timestamptz,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT agent_tool_permissions_connector_ref CHECK (
    connector_id IS NOT NULL OR connector_type IS NOT NULL
  )
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_agent_tool_permissions_agent_connector
  ON public.agent_tool_permissions (org_id, agent_id, connector_id)
  WHERE connector_id IS NOT NULL;

CREATE UNIQUE INDEX IF NOT EXISTS idx_agent_tool_permissions_agent_type
  ON public.agent_tool_permissions (org_id, agent_id, connector_type)
  WHERE connector_id IS NULL AND connector_type IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_agent_tool_permissions_agent
  ON public.agent_tool_permissions (org_id, agent_id);

DROP TRIGGER IF EXISTS agent_tool_permissions_set_updated_at ON public.agent_tool_permissions;
CREATE TRIGGER agent_tool_permissions_set_updated_at
  BEFORE UPDATE ON public.agent_tool_permissions
  FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();

ALTER TABLE public.agent_tool_permissions ENABLE ROW LEVEL SECURITY;

CREATE POLICY "agent_tool_permissions_org"
  ON public.agent_tool_permissions FOR ALL
  USING (
    org_id = (
      SELECT org_id FROM public.organization_members WHERE user_id = auth.uid() LIMIT 1
    )
  );
