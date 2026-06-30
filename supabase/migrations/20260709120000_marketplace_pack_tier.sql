-- Phase 8: Department pack tier banding for marketplace pricing framework.

ALTER TABLE public.marketplace_assets
  ADD COLUMN IF NOT EXISTS pack_tier smallint
  CHECK (pack_tier IS NULL OR (pack_tier >= 1 AND pack_tier <= 3));

COMMENT ON COLUMN public.marketplace_assets.pack_tier IS
  'Department pack complexity band (1=starter, 2=multi-agent, 3=command-center). Drives recommended one-time unlock price.';

-- Marketing Operations Pack: Tier 2 ($149 one-time) per Phase 8.3 framework.
-- Platform subscription (Node/Control/Command) and AI usage are billed separately.
UPDATE public.marketplace_assets
SET
  pricing_type = 'paid',
  price_cents = 14900,
  pack_tier = 2,
  updated_at = now()
WHERE slug = 'marketing-operations-pack';
