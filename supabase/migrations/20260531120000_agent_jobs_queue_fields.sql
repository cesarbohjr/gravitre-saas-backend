-- Add queue timing fields to agent_jobs for async execution tracking.

ALTER TABLE public.agent_jobs
  ADD COLUMN IF NOT EXISTS queued_at timestamptz,
  ADD COLUMN IF NOT EXISTS timeout_at timestamptz,
  ADD COLUMN IF NOT EXISTS retry_count int NOT NULL DEFAULT 0;

-- Backfill queued_at from created_at for existing rows.
UPDATE public.agent_jobs
SET queued_at = created_at
WHERE queued_at IS NULL;
