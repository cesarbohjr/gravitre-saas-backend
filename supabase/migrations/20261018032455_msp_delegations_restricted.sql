-- MSP delegated authorization persistence. Storage only: DOES NOT extend
-- auth_org_accessible, organization RLS, or customer resource permissions.
BEGIN;

CREATE TABLE IF NOT EXISTS public.msp_delegations (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  provider_org_id uuid NOT NULL REFERENCES public.organizations(id) ON DELETE CASCADE,
  customer_org_id uuid NOT NULL REFERENCES public.organizations(id) ON DELETE CASCADE,
  grantee_user_id uuid NOT NULL,
  tier smallint NOT NULL CHECK (tier BETWEEN 1 AND 3),
  actions text[] NOT NULL DEFAULT '{}',
  approved_by_customer_user_id uuid NOT NULL,
  approved_at timestamptz NOT NULL DEFAULT now(),
  expires_at timestamptz NOT NULL,
  revoked_at timestamptz,
  created_at timestamptz NOT NULL DEFAULT now(),
  CHECK (provider_org_id <> customer_org_id),
  CHECK (expires_at > approved_at),
  CHECK (revoked_at IS NULL OR revoked_at >= approved_at)
);
CREATE INDEX IF NOT EXISTS idx_msp_delegations_lookup
  ON public.msp_delegations (provider_org_id, customer_org_id, grantee_user_id, expires_at)
  WHERE revoked_at IS NULL;

ALTER TABLE public.msp_delegations ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.msp_delegations FORCE ROW LEVEL SECURITY;
REVOKE ALL ON public.msp_delegations FROM PUBLIC, anon, authenticated;
GRANT SELECT, INSERT, UPDATE ON public.msp_delegations TO service_role;

CREATE TABLE IF NOT EXISTS public.msp_delegation_audit (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  delegation_id uuid REFERENCES public.msp_delegations(id) ON DELETE SET NULL,
  provider_org_id uuid NOT NULL,
  customer_org_id uuid NOT NULL,
  actor_user_id uuid NOT NULL,
  action text NOT NULL CHECK (action IN ('grant.created','grant.revoked','grant.denied')),
  recorded_at timestamptz NOT NULL DEFAULT now(),
  metadata jsonb NOT NULL DEFAULT '{}'::jsonb
);
CREATE INDEX IF NOT EXISTS idx_msp_delegation_audit_customer
  ON public.msp_delegation_audit (customer_org_id, recorded_at DESC);
ALTER TABLE public.msp_delegation_audit ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.msp_delegation_audit FORCE ROW LEVEL SECURITY;
REVOKE ALL ON public.msp_delegation_audit FROM PUBLIC, anon, authenticated;
GRANT SELECT, INSERT ON public.msp_delegation_audit TO service_role;

-- Deliberately no authenticated SELECT policies, no parent-org inheritance
-- and no SECURITY DEFINER functions. Server code must independently verify
-- current customer owner consent and membership on every scoped action.
COMMIT;
