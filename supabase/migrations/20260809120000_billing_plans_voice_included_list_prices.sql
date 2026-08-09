-- Update public list prices for Node/Control/Command after voice-included value capture.
-- Stripe Price objects are unchanged for existing subscribers (grandfathered on prior Prices);
-- this table is catalog/list-price SoT for entitlements UI and plan metadata.

UPDATE public.billing_plans SET price_usd = 59 WHERE code = 'node';
UPDATE public.billing_plans SET price_usd = 149 WHERE code = 'control';
UPDATE public.billing_plans SET price_usd = 349 WHERE code = 'command';
