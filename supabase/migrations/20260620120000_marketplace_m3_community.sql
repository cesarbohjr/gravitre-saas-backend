-- M3 / STA-247–249: Community publishing, platform review, featured assets

ALTER TABLE public.marketplace_publishers
  ADD COLUMN IF NOT EXISTS public_publishing_enabled boolean NOT NULL DEFAULT false,
  ADD COLUMN IF NOT EXISTS onboarded_at timestamptz;

COMMENT ON COLUMN public.marketplace_publishers.public_publishing_enabled IS
  'True after org completes creator publisher onboarding (MKT-AUDIT-11.1).';

ALTER TABLE public.marketplace_assets
  ADD COLUMN IF NOT EXISTS review_scope text NOT NULL DEFAULT 'internal'
    CHECK (review_scope IN ('internal', 'public')),
  ADD COLUMN IF NOT EXISTS featured boolean NOT NULL DEFAULT false,
  ADD COLUMN IF NOT EXISTS verified boolean NOT NULL DEFAULT false;

CREATE INDEX IF NOT EXISTS idx_marketplace_assets_public_review
  ON public.marketplace_assets (status, review_scope)
  WHERE status = 'pending_review' AND review_scope = 'public';

CREATE INDEX IF NOT EXISTS idx_marketplace_assets_featured
  ON public.marketplace_assets (featured, status, visibility)
  WHERE featured = true AND status = 'published';

COMMENT ON COLUMN public.marketplace_assets.review_scope IS
  'internal = org admin queue; public = Gravitre platform review queue (MKT-AUDIT-11.2).';

COMMENT ON COLUMN public.marketplace_assets.featured IS
  'Curated spotlight on marketplace home (MKT-AUDIT-11.3).';

COMMENT ON COLUMN public.marketplace_assets.verified IS
  'Asset-level verified badge beyond publisher.verified (MKT-AUDIT-11.3).';
