-- MSP partner program: wholesale billing and client workspaces.
--
-- An MSP pays Gravitre the wholesale price for each client workspace and bills
-- the client its own price. This migration stores who manages whom and how the
-- client is billed. It does NOT widen tenant access: every new table is
-- service_role only (RLS forced, no policies), and the parent link written to
-- organizations.parent_org_id still grants no data access by itself.
--
-- Idempotent: safe to run more than once.
--
-- Preflight (read-only):
--   SELECT column_name FROM information_schema.columns
--    WHERE table_schema = 'public' AND table_name IN ('organizations','org_billing')
--      AND column_name IN ('account_type','billing_source','billed_by_org_id');
--   SELECT to_regclass('public.msp_clients'), to_regclass('public.msp_billing_accounts');
--
-- Rollback (only before any MSP has been billed; destroys partner data):
--   DROP TRIGGER IF EXISTS trg_msp_clients_guard ON public.msp_clients;
--   DROP FUNCTION IF EXISTS public.msp_clients_guard();
--   DROP TABLE IF EXISTS public.msp_billing_accounts;
--   DROP TABLE IF EXISTS public.msp_clients;
--   ALTER TABLE public.org_billing DROP COLUMN IF EXISTS billed_by_org_id;
--   ALTER TABLE public.org_billing DROP COLUMN IF EXISTS billing_source;
--   ALTER TABLE public.organizations DROP COLUMN IF EXISTS account_type;
--   UPDATE public.organizations SET parent_org_id = NULL WHERE parent_org_id IS NOT NULL;
BEGIN;

-- 1. Account type -------------------------------------------------------------
ALTER TABLE public.organizations
  ADD COLUMN IF NOT EXISTS account_type text NOT NULL DEFAULT 'standard';

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint WHERE conname = 'organizations_account_type_check'
  ) THEN
    ALTER TABLE public.organizations
      ADD CONSTRAINT organizations_account_type_check
      CHECK (account_type IN ('standard', 'msp'));
  END IF;
END $$;

COMMENT ON COLUMN public.organizations.account_type IS
  'standard or msp. An msp org manages client workspaces and pays wholesale for them.';

-- 2. Billing source on org_billing ---------------------------------------------
ALTER TABLE public.org_billing
  ADD COLUMN IF NOT EXISTS billing_source text NOT NULL DEFAULT 'self';
ALTER TABLE public.org_billing
  ADD COLUMN IF NOT EXISTS billed_by_org_id uuid REFERENCES public.organizations(id) ON DELETE SET NULL;

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint WHERE conname = 'org_billing_billing_source_check'
  ) THEN
    ALTER TABLE public.org_billing
      ADD CONSTRAINT org_billing_billing_source_check
      CHECK (billing_source IN ('self', 'msp'));
  END IF;
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint WHERE conname = 'org_billing_msp_source_consistent'
  ) THEN
    ALTER TABLE public.org_billing
      ADD CONSTRAINT org_billing_msp_source_consistent
      CHECK (billing_source = 'self' OR billed_by_org_id IS NOT NULL);
  END IF;
END $$;

CREATE INDEX IF NOT EXISTS idx_org_billing_billed_by
  ON public.org_billing (billed_by_org_id)
  WHERE billed_by_org_id IS NOT NULL;

-- 3. MSP -> client relationships ----------------------------------------------
CREATE TABLE IF NOT EXISTS public.msp_clients (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  msp_org_id uuid NOT NULL REFERENCES public.organizations(id) ON DELETE CASCADE,
  client_org_id uuid NOT NULL REFERENCES public.organizations(id) ON DELETE CASCADE,
  plan_code text NOT NULL CHECK (plan_code IN ('node', 'control', 'command')),
  resale_price_cents integer CHECK (resale_price_cents IS NULL OR resale_price_cents BETWEEN 0 AND 100000000),
  resale_currency text NOT NULL DEFAULT 'usd' CHECK (resale_currency ~ '^[a-z]{3}$'),
  resale_interval text NOT NULL DEFAULT 'month' CHECK (resale_interval IN ('month', 'year')),
  status text NOT NULL DEFAULT 'pending_client_approval'
    CHECK (status IN ('pending_client_approval', 'active', 'detached')),
  access_level text CHECK (access_level IS NULL OR access_level IN ('full', 'health_only')),
  origin text NOT NULL DEFAULT 'linked' CHECK (origin IN ('created', 'linked')),
  -- MSP members added to the client org by a "full" approval; removed on detach.
  granted_user_ids uuid[] NOT NULL DEFAULT '{}',
  created_by uuid NOT NULL,
  approved_by uuid,
  approved_at timestamptz,
  detached_by uuid,
  detached_at timestamptz,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT msp_clients_not_self CHECK (client_org_id <> msp_org_id),
  CONSTRAINT msp_clients_active_has_access CHECK (status <> 'active' OR access_level IS NOT NULL),
  CONSTRAINT msp_clients_active_approved CHECK (status <> 'active' OR approved_at IS NOT NULL),
  CONSTRAINT msp_clients_detached_stamped CHECK (status <> 'detached' OR detached_at IS NOT NULL)
);

