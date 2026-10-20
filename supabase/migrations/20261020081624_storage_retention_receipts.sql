-- Part 2 of the storage migration (see 20261020081535_storage_retention_metering.sql).

CREATE INDEX IF NOT EXISTS idx_org_legal_holds_active
  ON public.org_legal_holds (org_id)
  WHERE released_at IS NULL;

COMMENT ON TABLE public.org_legal_holds IS
  'While a hold has released_at NULL, data retention skips the org entirely (nothing counted or deleted).';

ALTER TABLE public.org_legal_holds ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON public.org_legal_holds FROM anon, authenticated;
GRANT ALL ON public.org_legal_holds TO service_role;

-- -----------------------------------------------------------------------------
-- 2) Retention receipts
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.data_retention_runs (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  started_at timestamptz NOT NULL DEFAULT now(),
  finished_at timestamptz,
  dry_run boolean NOT NULL,
  status text NOT NULL DEFAULT 'running'
    CHECK (status IN ('running', 'completed', 'partial', 'failed', 'abandoned')),
  settings jsonb NOT NULL DEFAULT '{}'::jsonb,
  totals jsonb NOT NULL DEFAULT '{}'::jsonb,
  details jsonb NOT NULL DEFAULT '{}'::jsonb,
  error text
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_data_retention_runs_one_running
  ON public.data_retention_runs ((true))
  WHERE status = 'running';

CREATE INDEX IF NOT EXISTS idx_data_retention_runs_started
  ON public.data_retention_runs (started_at DESC);

ALTER TABLE public.data_retention_runs ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON public.data_retention_runs FROM anon, authenticated;
GRANT ALL ON public.data_retention_runs TO service_role;
