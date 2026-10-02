-- Marketplace 3.0 persisted certification lifecycle.
ALTER TABLE public.marketplace_assets
  ADD COLUMN IF NOT EXISTS certification_level text
    CHECK (certification_level IN (
      'compatible',
      'tested',
      'governed',
      'production_verified',
      'outcome_verified'
    )),
  ADD COLUMN IF NOT EXISTS certification_report jsonb NOT NULL DEFAULT '{}'::jsonb,
  ADD COLUMN IF NOT EXISTS certification_evidence jsonb NOT NULL DEFAULT '{}'::jsonb,
  ADD COLUMN IF NOT EXISTS certification_updated_at timestamptz,
  ADD COLUMN IF NOT EXISTS certified_by uuid;

CREATE INDEX IF NOT EXISTS idx_marketplace_assets_certification
  ON public.marketplace_assets (certification_level, status, visibility);

COMMENT ON COLUMN public.marketplace_assets.certification_level IS
  'Marketplace 3.0 certification level. Production/outcome verified require evidence-linked certification.';
COMMENT ON COLUMN public.marketplace_assets.certification_report IS
  'Latest Marketplace 3.0 certification findings and resolved runtime/skill information.';
COMMENT ON COLUMN public.marketplace_assets.certification_evidence IS
  'Evidence references used to support Marketplace 3.0 certification; never secret material.';
