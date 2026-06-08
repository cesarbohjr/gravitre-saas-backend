-- STA-117: Federated connector consent — time-boxed read-only tool access across B2B partners

CREATE TABLE IF NOT EXISTS public.federated_connector_grants (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  partnership_id uuid NOT NULL REFERENCES public.org_b2b_partnerships(id) ON DELETE CASCADE,
  grantor_org_id uuid NOT NULL REFERENCES public.organizations(id) ON DELETE CASCADE,
  grantee_org_id uuid NOT NULL REFERENCES public.organizations(id) ON DELETE CASCADE,
  connector_id uuid NOT NULL REFERENCES public.connectors(id) ON DELETE CASCADE,
  label text,
  allowed_actions text[] NOT NULL DEFAULT '{}'::text[],
  status text NOT NULL DEFAULT 'pending_grantee'
    CHECK (status IN ('pending_grantee', 'active', 'rejected', 'revoked', 'expired')),
  access_token_hash text,
  expires_at timestamptz NOT NULL,
  proposed_by uuid REFERENCES auth.users(id) ON DELETE SET NULL,
  accepted_by uuid REFERENCES auth.users(id) ON DELETE SET NULL,
  revoked_by uuid REFERENCES auth.users(id) ON DELETE SET NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  accepted_at timestamptz,
  revoked_at timestamptz
);

CREATE INDEX IF NOT EXISTS idx_federated_grants_grantor
  ON public.federated_connector_grants (grantor_org_id, status);
CREATE INDEX IF NOT EXISTS idx_federated_grants_grantee
  ON public.federated_connector_grants (grantee_org_id, status);
CREATE INDEX IF NOT EXISTS idx_federated_grants_token
  ON public.federated_connector_grants (access_token_hash)
  WHERE access_token_hash IS NOT NULL;

ALTER TABLE public.federated_connector_grants ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "federated_connector_grants_tenant" ON public.federated_connector_grants;
CREATE POLICY "federated_connector_grants_tenant"
  ON public.federated_connector_grants
  FOR SELECT
  USING (
    grantor_org_id IN (SELECT om.org_id FROM public.organization_members om WHERE om.user_id = auth.uid())
    OR grantee_org_id IN (SELECT om.org_id FROM public.organization_members om WHERE om.user_id = auth.uid())
  );

COMMENT ON TABLE public.federated_connector_grants IS
  'Time-boxed read-only connector tool grants between B2B partner orgs (STA-117).';
