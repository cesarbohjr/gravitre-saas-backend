ALTER TABLE IF EXISTS public.mcp_servers
  ADD COLUMN IF NOT EXISTS source_capability_package_id uuid
    REFERENCES public.capability_packages(id) ON DELETE SET NULL,
  ADD COLUMN IF NOT EXISTS activation_state text NOT NULL DEFAULT 'configured'
    CHECK (activation_state IN ('pending_review','configured','disabled'));

CREATE INDEX IF NOT EXISTS mcp_servers_source_capability_idx
  ON public.mcp_servers(org_id, source_capability_package_id)
  WHERE source_capability_package_id IS NOT NULL;

COMMENT ON COLUMN public.mcp_servers.source_capability_package_id IS
  'Portable capability package that declared this MCP dependency, when applicable.';
