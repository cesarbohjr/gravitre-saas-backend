-- Epic 2: Gravitre Marketplace unified asset data model (MKT-2.1 – MKT-2.5)
-- Extends STA-121 department packs + partner marketplace; does not replace partner tables.
--
-- RLS NOTE (MKT-2.3): marketplace_assets SELECT intentionally allows cross-tenant reads for
-- published public assets. All other marketplace tables use standard org_id isolation.

-- ---------------------------------------------------------------------------
-- MKT-2.1: Publishers
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS public.marketplace_publishers (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  slug text NOT NULL,
  display_name text NOT NULL,
  org_id uuid REFERENCES public.organizations(id) ON DELETE CASCADE,
  description text,
  logo_url text,
  website_url text,
  verified boolean NOT NULL DEFAULT false,
  status text NOT NULL DEFAULT 'active'
    CHECK (status IN ('active', 'suspended')),
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT marketplace_publishers_slug_key UNIQUE (slug)
);

CREATE INDEX IF NOT EXISTS idx_marketplace_publishers_org
  ON public.marketplace_publishers (org_id)
  WHERE org_id IS NOT NULL;

INSERT INTO public.marketplace_publishers (slug, display_name, org_id, description, verified, status)
VALUES (
  'gravitre',
  'Gravitre',
  NULL,
  'Gravitre-owned starter library and official marketplace assets.',
  true,
  'active'
)
ON CONFLICT (slug) DO NOTHING;

-- ---------------------------------------------------------------------------
-- MKT-2.2: Assets
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS public.marketplace_assets (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  publisher_id uuid NOT NULL REFERENCES public.marketplace_publishers(id) ON DELETE RESTRICT,
  org_id uuid REFERENCES public.organizations(id) ON DELETE CASCADE,
  slug text NOT NULL,
  title text NOT NULL,
  description text,
  asset_type text NOT NULL
    CHECK (asset_type IN (
      'ai_agent',
      'workflow',
      'knowledge_pack',
      'department_pack',
      'connector_config'
    )),
  category text,
  department text,
  tags text[] NOT NULL DEFAULT '{}'::text[],
  visibility text NOT NULL DEFAULT 'private'
    CHECK (visibility IN ('private', 'internal', 'public')),
  status text NOT NULL DEFAULT 'draft'
    CHECK (status IN ('draft', 'pending_review', 'published', 'archived')),
  pricing_type text NOT NULL DEFAULT 'free'
    CHECK (pricing_type IN ('free', 'paid', 'subscription')),
  price_cents integer NOT NULL DEFAULT 0 CHECK (price_cents >= 0),
  currency text NOT NULL DEFAULT 'usd',
  config jsonb NOT NULL DEFAULT '{}'::jsonb,
  required_connectors jsonb NOT NULL DEFAULT '[]'::jsonb,
  required_permissions jsonb NOT NULL DEFAULT '[]'::jsonb,
  install_variables jsonb NOT NULL DEFAULT '[]'::jsonb,
  install_count integer NOT NULL DEFAULT 0 CHECK (install_count >= 0),
  clone_count integer NOT NULL DEFAULT 0 CHECK (clone_count >= 0),
  average_rating numeric(3, 2),
  review_count integer NOT NULL DEFAULT 0 CHECK (review_count >= 0),
  current_version integer NOT NULL DEFAULT 1 CHECK (current_version >= 1),
  published_at timestamptz,
  published_by uuid REFERENCES auth.users(id) ON DELETE SET NULL,
  cloned_from_asset_id uuid REFERENCES public.marketplace_assets(id) ON DELETE SET NULL,
  created_by uuid REFERENCES auth.users(id) ON DELETE SET NULL,
  search_vector tsvector GENERATED ALWAYS AS (
    setweight(to_tsvector('english', coalesce(title, '')), 'A')
    || setweight(to_tsvector('english', coalesce(description, '')), 'B')
    || setweight(to_tsvector('english', coalesce(category, '')), 'C')
    || setweight(to_tsvector('english', coalesce(department, '')), 'C')
  ) STORED,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT marketplace_assets_slug_key UNIQUE (slug)
);

