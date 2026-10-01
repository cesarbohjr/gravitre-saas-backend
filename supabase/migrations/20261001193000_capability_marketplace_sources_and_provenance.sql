CREATE TABLE IF NOT EXISTS public.capability_marketplace_sources (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id uuid NOT NULL REFERENCES public.organizations(id) ON DELETE CASCADE,
  name text NOT NULL,
  source_type text NOT NULL DEFAULT 'github' CHECK (source_type IN ('github')),
  repository_url text NOT NULL,
  branch text NOT NULL DEFAULT 'main',
  root_path text NOT NULL DEFAULT '',
  auto_sync boolean NOT NULL DEFAULT false,
  approval_required boolean NOT NULL DEFAULT true,
  status text NOT NULL DEFAULT 'active' CHECK (status IN ('active','paused','error','removed')),
  last_synced_at timestamptz,
  last_sync_status text,
  last_sync_error text,
  created_by uuid,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE(org_id, repository_url, branch, root_path)
);

CREATE INDEX IF NOT EXISTS capability_marketplace_sources_org_idx
  ON public.capability_marketplace_sources(org_id, status);

ALTER TABLE public.capability_marketplace_sources ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS capability_marketplace_sources_org_member_read ON public.capability_marketplace_sources;
CREATE POLICY capability_marketplace_sources_org_member_read
  ON public.capability_marketplace_sources FOR SELECT
  USING (
    EXISTS (
      SELECT 1 FROM public.organization_members m
      WHERE m.org_id = capability_marketplace_sources.org_id
        AND m.user_id = auth.uid()
    )
  );

ALTER TABLE public.capability_packages
  ADD COLUMN IF NOT EXISTS marketplace_source_id uuid REFERENCES public.capability_marketplace_sources(id) ON DELETE SET NULL,
  ADD COLUMN IF NOT EXISTS publisher_name text,
  ADD COLUMN IF NOT EXISTS publisher_verified boolean NOT NULL DEFAULT false,
  ADD COLUMN IF NOT EXISTS signature_status text NOT NULL DEFAULT 'unsigned'
    CHECK (signature_status IN ('unsigned','verified','invalid','untrusted')),
  ADD COLUMN IF NOT EXISTS content_digest text;

COMMENT ON TABLE public.capability_marketplace_sources IS
  'Organization-owned Git-backed capability marketplace sources. Source registration never auto-executes package code.';
