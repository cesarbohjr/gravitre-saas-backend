ALTER TABLE public.capability_packages
  ADD COLUMN IF NOT EXISTS reviewed_by uuid,
  ADD COLUMN IF NOT EXISTS reviewed_at timestamptz,
  ADD COLUMN IF NOT EXISTS review_notes text;

CREATE INDEX IF NOT EXISTS capability_packages_review_idx
  ON public.capability_packages(org_id, risk_level, status, reviewed_at DESC);

COMMENT ON COLUMN public.capability_packages.reviewed_at IS
  'Last org-admin security/governance review timestamp for portable capability activation.';