CREATE INDEX IF NOT EXISTS idx_marketplace_assets_publisher
  ON public.marketplace_assets (publisher_id);
CREATE INDEX IF NOT EXISTS idx_marketplace_assets_org
  ON public.marketplace_assets (org_id)
  WHERE org_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_marketplace_assets_browse
  ON public.marketplace_assets (status, visibility, asset_type);
CREATE INDEX IF NOT EXISTS idx_marketplace_assets_category
  ON public.marketplace_assets (category, department);
CREATE INDEX IF NOT EXISTS idx_marketplace_assets_search
  ON public.marketplace_assets USING gin (search_vector);

-- ---------------------------------------------------------------------------
-- MKT-2.4: Version history, pack composition, installs, reviews, saves
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS public.marketplace_asset_versions (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  asset_id uuid NOT NULL REFERENCES public.marketplace_assets(id) ON DELETE CASCADE,
  version_number integer NOT NULL CHECK (version_number >= 1),
  config jsonb NOT NULL,
  required_connectors jsonb NOT NULL DEFAULT '[]'::jsonb,
  required_permissions jsonb NOT NULL DEFAULT '[]'::jsonb,
  install_variables jsonb NOT NULL DEFAULT '[]'::jsonb,
  change_summary text,
  published_by uuid REFERENCES auth.users(id) ON DELETE SET NULL,
  published_at timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT marketplace_asset_versions_asset_version_key UNIQUE (asset_id, version_number)
);

CREATE INDEX IF NOT EXISTS idx_marketplace_asset_versions_asset
  ON public.marketplace_asset_versions (asset_id, version_number DESC);

CREATE TABLE IF NOT EXISTS public.marketplace_pack_items (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  pack_asset_id uuid NOT NULL REFERENCES public.marketplace_assets(id) ON DELETE CASCADE,
  child_asset_id uuid NOT NULL REFERENCES public.marketplace_assets(id) ON DELETE RESTRICT,
  sort_order integer NOT NULL DEFAULT 0,
  required boolean NOT NULL DEFAULT true,
  created_at timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT marketplace_pack_items_unique UNIQUE (pack_asset_id, child_asset_id),
  CONSTRAINT marketplace_pack_items_not_self CHECK (pack_asset_id <> child_asset_id)
);

CREATE INDEX IF NOT EXISTS idx_marketplace_pack_items_pack
  ON public.marketplace_pack_items (pack_asset_id, sort_order);

CREATE TABLE IF NOT EXISTS public.marketplace_installs (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id uuid NOT NULL REFERENCES public.organizations(id) ON DELETE CASCADE,
  asset_id uuid NOT NULL REFERENCES public.marketplace_assets(id) ON DELETE RESTRICT,
  asset_version integer NOT NULL CHECK (asset_version >= 1),
  installed_entity_type text NOT NULL
    CHECK (installed_entity_type IN (
      'operator',
      'agent',
      'workflow',
      'rag_source',
      'connector',
      'department_pack'
    )),
  installed_entity_id uuid NOT NULL,
  install_variables jsonb NOT NULL DEFAULT '{}'::jsonb,
  status text NOT NULL DEFAULT 'active'
    CHECK (status IN ('active', 'failed', 'uninstalled')),
  installed_by uuid REFERENCES auth.users(id) ON DELETE SET NULL,
  installed_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  metadata jsonb NOT NULL DEFAULT '{}'::jsonb
);

CREATE INDEX IF NOT EXISTS idx_marketplace_installs_org
  ON public.marketplace_installs (org_id, installed_at DESC);
CREATE INDEX IF NOT EXISTS idx_marketplace_installs_asset
  ON public.marketplace_installs (asset_id);
CREATE INDEX IF NOT EXISTS idx_marketplace_installs_entity
  ON public.marketplace_installs (installed_entity_type, installed_entity_id);

