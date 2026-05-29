-- Idempotent usage metering.
--
-- record_usage()/record_overage() previously inserted unconditionally, so a
-- client retry or a re-processed event double-counted AI credits. Add an
-- idempotency_key and a UNIQUE (org_id, idempotency_key) constraint so the
-- application can INSERT ... ON CONFLICT DO NOTHING.
--
-- A unique INDEX (not a named constraint) is used so the statement is
-- idempotent via IF NOT EXISTS; it still backs ON CONFLICT (org_id,
-- idempotency_key). Existing rows have a NULL key and remain valid (NULLs are
-- distinct under a unique index), so this is safe to apply to populated tables.

ALTER TABLE public.usage_tracking
  ADD COLUMN IF NOT EXISTS idempotency_key text;

CREATE UNIQUE INDEX IF NOT EXISTS uq_usage_tracking_org_idempotency
  ON public.usage_tracking (org_id, idempotency_key);

ALTER TABLE public.overage_usage
  ADD COLUMN IF NOT EXISTS idempotency_key text;

CREATE UNIQUE INDEX IF NOT EXISTS uq_overage_usage_org_idempotency
  ON public.overage_usage (org_id, idempotency_key);
