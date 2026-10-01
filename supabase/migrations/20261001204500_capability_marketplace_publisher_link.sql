ALTER TABLE public.capability_packages
  ADD COLUMN IF NOT EXISTS marketplace_publisher_id uuid
    REFERENCES public.marketplace_publishers(id) ON DELETE SET NULL;

CREATE INDEX IF NOT EXISTS capability_packages_marketplace_publisher_idx
  ON public.capability_packages(marketplace_publisher_id)
  WHERE marketplace_publisher_id IS NOT NULL;

COMMENT ON COLUMN public.capability_packages.marketplace_publisher_id IS
  'Canonical Marketplace publisher identity when the package declaration matches an active publisher owned by the same organization.';