CREATE UNIQUE INDEX IF NOT EXISTS idx_marketplace_installs_org_asset_active
  ON public.marketplace_installs (org_id, asset_id)
  WHERE status = 'active';

COMMENT ON COLUMN public.marketplace_installs.installed_entity_id IS
  'Polymorphic FK — validated in application layer (no multi-table FK).';

CREATE TABLE IF NOT EXISTS public.marketplace_reviews (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  asset_id uuid NOT NULL REFERENCES public.marketplace_assets(id) ON DELETE CASCADE,
  org_id uuid NOT NULL REFERENCES public.organizations(id) ON DELETE CASCADE,
  user_id uuid NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  rating integer NOT NULL CHECK (rating >= 1 AND rating <= 5),
  title text,
  body text,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT marketplace_reviews_unique UNIQUE (asset_id, org_id, user_id)
);

CREATE INDEX IF NOT EXISTS idx_marketplace_reviews_asset
  ON public.marketplace_reviews (asset_id, created_at DESC);

CREATE TABLE IF NOT EXISTS public.marketplace_saves (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  asset_id uuid NOT NULL REFERENCES public.marketplace_assets(id) ON DELETE CASCADE,
  org_id uuid NOT NULL REFERENCES public.organizations(id) ON DELETE CASCADE,
  user_id uuid NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  created_at timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT marketplace_saves_unique UNIQUE (asset_id, org_id, user_id)
);

CREATE INDEX IF NOT EXISTS idx_marketplace_saves_user
  ON public.marketplace_saves (org_id, user_id, created_at DESC);

