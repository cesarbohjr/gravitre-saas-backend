-- STA-110: HIPAA BAA workflow + PHI-tagged connectors

ALTER TABLE public.connectors
  ADD COLUMN IF NOT EXISTS phi_capable boolean NOT NULL DEFAULT false;

CREATE INDEX IF NOT EXISTS idx_connectors_phi_capable
  ON public.connectors (org_id, phi_capable)
  WHERE phi_capable = true;

CREATE TABLE IF NOT EXISTS public.org_hipaa_baa_acceptances (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id uuid NOT NULL REFERENCES public.organizations(id) ON DELETE CASCADE,
  accepted_by uuid NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  baa_version text NOT NULL,
  accepted_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_org_hipaa_baa_org
  ON public.org_hipaa_baa_acceptances (org_id, accepted_at DESC);

ALTER TABLE public.org_hipaa_baa_acceptances ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "org_hipaa_baa_org" ON public.org_hipaa_baa_acceptances;
CREATE POLICY "org_hipaa_baa_org"
  ON public.org_hipaa_baa_acceptances FOR ALL
  USING (org_id = (SELECT org_id FROM public.organization_members WHERE user_id = auth.uid() LIMIT 1));
