ALTER TABLE public.capability_marketplace_candidates
  ADD COLUMN IF NOT EXISTS source_commit_sha text,
  ADD COLUMN IF NOT EXISTS source_package_path text;

ALTER TABLE public.capability_packages
  ADD COLUMN IF NOT EXISTS source_commit_sha text,
  ADD COLUMN IF NOT EXISTS source_package_path text;

COMMENT ON COLUMN public.capability_packages.source_commit_sha IS
  'Exact Git commit that produced this portable package when installed from a Git marketplace.';
