CREATE TABLE IF NOT EXISTS public.marketplace_capability_assets (
  asset_id uuid PRIMARY KEY REFERENCES public.marketplace_assets(id) ON DELETE CASCADE,
  source_org_id uuid NOT NULL REFERENCES public.organizations(id) ON DELETE CASCADE,
  source_package_id uuid REFERENCES public.capability_packages(id) ON DELETE SET NULL,
  package_name text NOT NULL,
  package_format text NOT NULL,
  package_version text,
  content_digest text,
  manifest jsonb NOT NULL DEFAULT '{}'::jsonb,
  inspection jsonb NOT NULL DEFAULT '{}'::jsonb,
  security_scan jsonb NOT NULL DEFAULT '{}'::jsonb,
  resources jsonb NOT NULL DEFAULT '[]'::jsonb,
  created_by uuid,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS marketplace_capability_assets_source_idx
  ON public.marketplace_capability_assets(source_org_id, source_package_id);

ALTER TABLE public.marketplace_capability_assets ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS marketplace_capability_assets_public_read ON public.marketplace_capability_assets;
CREATE POLICY marketplace_capability_assets_public_read
  ON public.marketplace_capability_assets FOR SELECT
  USING (
    EXISTS (
      SELECT 1
      FROM public.marketplace_assets a
      WHERE a.id = marketplace_capability_assets.asset_id
        AND a.status = 'published'
        AND a.visibility IN ('public','internal')
    )
    OR EXISTS (
      SELECT 1 FROM public.organization_members m
      WHERE m.org_id = marketplace_capability_assets.source_org_id
        AND m.user_id = auth.uid()
    )
  );

COMMENT ON TABLE public.marketplace_capability_assets IS
  'Immutable portable capability snapshots linked to existing Marketplace assets. Marketplace distribution never auto-activates imported capability execution.';
