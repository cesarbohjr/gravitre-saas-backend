-- Part 6 of the storage migration (see 20261020081535_storage_retention_metering.sql).

-- -----------------------------------------------------------------------------
-- 4) Storage usage snapshots
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.org_storage_usage_snapshots (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id uuid NOT NULL REFERENCES public.organizations(id) ON DELETE CASCADE,
  snapshot_date date NOT NULL DEFAULT (now() AT TIME ZONE 'utc')::date,
  captured_at timestamptz NOT NULL DEFAULT now(),
  total_bytes bigint NOT NULL DEFAULT 0 CHECK (total_bytes >= 0),
  categories jsonb NOT NULL DEFAULT '{}'::jsonb,
  method text NOT NULL DEFAULT 'proportional-relation-size-v1',
  CONSTRAINT org_storage_usage_snapshots_once_per_day UNIQUE (org_id, snapshot_date)
);

CREATE INDEX IF NOT EXISTS idx_org_storage_usage_snapshots_org_captured
  ON public.org_storage_usage_snapshots (org_id, captured_at DESC);

ALTER TABLE public.org_storage_usage_snapshots ENABLE ROW LEVEL SECURITY;

-- Prod ran this part without the DROP (the table was new, so the end state is the
-- same); the DROP keeps the file re-runnable.
DROP POLICY IF EXISTS org_storage_usage_snapshots_read ON public.org_storage_usage_snapshots;
CREATE POLICY org_storage_usage_snapshots_read ON public.org_storage_usage_snapshots FOR SELECT
  USING (org_id IN (SELECT om.org_id FROM public.organization_members om WHERE om.user_id = auth.uid()));

-- Members read their own org's snapshots; only the service role writes.
REVOKE ALL ON public.org_storage_usage_snapshots FROM anon, authenticated;
GRANT SELECT ON public.org_storage_usage_snapshots TO authenticated;
GRANT ALL ON public.org_storage_usage_snapshots TO service_role;
