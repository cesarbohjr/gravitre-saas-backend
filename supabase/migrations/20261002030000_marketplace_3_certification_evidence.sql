-- Gravitre Marketplace 3.0 certification evidence.
-- Certification is bound to the exact Outcome Pack config digest so changing a
-- package invalidates previous proof until the new version is re-certified.

CREATE TABLE IF NOT EXISTS public.marketplace_outcome_pack_certifications (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id uuid NOT NULL REFERENCES public.organizations(id) ON DELETE CASCADE,
  asset_id uuid NOT NULL REFERENCES public.marketplace_assets(id) ON DELETE CASCADE,
  config_digest text NOT NULL,
  certification_level text NOT NULL
    CHECK (certification_level IN (
      'compatible',
      'tested',
      'governed',
      'production_verified',
      'outcome_verified'
    )),
  publish_ready boolean NOT NULL DEFAULT false,
  report jsonb NOT NULL DEFAULT '{}'::jsonb,
  evidence jsonb NOT NULL DEFAULT '{}'::jsonb,
  certified_by uuid,
  certified_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (asset_id, config_digest)
);

CREATE INDEX IF NOT EXISTS idx_marketplace_outcome_pack_cert_org
  ON public.marketplace_outcome_pack_certifications (org_id, certified_at DESC);

CREATE INDEX IF NOT EXISTS idx_marketplace_outcome_pack_cert_asset
  ON public.marketplace_outcome_pack_certifications (asset_id, certified_at DESC);

ALTER TABLE public.marketplace_outcome_pack_certifications ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS marketplace_outcome_pack_certifications_org_scope
  ON public.marketplace_outcome_pack_certifications;

CREATE POLICY marketplace_outcome_pack_certifications_org_scope
  ON public.marketplace_outcome_pack_certifications
  FOR ALL
  TO authenticated
  USING (
    org_id IN (
      SELECT om.org_id
      FROM public.organization_members om
      WHERE om.user_id = (SELECT auth.uid())
    )
  )
  WITH CHECK (
    org_id IN (
      SELECT om.org_id
      FROM public.organization_members om
      WHERE om.user_id = (SELECT auth.uid())
    )
  );

COMMENT ON TABLE public.marketplace_outcome_pack_certifications IS
  'Marketplace 3.0 certification evidence bound to an immutable Outcome Pack config digest.';
