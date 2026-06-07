-- STA-97: Certified partner program — automated security scan + scope review + registry badge

ALTER TABLE public.partner_connector_submissions
  ADD COLUMN IF NOT EXISTS package_sources jsonb NOT NULL DEFAULT '{}'::jsonb,
  ADD COLUMN IF NOT EXISTS security_scan jsonb NOT NULL DEFAULT '{}'::jsonb,
  ADD COLUMN IF NOT EXISTS scope_review jsonb NOT NULL DEFAULT '{}'::jsonb,
  ADD COLUMN IF NOT EXISTS certification_status text NOT NULL DEFAULT 'pending'
    CHECK (certification_status IN ('pending', 'passed', 'failed'));

ALTER TABLE public.partner_connector_registry
  ADD COLUMN IF NOT EXISTS certification_badge text
    CHECK (certification_badge IS NULL OR certification_badge IN ('gravitre_certified')),
  ADD COLUMN IF NOT EXISTS certified_at timestamptz,
  ADD COLUMN IF NOT EXISTS security_scan_summary jsonb NOT NULL DEFAULT '{}'::jsonb;

CREATE INDEX IF NOT EXISTS idx_partner_submissions_certification
  ON public.partner_connector_submissions(certification_status);

CREATE INDEX IF NOT EXISTS idx_partner_registry_certified
  ON public.partner_connector_registry(certification_badge)
  WHERE certification_badge IS NOT NULL;
