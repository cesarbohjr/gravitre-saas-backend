CREATE TABLE IF NOT EXISTS public.capability_trusted_publishers (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id uuid NOT NULL REFERENCES public.organizations(id) ON DELETE CASCADE,
  publisher_name text NOT NULL,
  key_fingerprint text NOT NULL,
  public_key_pem text NOT NULL,
  status text NOT NULL DEFAULT 'active' CHECK (status IN ('active','revoked')),
  added_by uuid,
  created_at timestamptz NOT NULL DEFAULT now(),
  revoked_at timestamptz,
  UNIQUE(org_id, publisher_name, key_fingerprint)
);

CREATE INDEX IF NOT EXISTS capability_trusted_publishers_org_idx
  ON public.capability_trusted_publishers(org_id, status, publisher_name);

ALTER TABLE public.capability_trusted_publishers ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS capability_trusted_publishers_org_member_read
  ON public.capability_trusted_publishers;
CREATE POLICY capability_trusted_publishers_org_member_read
  ON public.capability_trusted_publishers FOR SELECT
  USING (
    EXISTS (
      SELECT 1 FROM public.organization_members m
      WHERE m.org_id = capability_trusted_publishers.org_id
        AND m.user_id = auth.uid()
    )
  );

COMMENT ON TABLE public.capability_trusted_publishers IS
  'Organization-approved signing keys for portable capability publishers. Signature validity alone does not confer publisher trust.';
