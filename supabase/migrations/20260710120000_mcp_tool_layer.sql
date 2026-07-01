-- MCP tool layer: org-scoped servers, tools, execution audit

CREATE TABLE IF NOT EXISTS public.mcp_servers (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id uuid NOT NULL REFERENCES public.organizations(id) ON DELETE CASCADE,
  server_name text NOT NULL,
  server_url text NOT NULL,
  transport text NOT NULL DEFAULT 'stdio'
    CHECK (transport IN ('stdio', 'sse', 'http')),
  auth_type text NOT NULL DEFAULT 'none'
    CHECK (auth_type IN ('none', 'api_key', 'oauth2', 'bearer')),
  auth_config jsonb NOT NULL DEFAULT '{}'::jsonb,
  enabled boolean NOT NULL DEFAULT true,
  verified_by_gravitre boolean NOT NULL DEFAULT false,
  created_by uuid REFERENCES auth.users(id) ON DELETE SET NULL,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_mcp_servers_org
  ON public.mcp_servers (org_id, enabled);

CREATE TABLE IF NOT EXISTS public.mcp_tools (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  server_id uuid NOT NULL REFERENCES public.mcp_servers(id) ON DELETE CASCADE,
  org_id uuid NOT NULL REFERENCES public.organizations(id) ON DELETE CASCADE,
  tool_name text NOT NULL,
  tool_description text,
  input_schema jsonb NOT NULL DEFAULT '{}'::jsonb,
  capability_tier text NOT NULL DEFAULT 'read'
    CHECK (capability_tier IN ('read', 'write')),
  requires_approval boolean GENERATED ALWAYS AS (capability_tier = 'write') STORED,
  enabled boolean NOT NULL DEFAULT true,
  risk_level text NOT NULL DEFAULT 'low'
    CHECK (risk_level IN ('low', 'medium', 'high')),
  created_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (server_id, tool_name)
);

CREATE INDEX IF NOT EXISTS idx_mcp_tools_org_enabled
  ON public.mcp_tools (org_id, enabled);

CREATE TABLE IF NOT EXISTS public.mcp_tool_executions (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id uuid NOT NULL REFERENCES public.organizations(id) ON DELETE CASCADE,
  tool_id uuid NOT NULL REFERENCES public.mcp_tools(id) ON DELETE CASCADE,
  agent_id uuid,
  workflow_run_id uuid,
  input jsonb NOT NULL,
  output jsonb,
  status text NOT NULL
    CHECK (status IN (
      'pending_approval', 'approved', 'rejected',
      'completed', 'failed', 'timeout'
    )),
  approval_id uuid,
  latency_ms integer,
  error text,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_mcp_tool_executions_org
  ON public.mcp_tool_executions (org_id, created_at DESC);

ALTER TABLE public.mcp_servers ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.mcp_tools ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.mcp_tool_executions ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS mcp_servers_org_isolation ON public.mcp_servers;
CREATE POLICY mcp_servers_org_isolation
  ON public.mcp_servers FOR ALL
  USING (
    org_id IN (SELECT org_id FROM public.organization_members WHERE user_id = auth.uid())
  );

DROP POLICY IF EXISTS mcp_tools_org_isolation ON public.mcp_tools;
CREATE POLICY mcp_tools_org_isolation
  ON public.mcp_tools FOR ALL
  USING (
    org_id IN (SELECT org_id FROM public.organization_members WHERE user_id = auth.uid())
  );

DROP POLICY IF EXISTS mcp_tool_executions_org_isolation ON public.mcp_tool_executions;
CREATE POLICY mcp_tool_executions_org_isolation
  ON public.mcp_tool_executions FOR ALL
  USING (
    org_id IN (SELECT org_id FROM public.organization_members WHERE user_id = auth.uid())
  );

COMMENT ON TABLE public.mcp_servers IS
  'Org-scoped MCP server registrations; auth_config secrets encrypted at application layer.';
COMMENT ON TABLE public.mcp_tools IS
  'Discovered MCP tools; write tier requires approval (GENERATED requires_approval).';
COMMENT ON TABLE public.mcp_tool_executions IS
  'MCP execution audit trail with approval linkage for write tools.';
