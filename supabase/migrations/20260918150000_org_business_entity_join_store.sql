-- 2.0-B: tenant-scoped BusinessEntity join store (confidence + evidence).
-- Alias cache in org_entity_resolution_records remains the lookup projection.
-- Never silent-merge: application refuses below 0.85; this table stores accepted joins only.

CREATE TABLE IF NOT EXISTS public.org_business_entities (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id uuid NOT NULL REFERENCES public.organizations(id) ON DELETE CASCADE,
  canonical_key text NOT NULL,
  display_name text NOT NULL,
  kind text NOT NULL,
  confidence double precision NOT NULL DEFAULT 0.7,
  evidence jsonb NOT NULL DEFAULT '[]'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT org_business_entities_org_key UNIQUE (org_id, canonical_key)
);

CREATE TABLE IF NOT EXISTS public.org_business_entity_bindings (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id uuid NOT NULL REFERENCES public.organizations(id) ON DELETE CASCADE,
  entity_id uuid NOT NULL REFERENCES public.org_business_entities(id) ON DELETE CASCADE,
  system text NOT NULL,
  resource_type text NOT NULL,
  resource_id text NOT NULL,
  confidence double precision NOT NULL DEFAULT 0.7,
  evidence jsonb NOT NULL DEFAULT '[]'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT org_business_entity_bindings_unique UNIQUE (org_id, system, resource_type, resource_id)
);

CREATE INDEX IF NOT EXISTS idx_org_business_entities_org_kind
  ON public.org_business_entities (org_id, kind);

CREATE INDEX IF NOT EXISTS idx_org_business_entity_bindings_org_system
  ON public.org_business_entity_bindings (org_id, system);

ALTER TABLE public.org_business_entities ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.org_business_entity_bindings ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS org_business_entities_org_scope ON public.org_business_entities;
CREATE POLICY org_business_entities_org_scope
  ON public.org_business_entities FOR ALL
  USING (
    org_id IN (SELECT org_id FROM public.organization_members WHERE user_id = auth.uid())
  )
  WITH CHECK (
    org_id IN (SELECT org_id FROM public.organization_members WHERE user_id = auth.uid())
  );

DROP POLICY IF EXISTS org_business_entity_bindings_org_scope ON public.org_business_entity_bindings;
CREATE POLICY org_business_entity_bindings_org_scope
  ON public.org_business_entity_bindings FOR ALL
  USING (
    org_id IN (SELECT org_id FROM public.organization_members WHERE user_id = auth.uid())
  )
  WITH CHECK (
    org_id IN (SELECT org_id FROM public.organization_members WHERE user_id = auth.uid())
  );

COMMENT ON TABLE public.org_business_entities IS
  '2.0-B accepted BusinessEntity joins. Application refuses silent merge below confidence threshold.';
COMMENT ON TABLE public.org_business_entity_bindings IS
  'Provider resource bindings for org_business_entities (HubSpot/QBO/Zendesk/GA4/GSC).';
