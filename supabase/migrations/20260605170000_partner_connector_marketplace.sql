-- STA-71: Partner connector submission + review workflow

CREATE TABLE public.partner_connector_submissions (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id uuid NOT NULL REFERENCES public.organizations(id) ON DELETE CASCADE,
  submitted_by uuid NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  package_id text NOT NULL,
  vendor text NOT NULL,
  name text NOT NULL,
  version text NOT NULL,
  manifest jsonb NOT NULL,
  security_checklist jsonb NOT NULL DEFAULT '{}'::jsonb,
  status text NOT NULL DEFAULT 'pending'
    CHECK (status IN ('pending', 'in_review', 'approved', 'rejected', 'withdrawn')),
  reviewer_id uuid REFERENCES auth.users(id) ON DELETE SET NULL,
  review_notes text,
  reviewed_at timestamptz,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX idx_partner_submissions_org_id ON public.partner_connector_submissions(org_id);
CREATE INDEX idx_partner_submissions_status ON public.partner_connector_submissions(status);
CREATE INDEX idx_partner_submissions_vendor ON public.partner_connector_submissions(vendor);
CREATE UNIQUE INDEX idx_partner_submissions_pending_vendor
  ON public.partner_connector_submissions(vendor)
  WHERE status IN ('pending', 'in_review');

CREATE TABLE public.partner_connector_registry (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  submission_id uuid NOT NULL REFERENCES public.partner_connector_submissions(id) ON DELETE CASCADE,
  org_id uuid NOT NULL REFERENCES public.organizations(id) ON DELETE CASCADE,
  package_id text NOT NULL,
  vendor text NOT NULL,
  name text NOT NULL,
  version text NOT NULL,
  manifest jsonb NOT NULL,
  published_by uuid NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  published_at timestamptz NOT NULL DEFAULT now(),
  status text NOT NULL DEFAULT 'published'
    CHECK (status IN ('published', 'deprecated', 'suspended')),
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT partner_connector_registry_package_id_key UNIQUE (package_id),
  CONSTRAINT partner_connector_registry_vendor_key UNIQUE (vendor)
);

CREATE INDEX idx_partner_registry_org_id ON public.partner_connector_registry(org_id);
CREATE INDEX idx_partner_registry_status ON public.partner_connector_registry(status);

ALTER TABLE public.partner_connector_submissions ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.partner_connector_registry ENABLE ROW LEVEL SECURITY;

-- Backend uses service_role; no direct client policies for MVP.
