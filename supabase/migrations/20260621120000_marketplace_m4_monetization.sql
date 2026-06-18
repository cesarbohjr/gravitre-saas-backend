-- M4 / STA-250–253: Paid entitlements, payout ledger wiring, convergence metadata

CREATE TABLE IF NOT EXISTS public.marketplace_asset_entitlements (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id uuid NOT NULL REFERENCES public.organizations(id) ON DELETE CASCADE,
  asset_id uuid NOT NULL REFERENCES public.marketplace_assets(id) ON DELETE CASCADE,
  status text NOT NULL DEFAULT 'pending'
    CHECK (status IN ('pending', 'active', 'expired', 'cancelled')),
  pricing_type text NOT NULL
    CHECK (pricing_type IN ('free', 'paid', 'subscription')),
  price_cents integer NOT NULL DEFAULT 0 CHECK (price_cents >= 0),
  currency text NOT NULL DEFAULT 'usd',
  stripe_checkout_session_id text,
  stripe_payment_intent_id text,
  stripe_subscription_id text,
  granted_at timestamptz,
  expires_at timestamptz,
  granted_by uuid REFERENCES auth.users(id) ON DELETE SET NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_marketplace_entitlements_org_asset_active
  ON public.marketplace_asset_entitlements (org_id, asset_id)
  WHERE status = 'active';

CREATE UNIQUE INDEX IF NOT EXISTS idx_marketplace_entitlements_checkout_session
  ON public.marketplace_asset_entitlements (stripe_checkout_session_id)
  WHERE stripe_checkout_session_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_marketplace_entitlements_org
  ON public.marketplace_asset_entitlements (org_id, created_at DESC);

COMMENT ON TABLE public.marketplace_asset_entitlements IS
  'Org entitlement to install paid/subscription marketplace assets (MKT-AUDIT-12.1).';

ALTER TABLE public.marketplace_assets
  ADD COLUMN IF NOT EXISTS partner_registry_id uuid
    REFERENCES public.partner_connector_registry(id) ON DELETE SET NULL;

CREATE INDEX IF NOT EXISTS idx_marketplace_assets_partner_registry
  ON public.marketplace_assets (partner_registry_id)
  WHERE partner_registry_id IS NOT NULL;

COMMENT ON COLUMN public.marketplace_assets.partner_registry_id IS
  'Optional link to federated partner connector registry row (MKT-AUDIT-13.1).';

ALTER TABLE public.marketplace_asset_entitlements ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "marketplace_entitlements_org_select" ON public.marketplace_asset_entitlements;
CREATE POLICY "marketplace_entitlements_org_select"
  ON public.marketplace_asset_entitlements FOR SELECT
  USING (
    org_id IN (
      SELECT om.org_id FROM public.organization_members om WHERE om.user_id = auth.uid()
    )
  );

DROP TRIGGER IF EXISTS marketplace_asset_entitlements_updated_at ON public.marketplace_asset_entitlements;
CREATE TRIGGER marketplace_asset_entitlements_updated_at
BEFORE UPDATE ON public.marketplace_asset_entitlements
FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();
