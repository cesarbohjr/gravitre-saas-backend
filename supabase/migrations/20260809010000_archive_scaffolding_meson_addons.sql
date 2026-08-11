-- Archive scaffolding Meson addon catalog SKUs that were never product-authorized,
-- Stripe-wired, or built behind require_addon. Keep rows for audit history.
-- Same honesty class as voice_interface purchase-gate retirement.

ALTER TABLE public.meson_addon_catalog
  ADD COLUMN IF NOT EXISTS archived_at timestamptz;

COMMENT ON COLUMN public.meson_addon_catalog.archived_at IS
  'When set, row is hidden from customer-facing Meson Addons. Preserved for audit.';

-- Scaffolding SKUs from 20260428011000 (never authorized / never Stripe-wired / never gated).
UPDATE public.meson_addon_catalog
SET
  archived_at = COALESCE(archived_at, now()),
  monthly_price_usd = 0,
  name = CASE code
    WHEN 'multi_language' THEN 'Multi-language (archived — scaffolding)'
    WHEN 'advanced_analytics' THEN 'Advanced Analytics (archived — scaffolding)'
    WHEN 'compliance_pack' THEN 'Compliance Pack (archived — scaffolding)'
    WHEN 'custom_model_training' THEN 'Custom Model Training (archived — scaffolding)'
    ELSE name
  END,
  description = CASE code
    WHEN 'multi_language' THEN
      'Archived. Seeded as optional catalog scaffolding; never product-authorized or Stripe-wired.'
    WHEN 'advanced_analytics' THEN
      'Archived. Seeded as optional catalog scaffolding; never product-authorized or Stripe-wired.'
    WHEN 'compliance_pack' THEN
      'Archived. Seeded as optional catalog scaffolding; never product-authorized or Stripe-wired.'
    WHEN 'custom_model_training' THEN
      'Archived. Seeded as optional catalog scaffolding; never product-authorized or Stripe-wired.'
    ELSE description
  END
WHERE code IN (
  'multi_language',
  'advanced_analytics',
  'compliance_pack',
  'custom_model_training'
);

-- Align prior voice purchase-gate retirement with explicit archive timestamp.
UPDATE public.meson_addon_catalog
SET archived_at = COALESCE(archived_at, now())
WHERE code = 'voice_interface';

-- Clear inert JSON flags for archived scaffolding codes (zero functional gates existed).
UPDATE public.subscriptions
SET
  meson_addons = COALESCE(
    (
      SELECT jsonb_agg(to_jsonb(elem) ORDER BY elem)
      FROM jsonb_array_elements_text(COALESCE(meson_addons, '[]'::jsonb)) AS elem
      WHERE elem NOT IN (
        'multi_language',
        'advanced_analytics',
        'compliance_pack',
        'custom_model_training',
        'voice_interface'
      )
    ),
    '[]'::jsonb
  ),
  updated_at = now()
WHERE meson_addons IS NOT NULL
  AND meson_addons::text <> '[]'
  AND EXISTS (
    SELECT 1
    FROM jsonb_array_elements_text(COALESCE(meson_addons, '[]'::jsonb)) AS elem
    WHERE elem IN (
      'multi_language',
      'advanced_analytics',
      'compliance_pack',
      'custom_model_training',
      'voice_interface'
    )
  );
