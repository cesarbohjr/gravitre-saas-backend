-- STA-98: Customer private connector runtime (signed packages, org-scoped)

CREATE TABLE public.org_private_connector_bundles (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id uuid NOT NULL REFERENCES public.organizations(id) ON DELETE CASCADE,
  created_by uuid NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  name text NOT NULL,
  package_id text NOT NULL,
  vendor text NOT NULL,
  version text NOT NULL,
  manifest jsonb NOT NULL,
  package_sources jsonb NOT NULL DEFAULT '{}'::jsonb,
  signing_public_key_pem text NOT NULL,
  signature text NOT NULL,
  signature_algorithm text NOT NULL DEFAULT 'ed25519'
    CHECK (signature_algorithm IN ('ed25519')),
  security_scan jsonb NOT NULL DEFAULT '{}'::jsonb,
  scope_review jsonb NOT NULL DEFAULT '{}'::jsonb,
  certification_status text NOT NULL DEFAULT 'pending'
    CHECK (certification_status IN ('pending', 'passed', 'failed')),
  status text NOT NULL DEFAULT 'draft'
    CHECK (status IN ('draft', 'active', 'disabled')),
  activated_at timestamptz,
  activated_by uuid REFERENCES auth.users(id) ON DELETE SET NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT org_private_connector_bundles_org_vendor_key UNIQUE (org_id, vendor)
);

CREATE INDEX idx_private_bundles_org_id ON public.org_private_connector_bundles(org_id);
CREATE INDEX idx_private_bundles_status ON public.org_private_connector_bundles(org_id, status);
CREATE INDEX idx_private_bundles_vendor ON public.org_private_connector_bundles(vendor);

ALTER TABLE public.org_private_connector_bundles ENABLE ROW LEVEL SECURITY;
