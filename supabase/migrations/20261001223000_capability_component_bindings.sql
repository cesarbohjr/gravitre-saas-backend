CREATE TABLE IF NOT EXISTS public.capability_component_bindings (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id uuid NOT NULL REFERENCES public.organizations(id) ON DELETE CASCADE,
  package_id uuid NOT NULL REFERENCES public.capability_packages(id) ON DELETE CASCADE,
  component_kind text NOT NULL CHECK (component_kind IN ('agent','play','template','trigger')),
  component_name text NOT NULL,
  target_type text NOT NULL CHECK (target_type IN ('agent','play','workflow','workflow_schedule','marketplace_asset')),
  target_id text NOT NULL,
  enabled boolean NOT NULL DEFAULT true,
  created_by uuid,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE(package_id, component_kind, component_name, target_type, target_id)
);

CREATE INDEX IF NOT EXISTS capability_component_bindings_package_idx
  ON public.capability_component_bindings(package_id, enabled, component_kind);

ALTER TABLE public.capability_component_bindings ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS capability_component_bindings_org_member_read
  ON public.capability_component_bindings;
CREATE POLICY capability_component_bindings_org_member_read
  ON public.capability_component_bindings FOR SELECT
  USING (
    EXISTS (
      SELECT 1 FROM public.organization_members m
      WHERE m.org_id = capability_component_bindings.org_id
        AND m.user_id = auth.uid()
    )
  );

COMMENT ON TABLE public.capability_component_bindings IS
  'Admin-reviewed bindings from portable package declarations to existing native Gravitre entities. Bindings never create or execute target entities.';
