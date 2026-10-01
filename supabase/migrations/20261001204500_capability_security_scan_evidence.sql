ALTER TABLE public.capability_packages
  ADD COLUMN IF NOT EXISTS security_scan jsonb NOT NULL DEFAULT '{}'::jsonb;

ALTER TABLE public.capability_marketplace_candidates
  ADD COLUMN IF NOT EXISTS security_scan jsonb NOT NULL DEFAULT '{}'::jsonb;

CREATE INDEX IF NOT EXISTS capability_packages_security_risk_idx
  ON public.capability_packages(org_id, ((security_scan->>'risk')));

COMMENT ON COLUMN public.capability_packages.security_scan IS
  'Static non-executing security scan evidence for the installed portable package.';
