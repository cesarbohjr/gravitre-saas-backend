-- MKT-AUDIT-4.6: Structured outcome metadata + internal publish feedback
ALTER TABLE public.marketplace_assets
  ADD COLUMN IF NOT EXISTS business_outcome text,
  ADD COLUMN IF NOT EXISTS use_case text,
  ADD COLUMN IF NOT EXISTS estimated_hours_saved numeric(6, 1),
  ADD COLUMN IF NOT EXISTS review_feedback text;

COMMENT ON COLUMN public.marketplace_assets.business_outcome IS
  'Customer-facing business outcome statement for marketplace cards.';
COMMENT ON COLUMN public.marketplace_assets.use_case IS
  'Primary use case summary for browse/detail UX.';
COMMENT ON COLUMN public.marketplace_assets.estimated_hours_saved IS
  'Estimated strategic hours saved per month after install.';
COMMENT ON COLUMN public.marketplace_assets.review_feedback IS
  'Latest internal publish rejection feedback for org-owned drafts.';
