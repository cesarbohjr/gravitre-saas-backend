-- Voice becomes plan-included (org ON/OFF), not a $49 Meson purchase gate.
-- Prepaid top-ups + auto-top-up settings for Voice Minutes.

ALTER TABLE public.subscriptions
  ADD COLUMN IF NOT EXISTS voice_enabled boolean NOT NULL DEFAULT true;

ALTER TABLE public.subscriptions
  ADD COLUMN IF NOT EXISTS voice_minutes_prepaid integer NOT NULL DEFAULT 0;

ALTER TABLE public.subscriptions
  ADD COLUMN IF NOT EXISTS voice_auto_topup_enabled boolean NOT NULL DEFAULT false;

ALTER TABLE public.subscriptions
  ADD COLUMN IF NOT EXISTS voice_auto_topup_minutes integer NOT NULL DEFAULT 60;

ALTER TABLE public.subscriptions
  ADD COLUMN IF NOT EXISTS voice_auto_topup_threshold_minutes integer NOT NULL DEFAULT 15;

ALTER TABLE public.subscriptions
  ADD COLUMN IF NOT EXISTS voice_auto_topup_max_charge_cents integer NOT NULL DEFAULT 3600;

COMMENT ON COLUMN public.subscriptions.voice_enabled IS
  'Org-level voice ON/OFF. Default true — plan-included; not a paid Meson addon.';
COMMENT ON COLUMN public.subscriptions.voice_minutes_prepaid IS
  'Purchased Voice Minutes remaining this cycle (added to plan allotment).';
COMMENT ON COLUMN public.subscriptions.voice_auto_topup_max_charge_cents IS
  'Hard cap per automatic top-up charge (default $36 = 300 min @ $0.12).';

-- Retire Voice Interface as a priced Meson catalog purchase (keep row for history).
UPDATE public.meson_addon_catalog
SET
  name = 'Voice Interface (retired — plan included)',
  description = 'Retired. Voice is included with every plan. Use Billing & Plan for top-ups and org voice ON/OFF.',
  monthly_price_usd = 0
WHERE code = 'voice_interface';

CREATE TABLE IF NOT EXISTS public.billing_topup_events (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id uuid NOT NULL REFERENCES public.organizations(id) ON DELETE CASCADE,
  metric_type text NOT NULL,
  minutes integer NOT NULL,
  amount_cents integer NOT NULL,
  currency text NOT NULL DEFAULT 'usd',
  stripe_checkout_session_id text,
  stripe_payment_intent_id text,
  source text NOT NULL DEFAULT 'manual', -- manual | auto
  status text NOT NULL DEFAULT 'pending', -- pending | completed | failed
  metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now(),
  completed_at timestamptz
);

CREATE UNIQUE INDEX IF NOT EXISTS billing_topup_events_session_uidx
  ON public.billing_topup_events (stripe_checkout_session_id)
  WHERE stripe_checkout_session_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS billing_topup_events_org_created_idx
  ON public.billing_topup_events (org_id, created_at DESC);