-- ---------------------------------------------------------------------------
-- MKT-2.5: Payout ledger (schema-only — no Stripe wiring in Stage 1)
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS public.marketplace_payouts (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  publisher_id uuid NOT NULL REFERENCES public.marketplace_publishers(id) ON DELETE RESTRICT,
  partner_org_id uuid REFERENCES public.organizations(id) ON DELETE SET NULL,
  asset_id uuid REFERENCES public.marketplace_assets(id) ON DELETE SET NULL,
  install_id uuid REFERENCES public.marketplace_installs(id) ON DELETE SET NULL,
  gross_amount_cents integer NOT NULL DEFAULT 0 CHECK (gross_amount_cents >= 0),
  platform_fee_cents integer NOT NULL DEFAULT 0 CHECK (platform_fee_cents >= 0),
  partner_earnings_cents integer NOT NULL DEFAULT 0 CHECK (partner_earnings_cents >= 0),
  currency text NOT NULL DEFAULT 'usd',
  status text NOT NULL DEFAULT 'pending'
    CHECK (status IN ('pending', 'transferred', 'failed', 'cancelled')),
  stripe_transfer_id text,
  period_start timestamptz,
  period_end timestamptz,
  notes text,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_marketplace_payouts_publisher
  ON public.marketplace_payouts (publisher_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_marketplace_payouts_partner_org
  ON public.marketplace_payouts (partner_org_id)
  WHERE partner_org_id IS NOT NULL;

COMMENT ON TABLE public.marketplace_payouts IS
  'Phase 4 payout ledger only — no Stripe transfer automation in Stage 1 (MKT-2.5).';

-- ---------------------------------------------------------------------------
-- updated_at triggers
-- ---------------------------------------------------------------------------

DROP TRIGGER IF EXISTS marketplace_publishers_updated_at ON public.marketplace_publishers;
CREATE TRIGGER marketplace_publishers_updated_at
BEFORE UPDATE ON public.marketplace_publishers
FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();

DROP TRIGGER IF EXISTS marketplace_assets_updated_at ON public.marketplace_assets;
CREATE TRIGGER marketplace_assets_updated_at
BEFORE UPDATE ON public.marketplace_assets
FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();

DROP TRIGGER IF EXISTS marketplace_installs_updated_at ON public.marketplace_installs;
CREATE TRIGGER marketplace_installs_updated_at
BEFORE UPDATE ON public.marketplace_installs
FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();

DROP TRIGGER IF EXISTS marketplace_reviews_updated_at ON public.marketplace_reviews;
CREATE TRIGGER marketplace_reviews_updated_at
BEFORE UPDATE ON public.marketplace_reviews
FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();

-- ---------------------------------------------------------------------------
-- MKT-2.3: Row level security
-- ---------------------------------------------------------------------------

ALTER TABLE public.marketplace_publishers ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.marketplace_assets ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.marketplace_asset_versions ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.marketplace_pack_items ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.marketplace_installs ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.marketplace_reviews ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.marketplace_saves ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.marketplace_payouts ENABLE ROW LEVEL SECURITY;

-- Publishers: active publishers readable by any authenticated user.
DROP POLICY IF EXISTS "marketplace_publishers_select_authenticated" ON public.marketplace_publishers;
CREATE POLICY "marketplace_publishers_select_authenticated"
  ON public.marketplace_publishers FOR SELECT
  USING (auth.uid() IS NOT NULL AND status = 'active');

DROP POLICY IF EXISTS "marketplace_publishers_org_admin_write" ON public.marketplace_publishers;
CREATE POLICY "marketplace_publishers_org_admin_write"
  ON public.marketplace_publishers FOR ALL
  USING (
    org_id IS NOT NULL
    AND org_id IN (
      SELECT om.org_id
      FROM public.organization_members om
      WHERE om.user_id = auth.uid() AND om.role = 'admin'
    )
  )
  WITH CHECK (
    org_id IS NOT NULL
    AND org_id IN (
      SELECT om.org_id
      FROM public.organization_members om
      WHERE om.user_id = auth.uid() AND om.role = 'admin'
    )
  );

-- Assets: deliberate cross-tenant browse for published public catalog entries.
DROP POLICY IF EXISTS "marketplace_assets_select_browse" ON public.marketplace_assets;
CREATE POLICY "marketplace_assets_select_browse"
  ON public.marketplace_assets FOR SELECT
  USING (
    auth.uid() IS NOT NULL
    AND (
      (visibility = 'public' AND status = 'published')
      OR (
        visibility = 'internal'
        AND status = 'published'
        AND (
          org_id IN (
            SELECT om.org_id FROM public.organization_members om WHERE om.user_id = auth.uid()
          )
          OR publisher_id IN (
            SELECT mp.id
            FROM public.marketplace_publishers mp
            WHERE mp.org_id IN (
              SELECT om.org_id FROM public.organization_members om WHERE om.user_id = auth.uid()
            )
          )
        )
      )
      OR (
        org_id IN (
          SELECT om.org_id FROM public.organization_members om WHERE om.user_id = auth.uid()
        )
      )
      OR (
        publisher_id IN (
          SELECT mp.id
          FROM public.marketplace_publishers mp
          WHERE mp.org_id IN (
            SELECT om.org_id FROM public.organization_members om WHERE om.user_id = auth.uid()
          )
        )
      )
    )
  );

DROP POLICY IF EXISTS "marketplace_assets_org_admin_write" ON public.marketplace_assets;
CREATE POLICY "marketplace_assets_org_admin_write"
  ON public.marketplace_assets FOR INSERT
  WITH CHECK (
    org_id IS NOT NULL
    AND org_id IN (
      SELECT om.org_id
      FROM public.organization_members om
      WHERE om.user_id = auth.uid() AND om.role = 'admin'
    )
  );

DROP POLICY IF EXISTS "marketplace_assets_org_admin_update" ON public.marketplace_assets;
CREATE POLICY "marketplace_assets_org_admin_update"
  ON public.marketplace_assets FOR UPDATE
  USING (
    org_id IS NOT NULL
    AND org_id IN (
      SELECT om.org_id
      FROM public.organization_members om
      WHERE om.user_id = auth.uid() AND om.role = 'admin'
    )
  )
  WITH CHECK (
    org_id IS NOT NULL
    AND org_id IN (
      SELECT om.org_id
      FROM public.organization_members om
      WHERE om.user_id = auth.uid() AND om.role = 'admin'
    )
  );

DROP POLICY IF EXISTS "marketplace_assets_org_admin_delete" ON public.marketplace_assets;
CREATE POLICY "marketplace_assets_org_admin_delete"
  ON public.marketplace_assets FOR DELETE
  USING (
    org_id IS NOT NULL
    AND org_id IN (
      SELECT om.org_id
      FROM public.organization_members om
      WHERE om.user_id = auth.uid() AND om.role = 'admin'
    )
  );

-- Versions / pack items: readable when parent asset is readable; writes via org admin on parent org.
DROP POLICY IF EXISTS "marketplace_asset_versions_select" ON public.marketplace_asset_versions;
CREATE POLICY "marketplace_asset_versions_select"
  ON public.marketplace_asset_versions FOR SELECT
  USING (
    asset_id IN (
      SELECT ma.id FROM public.marketplace_assets ma
      WHERE auth.uid() IS NOT NULL
    )
  );

DROP POLICY IF EXISTS "marketplace_pack_items_select" ON public.marketplace_pack_items;
CREATE POLICY "marketplace_pack_items_select"
  ON public.marketplace_pack_items FOR SELECT
  USING (
    pack_asset_id IN (
      SELECT ma.id FROM public.marketplace_assets ma
      WHERE auth.uid() IS NOT NULL
    )
  );

-- Installs, reviews, saves: standard org isolation.
DROP POLICY IF EXISTS "marketplace_installs_org_scope" ON public.marketplace_installs;
CREATE POLICY "marketplace_installs_org_scope"
  ON public.marketplace_installs FOR ALL
  USING (
    org_id IN (
      SELECT om.org_id FROM public.organization_members om WHERE om.user_id = auth.uid()
    )
  )
  WITH CHECK (
    org_id IN (
      SELECT om.org_id FROM public.organization_members om WHERE om.user_id = auth.uid()
    )
  );

DROP POLICY IF EXISTS "marketplace_reviews_org_scope" ON public.marketplace_reviews;
CREATE POLICY "marketplace_reviews_org_scope"
  ON public.marketplace_reviews FOR ALL
  USING (
    org_id IN (
      SELECT om.org_id FROM public.organization_members om WHERE om.user_id = auth.uid()
    )
  )
  WITH CHECK (
    org_id IN (
      SELECT om.org_id FROM public.organization_members om WHERE om.user_id = auth.uid()
    )
  );

DROP POLICY IF EXISTS "marketplace_saves_org_scope" ON public.marketplace_saves;
CREATE POLICY "marketplace_saves_org_scope"
  ON public.marketplace_saves FOR ALL
  USING (
    org_id IN (
      SELECT om.org_id FROM public.organization_members om WHERE om.user_id = auth.uid()
    )
  )
  WITH CHECK (
    org_id IN (
      SELECT om.org_id FROM public.organization_members om WHERE om.user_id = auth.uid()
    )
  );

-- Payouts: publisher org admins read-only (writes via service_role in Phase 4).
DROP POLICY IF EXISTS "marketplace_payouts_publisher_admin_select" ON public.marketplace_payouts;
CREATE POLICY "marketplace_payouts_publisher_admin_select"
  ON public.marketplace_payouts FOR SELECT
  USING (
    partner_org_id IN (
      SELECT om.org_id
      FROM public.organization_members om
      WHERE om.user_id = auth.uid() AND om.role = 'admin'
    )
    OR publisher_id IN (
      SELECT mp.id
      FROM public.marketplace_publishers mp
      WHERE mp.org_id IN (
        SELECT om.org_id
        FROM public.organization_members om
        WHERE om.user_id = auth.uid() AND om.role = 'admin'
      )
    )
  );

COMMENT ON TABLE public.marketplace_assets IS
  'Unified marketplace asset registry (MKT-2.2). Gravitre starter library + org-owned templates.';
COMMENT ON TABLE public.marketplace_installs IS
  'Install ledger superseding org_department_pack_installs (backfill in MKT-4.5).';
