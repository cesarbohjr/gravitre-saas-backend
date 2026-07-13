-- Phase 1.5: shared durable cache + external entities + external signals
-- One pipeline for all gravitree pack sources (FRED / NVD / World Bank / …).

CREATE TABLE IF NOT EXISTS public.knowledge_pack_cache (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  vendor text NOT NULL,
  cache_key text NOT NULL,
  payload jsonb NOT NULL,
  provenance jsonb NOT NULL DEFAULT '{}'::jsonb,
  ttl_seconds integer NOT NULL DEFAULT 3600,
  expires_at timestamptz NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT knowledge_pack_cache_vendor_key UNIQUE (vendor, cache_key)
);

CREATE INDEX IF NOT EXISTS idx_knowledge_pack_cache_expires
  ON public.knowledge_pack_cache (expires_at);

ALTER TABLE public.knowledge_pack_cache ENABLE ROW LEVEL SECURITY;

-- Platform-shared gravitree cache (no tenant secret). Service role writes;
-- authenticated members may read non-expired rows for debugging/smoke.
DROP POLICY IF EXISTS knowledge_pack_cache_read_authenticated ON public.knowledge_pack_cache;
CREATE POLICY knowledge_pack_cache_read_authenticated
  ON public.knowledge_pack_cache FOR SELECT
  USING (auth.role() = 'authenticated' AND expires_at > now());

COMMENT ON TABLE public.knowledge_pack_cache IS
  'Phase 1.5 durable TTL cache for gravitree-managed intelligence sources; shared cache_get/cache_set only.';

CREATE TABLE IF NOT EXISTS public.external_entities (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id uuid NOT NULL REFERENCES public.organizations(id) ON DELETE CASCADE,
  vendor text NOT NULL,
  entity_type text NOT NULL,
  external_id text NOT NULL,
  title text,
  payload jsonb NOT NULL DEFAULT '{}'::jsonb,
  provenance jsonb NOT NULL DEFAULT '{}'::jsonb,
  source_cache_id uuid REFERENCES public.knowledge_pack_cache(id) ON DELETE SET NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT external_entities_org_vendor_ext UNIQUE (org_id, vendor, entity_type, external_id)
);

CREATE INDEX IF NOT EXISTS idx_external_entities_org_vendor
  ON public.external_entities (org_id, vendor);

ALTER TABLE public.external_entities ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS external_entities_org_scope ON public.external_entities;
CREATE POLICY external_entities_org_scope
  ON public.external_entities FOR ALL
  USING (
    org_id IN (
      SELECT organization_members.org_id
      FROM public.organization_members
      WHERE organization_members.user_id = auth.uid()
    )
  )
  WITH CHECK (
    org_id IN (
      SELECT organization_members.org_id
      FROM public.organization_members
      WHERE organization_members.user_id = auth.uid()
    )
  );

COMMENT ON TABLE public.external_entities IS
  'Phase 1.5 normalized external entities written only via write_external_entity_with_provenance.';

CREATE TABLE IF NOT EXISTS public.external_signals (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id uuid NOT NULL REFERENCES public.organizations(id) ON DELETE CASCADE,
  signal_definition_id text NOT NULL,
  vendor text NOT NULL,
  signal_type text NOT NULL,
  title text NOT NULL,
  severity text NOT NULL DEFAULT 'info',
  entity_id uuid REFERENCES public.external_entities(id) ON DELETE SET NULL,
  payload jsonb NOT NULL DEFAULT '{}'::jsonb,
  provenance jsonb NOT NULL DEFAULT '{}'::jsonb,
  detected_at timestamptz NOT NULL DEFAULT now(),
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_external_signals_org_detected
  ON public.external_signals (org_id, detected_at DESC);

CREATE INDEX IF NOT EXISTS idx_external_signals_org_def
  ON public.external_signals (org_id, signal_definition_id);

ALTER TABLE public.external_signals ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS external_signals_org_scope ON public.external_signals;
CREATE POLICY external_signals_org_scope
  ON public.external_signals FOR ALL
  USING (
    org_id IN (
      SELECT organization_members.org_id
      FROM public.organization_members
      WHERE organization_members.user_id = auth.uid()
    )
  )
  WITH CHECK (
    org_id IN (
      SELECT organization_members.org_id
      FROM public.organization_members
      WHERE organization_members.user_id = auth.uid()
    )
  );

COMMENT ON TABLE public.external_signals IS
  'Phase 1.5 signals produced by PackSignalDefinition registrations against the shared path.';
