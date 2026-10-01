ALTER TABLE public.capability_trusted_publishers
  ADD COLUMN IF NOT EXISTS marketplace_publisher_id uuid REFERENCES public.marketplace_publishers(id) ON DELETE SET NULL;

ALTER TABLE public.capability_packages
  ADD COLUMN IF NOT EXISTS publisher_trusted boolean NOT NULL DEFAULT false,
  ADD COLUMN IF NOT EXISTS publisher_trust_scope text NOT NULL DEFAULT 'none'
    CHECK (publisher_trust_scope IN ('none','organization','marketplace_verified')),
  ADD COLUMN IF NOT EXISTS marketplace_publisher_id uuid REFERENCES public.marketplace_publishers(id) ON DELETE SET NULL;

COMMENT ON COLUMN public.capability_packages.publisher_trusted IS
  'True when the installing organization has explicitly trusted the signing key. This is distinct from Marketplace publisher verification.';

COMMENT ON COLUMN public.capability_packages.publisher_verified IS
  'True only when the package signing identity is linked to a platform-verified Marketplace publisher.';
