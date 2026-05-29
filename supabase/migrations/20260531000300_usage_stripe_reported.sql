-- Track which usage_tracking rows have been reported to Stripe metered billing.
-- Reporting only ever sends rows where stripe_reported_at IS NULL and then marks
-- them, so re-running the sync never double-reports (Stripe meter events are
-- additive). Safe to re-run.

ALTER TABLE public.usage_tracking
  ADD COLUMN IF NOT EXISTS stripe_reported_at timestamptz;

-- Partial index to quickly find unreported AI-credit usage per org.
CREATE INDEX IF NOT EXISTS idx_usage_tracking_unreported
  ON public.usage_tracking (org_id, metric_type)
  WHERE stripe_reported_at IS NULL;
