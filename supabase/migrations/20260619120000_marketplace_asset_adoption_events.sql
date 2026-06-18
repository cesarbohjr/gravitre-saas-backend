-- STA-245 / MKT-AUDIT-10.2: Per-asset adoption events for unified marketplace assets
-- Distinct from partner connector billing table marketplace_usage_events.

CREATE TABLE IF NOT EXISTS public.marketplace_asset_adoption_events (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id uuid NOT NULL REFERENCES public.organizations(id) ON DELETE CASCADE,
  asset_id uuid NOT NULL REFERENCES public.marketplace_assets(id) ON DELETE CASCADE,
  install_id uuid REFERENCES public.marketplace_installs(id) ON DELETE SET NULL,
  event_type text NOT NULL
    CHECK (event_type IN ('agent_run', 'workflow_run', 'view')),
  entity_type text
    CHECK (entity_type IS NULL OR entity_type IN ('agent', 'workflow')),
  entity_id uuid,
  source_id text,
  metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
  idempotency_key text NOT NULL UNIQUE,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_marketplace_adoption_org_created
  ON public.marketplace_asset_adoption_events (org_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_marketplace_adoption_asset
  ON public.marketplace_asset_adoption_events (asset_id, created_at DESC);

COMMENT ON TABLE public.marketplace_asset_adoption_events IS
  'Unified marketplace asset adoption/usage events (agent runs, workflow runs). Separate from partner connector marketplace_usage_events.';

ALTER TABLE public.marketplace_asset_adoption_events ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "marketplace_adoption_events_org_select" ON public.marketplace_asset_adoption_events;
CREATE POLICY "marketplace_adoption_events_org_select"
  ON public.marketplace_asset_adoption_events FOR SELECT
  USING (
    org_id IN (
      SELECT om.org_id FROM public.organization_members om WHERE om.user_id = auth.uid()
    )
  );
