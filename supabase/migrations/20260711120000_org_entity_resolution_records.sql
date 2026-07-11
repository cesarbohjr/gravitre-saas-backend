-- Wave 5: Durable entity-resolution aliases (session → org-level)

CREATE TABLE IF NOT EXISTS public.org_entity_resolution_records (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id uuid NOT NULL REFERENCES public.organizations(id) ON DELETE CASCADE,
  alias_normalized text NOT NULL,
  entity_type text NOT NULL,
  entity_id text NOT NULL,
  integration text NOT NULL DEFAULT '',
  source text NOT NULL DEFAULT 'tool_output',
  confidence double precision NOT NULL DEFAULT 0.7,
  evidence_count integer NOT NULL DEFAULT 1,
  last_observed_at timestamptz NOT NULL DEFAULT now(),
  created_by_conversation_id uuid NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_org_entity_resolution_unique
  ON public.org_entity_resolution_records (
    org_id,
    integration,
    alias_normalized,
    entity_type
  );

CREATE INDEX IF NOT EXISTS idx_org_entity_resolution_lookup
  ON public.org_entity_resolution_records (org_id, alias_normalized);

CREATE INDEX IF NOT EXISTS idx_org_entity_resolution_integration
  ON public.org_entity_resolution_records (org_id, integration, entity_type);

ALTER TABLE public.org_entity_resolution_records ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS org_entity_resolution_isolation ON public.org_entity_resolution_records;
CREATE POLICY org_entity_resolution_isolation
  ON public.org_entity_resolution_records FOR ALL
  USING (
    org_id IN (SELECT org_id FROM public.organization_members WHERE user_id = auth.uid())
  );

COMMENT ON TABLE public.org_entity_resolution_records IS
  'Wave 5 durable alias → entity_id resolutions promoted from connector session state.';