-- A workspace has at most one live (pending or active) MSP relationship.
-- Detached rows stay as history and do not block a later link.
CREATE UNIQUE INDEX IF NOT EXISTS uq_msp_clients_live_client
  ON public.msp_clients (client_org_id)
  WHERE status <> 'detached';
CREATE INDEX IF NOT EXISTS idx_msp_clients_msp_status
  ON public.msp_clients (msp_org_id, status);

-- Client cannot itself be an MSP; the managing org must be an MSP.
CREATE OR REPLACE FUNCTION public.msp_clients_guard()
RETURNS trigger
LANGUAGE plpgsql
SECURITY INVOKER
SET search_path = pg_catalog, public
AS $$
DECLARE
  v_msp_type text;
  v_client_type text;
BEGIN
  IF NEW.status = 'detached' THEN
    RETURN NEW;
  END IF;
  SELECT account_type INTO v_msp_type FROM public.organizations WHERE id = NEW.msp_org_id;
  SELECT account_type INTO v_client_type FROM public.organizations WHERE id = NEW.client_org_id;
  IF v_msp_type IS DISTINCT FROM 'msp' THEN
    RAISE EXCEPTION 'Managing organization is not an MSP' USING ERRCODE = 'check_violation';
  END IF;
  IF v_client_type IS DISTINCT FROM 'standard' THEN
    RAISE EXCEPTION 'An MSP cannot be managed as a client' USING ERRCODE = 'check_violation';
  END IF;
  NEW.updated_at := now();
  RETURN NEW;
END;
$$;
REVOKE ALL ON FUNCTION public.msp_clients_guard() FROM PUBLIC, anon, authenticated;

DROP TRIGGER IF EXISTS trg_msp_clients_guard ON public.msp_clients;
CREATE TRIGGER trg_msp_clients_guard
BEFORE INSERT OR UPDATE ON public.msp_clients
FOR EACH ROW EXECUTE FUNCTION public.msp_clients_guard();

ALTER TABLE public.msp_clients ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.msp_clients FORCE ROW LEVEL SECURITY;
REVOKE ALL ON public.msp_clients FROM PUBLIC, anon, authenticated;
GRANT SELECT, INSERT, UPDATE ON public.msp_clients TO service_role;

-- 4. The MSP's single wholesale Stripe subscription ----------------------------
CREATE TABLE IF NOT EXISTS public.msp_billing_accounts (
  msp_org_id uuid PRIMARY KEY REFERENCES public.organizations(id) ON DELETE CASCADE,
  stripe_customer_id text,
  stripe_subscription_id text UNIQUE,
  status text NOT NULL DEFAULT 'none'
    CHECK (status IN ('none', 'incomplete', 'trialing', 'active', 'past_due', 'canceled')),
  current_period_end timestamptz,
  cancel_at_period_end boolean NOT NULL DEFAULT false,
  last_synced_quantities jsonb NOT NULL DEFAULT '{}'::jsonb,
  last_synced_at timestamptz,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

ALTER TABLE public.msp_billing_accounts ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.msp_billing_accounts FORCE ROW LEVEL SECURITY;
REVOKE ALL ON public.msp_billing_accounts FROM PUBLIC, anon, authenticated;
GRANT SELECT, INSERT, UPDATE ON public.msp_billing_accounts TO service_role;

-- Deliberately no authenticated policies and no SECURITY DEFINER functions.
-- FastAPI verifies the caller's role in the MSP or client org on every request.
COMMIT;
