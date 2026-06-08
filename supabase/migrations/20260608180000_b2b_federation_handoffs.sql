-- STA-116: Cross-org B2B agent handoff protocol (partnerships + briefing exchange)

CREATE TABLE IF NOT EXISTS public.org_b2b_partnerships (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  org_a_id uuid NOT NULL REFERENCES public.organizations(id) ON DELETE CASCADE,
  org_b_id uuid NOT NULL REFERENCES public.organizations(id) ON DELETE CASCADE,
  invited_by_org_id uuid NOT NULL REFERENCES public.organizations(id) ON DELETE CASCADE,
  status text NOT NULL DEFAULT 'pending_partner'
    CHECK (status IN ('pending_partner', 'active', 'rejected', 'revoked')),
  initiator_consent_at timestamptz NOT NULL DEFAULT now(),
  partner_consent_at timestamptz,
  invited_by uuid REFERENCES auth.users(id) ON DELETE SET NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT org_b2b_partnerships_ordered CHECK (org_a_id::text < org_b_id::text),
  CONSTRAINT org_b2b_partnerships_pair_key UNIQUE (org_a_id, org_b_id)
);

CREATE INDEX IF NOT EXISTS idx_org_b2b_partnerships_org_a
  ON public.org_b2b_partnerships (org_a_id, status);
CREATE INDEX IF NOT EXISTS idx_org_b2b_partnerships_org_b
  ON public.org_b2b_partnerships (org_b_id, status);

CREATE TABLE IF NOT EXISTS public.cross_org_handoffs (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  partnership_id uuid NOT NULL REFERENCES public.org_b2b_partnerships(id) ON DELETE CASCADE,
  sender_org_id uuid NOT NULL REFERENCES public.organizations(id) ON DELETE CASCADE,
  receiver_org_id uuid NOT NULL REFERENCES public.organizations(id) ON DELETE CASCADE,
  from_agent_id uuid REFERENCES public.agents(id) ON DELETE SET NULL,
  to_agent_id uuid REFERENCES public.agents(id) ON DELETE SET NULL,
  briefing jsonb NOT NULL DEFAULT '{}'::jsonb,
  message text,
  status text NOT NULL DEFAULT 'pending_receiver'
    CHECK (status IN ('pending_receiver', 'accepted', 'rejected', 'completed', 'failed')),
  sender_user_id uuid NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  receiver_user_id uuid REFERENCES auth.users(id) ON DELETE SET NULL,
  error_message text,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  accepted_at timestamptz,
  completed_at timestamptz
);

CREATE INDEX IF NOT EXISTS idx_cross_org_handoffs_sender
  ON public.cross_org_handoffs (sender_org_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_cross_org_handoffs_receiver
  ON public.cross_org_handoffs (receiver_org_id, status, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_cross_org_handoffs_partnership
  ON public.cross_org_handoffs (partnership_id);

ALTER TABLE public.org_b2b_partnerships ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.cross_org_handoffs ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "org_b2b_partnerships_tenant" ON public.org_b2b_partnerships;
CREATE POLICY "org_b2b_partnerships_tenant"
  ON public.org_b2b_partnerships
  FOR SELECT
  USING (
    org_a_id IN (SELECT om.org_id FROM public.organization_members om WHERE om.user_id = auth.uid())
    OR org_b_id IN (SELECT om.org_id FROM public.organization_members om WHERE om.user_id = auth.uid())
  );

DROP POLICY IF EXISTS "cross_org_handoffs_tenant" ON public.cross_org_handoffs;
CREATE POLICY "cross_org_handoffs_tenant"
  ON public.cross_org_handoffs
  FOR SELECT
  USING (
    sender_org_id IN (SELECT om.org_id FROM public.organization_members om WHERE om.user_id = auth.uid())
    OR receiver_org_id IN (SELECT om.org_id FROM public.organization_members om WHERE om.user_id = auth.uid())
  );

COMMENT ON TABLE public.org_b2b_partnerships IS
  'Mutual-consent B2B federation link between two Gravitre orgs (STA-116).';
COMMENT ON TABLE public.cross_org_handoffs IS
  'Cross-org agent briefing exchange; receiver org must accept before delivery (STA-116).';
