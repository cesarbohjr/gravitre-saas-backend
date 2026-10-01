CREATE TABLE IF NOT EXISTS public.capability_package_resources (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  package_id uuid NOT NULL REFERENCES public.capability_packages(id) ON DELETE CASCADE,
  org_id uuid NOT NULL REFERENCES public.organizations(id) ON DELETE CASCADE,
  path text NOT NULL,
  kind text NOT NULL CHECK (kind IN ('reference','script','asset')),
  content text,
  executable boolean NOT NULL DEFAULT false,
  created_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE(package_id, path)
);

CREATE INDEX IF NOT EXISTS capability_package_resources_package_idx
  ON public.capability_package_resources(package_id, kind);

ALTER TABLE public.capability_package_resources ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS capability_package_resources_org_member_read ON public.capability_package_resources;
CREATE POLICY capability_package_resources_org_member_read
  ON public.capability_package_resources FOR SELECT
  USING (
    EXISTS (
      SELECT 1 FROM public.organization_members m
      WHERE m.org_id = capability_package_resources.org_id
        AND m.user_id = auth.uid()
    )
  );

COMMENT ON TABLE public.capability_package_resources IS
  'Textual portable capability resources. Script rows retain path metadata only and are never executed directly.';
