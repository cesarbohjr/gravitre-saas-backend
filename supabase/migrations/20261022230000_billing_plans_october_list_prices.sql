-- New public catalog prices only. Existing Stripe subscriptions retain their original Price IDs.
-- Apply only alongside the corresponding new Stripe Price objects and checkout env configuration.
UPDATE public.billing_plans SET price_usd = 79 WHERE code = 'node';
UPDATE public.billing_plans SET price_usd = 249 WHERE code = 'control';
UPDATE public.billing_plans SET price_usd = 599 WHERE code = 'command';
