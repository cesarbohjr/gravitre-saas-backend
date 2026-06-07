-- STA-80: Dedicated org data region column with backfill from settings JSONB.
ALTER TABLE public.organizations
  ADD COLUMN IF NOT EXISTS data_region text NOT NULL DEFAULT 'us';

ALTER TABLE public.organizations
  DROP CONSTRAINT IF EXISTS organizations_data_region_check;

ALTER TABLE public.organizations
  ADD CONSTRAINT organizations_data_region_check
  CHECK (data_region IN ('us', 'eu'));

UPDATE public.organizations
SET data_region = COALESCE(
  NULLIF(TRIM(settings->'enterprise'->'dataResidency'->>'region'), ''),
  NULLIF(TRIM(settings->>'data_region'), ''),
  'us'
)
WHERE data_region = 'us'
  AND (
    settings->'enterprise'->'dataResidency'->>'region' IS NOT NULL
    OR settings->>'data_region' IS NOT NULL
  );

CREATE INDEX IF NOT EXISTS idx_organizations_data_region ON public.organizations (data_region);
