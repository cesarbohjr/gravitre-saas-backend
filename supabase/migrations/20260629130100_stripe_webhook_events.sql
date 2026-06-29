-- Stripe webhook idempotency: deduplicate event.id before side effects.
CREATE TABLE IF NOT EXISTS public.stripe_webhook_events (
  stripe_event_id TEXT PRIMARY KEY,
  event_type TEXT NOT NULL,
  processed_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  org_id UUID
);

CREATE INDEX IF NOT EXISTS idx_stripe_webhook_events_org_id
  ON public.stripe_webhook_events (org_id);

ALTER TABLE public.stripe_webhook_events ENABLE ROW LEVEL SECURITY;

COMMENT ON TABLE public.stripe_webhook_events IS
  'Processed Stripe webhook event IDs for idempotent handler retries.';
