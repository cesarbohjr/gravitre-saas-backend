-- Portable capability ecosystem: Agent Skills, MCP and plugin packages.
-- Imported metadata is inert. Runtime execution continues through Gravitre's
-- canonical connector/workflow/approval/verification systems.

CREATE TABLE IF NOT EXISTS public.capability_packages (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id uuid NOT NULL REFERENCES public.organizations(id) ON DELETE CASCADE,
  name text NOT NULL,
  package_format text NOT NULL CHECK (package_format IN (
    'agent_skill','openai_plugin','claude_plugin','gravitre','mcp','unknown'
  )),
  version text,
  description text,
  license text,
  license_policy text NOT NULL CHECK (license_policy IN ('allow','review','block')),
  risk_level text NOT NULL CHECK (risk_level IN ('low','moderate','high','blocked')),
  source_type text NOT NULL DEFAULT 'manual' CHECK (source_type IN ('manual','github','zip','mcp','marketplace')),
  source_uri text,
  manifest jsonb NOT NULL DEFAULT '{}'::jsonb,
  inspection jsonb NOT NULL DEFAULT '{}'::jsonb,
  status text NOT NULL DEFAULT 'installed' CHECK (status IN ('installed','disabled','quarantined','removed')),
  installed_by uuid,
  installed_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (org_id, name, version)
);

CREATE INDEX IF NOT EXISTS capability_packages_org_status_idx
  ON public.capability_packages(org_id, status, installed_at DESC);

ALTER TABLE public.capability_packages ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS capability_packages_org_member_read ON public.capability_packages;
CREATE POLICY capability_packages_org_member_read
  ON public.capability_packages FOR SELECT
  USING (
    EXISTS (
      SELECT 1 FROM public.organization_members m
      WHERE m.org_id = capability_packages.org_id
        AND m.user_id = auth.uid()
    )
  );

COMMENT ON TABLE public.capability_packages IS
  'Installed portable capability package metadata. Package content is inert; runtime actions remain governed by Gravitre execution policies.';
