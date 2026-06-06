-- STA-96: Marketplace v2 — partner Connect accounts, connector pricing, usage ledger

CREATE TABLE public.marketplace_partner_accounts (
  org_id uuid PRIMARY KEY REFERENCES public.organizations(id) ON DELETE CASCADE,
  stripe_connect_account_id text UNIQUE,
  connect_status text NOT NULL DEFAULT 'pending'
    CHECK (connect_status IN ('pending', 'onboarding', 'active', 'restricted', 'disabled')),
  charges_enabled boolean NOT NULL DEFAULT false,
  payouts_enabled boolean NOT NULL DEFAULT false,
  details_submitted boolean NOT NULL DEFAULT false,
  onboarding_completed_at timestamptz,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE public.marketplace_connector_pricing (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  registry_id uuid NOT NULL REFERENCES public.partner_connector_registry(id) ON DELETE CASCADE,
  partner_org_id uuid NOT NULL REFERENCES public.organizations(id) ON DELETE CASCADE,
  pricing_model text NOT NULL DEFAULT 'free'
    CHECK (pricing_model IN ('free', 'flat_monthly', 'per_invocation')),
  price_cents integer NOT NULL DEFAULT 0 CHECK (price_cents >= 0),
  currency text NOT NULL DEFAULT 'usd',
  platform_fee_bps integer NOT NULL DEFAULT 2000
    CHECK (platform_fee_bps >= 0 AND platform_fee_bps <= 10000),
  stripe_price_id text,
  active boolean NOT NULL DEFAULT true,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT marketplace_connector_pricing_registry_unique UNIQUE (registry_id)
);

CREATE INDEX idx_marketplace_pricing_partner_org
  ON public.marketplace_connector_pricing(partner_org_id);

CREATE TABLE public.marketplace_connector_installs (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  registry_id uuid NOT NULL REFERENCES public.partner_connector_registry(id) ON DELETE CASCADE,
  partner_org_id uuid NOT NULL REFERENCES public.organizations(id) ON DELETE CASCADE,
  customer_org_id uuid NOT NULL REFERENCES public.organizations(id) ON DELETE CASCADE,
  connector_id uuid REFERENCES public.connectors(id) ON DELETE SET NULL,
  status text NOT NULL DEFAULT 'active'
    CHECK (status IN ('active', 'cancelled')),
  stripe_subscription_id text,
  installed_at timestamptz NOT NULL DEFAULT now(),
  cancelled_at timestamptz,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT marketplace_install_unique UNIQUE (registry_id, customer_org_id)
);

CREATE INDEX idx_marketplace_installs_partner_org
  ON public.marketplace_connector_installs(partner_org_id);
CREATE INDEX idx_marketplace_installs_customer_org
  ON public.marketplace_connector_installs(customer_org_id);

CREATE TABLE public.marketplace_usage_events (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  registry_id uuid NOT NULL REFERENCES public.partner_connector_registry(id) ON DELETE CASCADE,
  partner_org_id uuid NOT NULL REFERENCES public.organizations(id) ON DELETE CASCADE,
  customer_org_id uuid NOT NULL REFERENCES public.organizations(id) ON DELETE CASCADE,
  connector_id uuid,
  action text NOT NULL,
  quantity integer NOT NULL DEFAULT 1 CHECK (quantity > 0),
  unit_price_cents integer NOT NULL DEFAULT 0 CHECK (unit_price_cents >= 0),
  gross_amount_cents integer NOT NULL DEFAULT 0 CHECK (gross_amount_cents >= 0),
  platform_fee_cents integer NOT NULL DEFAULT 0 CHECK (platform_fee_cents >= 0),
  partner_earnings_cents integer NOT NULL DEFAULT 0 CHECK (partner_earnings_cents >= 0),
  currency text NOT NULL DEFAULT 'usd',
  idempotency_key text NOT NULL UNIQUE,
  transfer_status text NOT NULL DEFAULT 'pending'
    CHECK (transfer_status IN ('pending', 'transferred', 'skipped', 'failed')),
  stripe_transfer_id text,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX idx_marketplace_usage_partner_org
  ON public.marketplace_usage_events(partner_org_id, created_at DESC);
CREATE INDEX idx_marketplace_usage_customer_org
  ON public.marketplace_usage_events(customer_org_id, created_at DESC);

ALTER TABLE public.marketplace_partner_accounts ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.marketplace_connector_pricing ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.marketplace_connector_installs ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.marketplace_usage_events ENABLE ROW LEVEL SECURITY;
