-- Gravitre Marketplace 3.0: additive asset/entity types.
-- No new public tables are created in this migration.
-- Existing Marketplace assets/install rows remain valid.

ALTER TABLE public.marketplace_assets
  DROP CONSTRAINT IF EXISTS marketplace_assets_asset_type_check;

ALTER TABLE public.marketplace_assets
  ADD CONSTRAINT marketplace_assets_asset_type_check
  CHECK (asset_type IN (
    'ai_agent',
    'workflow',
    'knowledge_pack',
    'department_pack',
    'connector_config',
    'intelligence_pack',
    'capability_package',
    'play',
    'dataset_pack',
    'dashboard_pack',
    'outcome_pack'
  ));

ALTER TABLE public.marketplace_installs
  DROP CONSTRAINT IF EXISTS marketplace_installs_installed_entity_type_check;

ALTER TABLE public.marketplace_installs
  ADD CONSTRAINT marketplace_installs_installed_entity_type_check
  CHECK (installed_entity_type IN (
    'operator',
    'agent',
    'workflow',
    'rag_source',
    'connector',
    'department_pack',
    'knowledge_pack',
    'intelligence_pack',
    'capability_package',
    'play',
    'dataset_pack',
    'dashboard_pack',
    'outcome_pack'
  ));

COMMENT ON COLUMN public.marketplace_assets.asset_type IS
  'Marketplace asset type. Marketplace 3.0 adds play, dataset_pack, dashboard_pack, and outcome_pack as first-class catalog primitives.';


-- Installed Dataset Pack definitions. These are configuration/measurement
-- contracts; they do not introduce an execution runtime.
CREATE TABLE IF NOT EXISTS public.marketplace_dataset_pack_installations (
  id uuid PRIMARY KEY,
  org_id uuid NOT NULL REFERENCES public.organizations(id) ON DELETE CASCADE,
  asset_id uuid NOT NULL REFERENCES public.marketplace_assets(id) ON DELETE CASCADE,
  source_outcome_pack_id uuid,
  status text NOT NULL DEFAULT 'active'
    CHECK (status IN ('active', 'archived')),
  config jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_by uuid,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_marketplace_dataset_pack_installations_org
  ON public.marketplace_dataset_pack_installations (org_id, status);

CREATE INDEX IF NOT EXISTS idx_marketplace_dataset_pack_installations_asset
  ON public.marketplace_dataset_pack_installations (asset_id);

-- Installed Dashboard Pack definitions. Dashboard rendering/aggregation remains
-- owned by Gravitre's existing dashboard and outcome telemetry services.
CREATE TABLE IF NOT EXISTS public.marketplace_dashboard_pack_installations (
  id uuid PRIMARY KEY,
  org_id uuid NOT NULL REFERENCES public.organizations(id) ON DELETE CASCADE,
  asset_id uuid NOT NULL REFERENCES public.marketplace_assets(id) ON DELETE CASCADE,
  source_outcome_pack_id uuid,
  status text NOT NULL DEFAULT 'active'
    CHECK (status IN ('active', 'archived')),
  config jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_by uuid,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_marketplace_dashboard_pack_installations_org
  ON public.marketplace_dashboard_pack_installations (org_id, status);

CREATE INDEX IF NOT EXISTS idx_marketplace_dashboard_pack_installations_asset
  ON public.marketplace_dashboard_pack_installations (asset_id);

ALTER TABLE public.marketplace_dataset_pack_installations ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.marketplace_dashboard_pack_installations ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS marketplace_dataset_pack_installations_org_scope
  ON public.marketplace_dataset_pack_installations;
CREATE POLICY marketplace_dataset_pack_installations_org_scope
  ON public.marketplace_dataset_pack_installations
  FOR ALL
  TO authenticated
  USING (
    org_id IN (
      SELECT om.org_id
      FROM public.organization_members om
      WHERE om.user_id = (SELECT auth.uid())
    )
  )
  WITH CHECK (
    org_id IN (
      SELECT om.org_id
      FROM public.organization_members om
      WHERE om.user_id = (SELECT auth.uid())
    )
  );

DROP POLICY IF EXISTS marketplace_dashboard_pack_installations_org_scope
  ON public.marketplace_dashboard_pack_installations;
CREATE POLICY marketplace_dashboard_pack_installations_org_scope
  ON public.marketplace_dashboard_pack_installations
  FOR ALL
  TO authenticated
  USING (
    org_id IN (
      SELECT om.org_id
      FROM public.organization_members om
      WHERE om.user_id = (SELECT auth.uid())
    )
  )
  WITH CHECK (
    org_id IN (
      SELECT om.org_id
      FROM public.organization_members om
      WHERE om.user_id = (SELECT auth.uid())
    )
  );

COMMENT ON TABLE public.marketplace_dataset_pack_installations IS
  'Marketplace 3.0 tenant dataset/metric contract installations. No separate execution engine.';
COMMENT ON TABLE public.marketplace_dashboard_pack_installations IS
  'Marketplace 3.0 tenant KPI/dashboard contract installations backed by existing Gravitre telemetry.';
