-- Correct department packs that were seeded as subscription back to one-time paid unlock.
UPDATE public.marketplace_assets
SET
  pricing_type = 'paid',
  updated_at = now()
WHERE asset_type = 'department_pack'
  AND pricing_type = 'subscription';
