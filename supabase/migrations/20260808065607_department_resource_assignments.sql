-- Department-scoped assignment of workflows, agents, and councils.
-- Composes with Lite seats (department_members) without replacing plan/Meson entitlements.

CREATE TABLE IF NOT EXISTS public.department_resource_assignments (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id uuid NOT NULL REFERENCES public.organizations(id) ON DELETE CASCADE,
  department_id uuid NOT NULL REFERENCES public.departments(id) ON DELETE CASCADE,
  resource_type text NOT NULL CHECK (resource_type IN ('workflow', 'agent', 'council')),
  resource_id text NOT NULL,
  assigned_by uuid,
  created_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (department_id, resource_type, resource_id)
);

CREATE INDEX IF NOT EXISTS idx_dept_resource_assign_org
  ON public.department_resource_assignments (org_id);

CREATE INDEX IF NOT EXISTS idx_dept_resource_assign_dept
  ON public.department_resource_assignments (department_id);

CREATE INDEX IF NOT EXISTS idx_dept_resource_assign_resource
  ON public.department_resource_assignments (org_id, resource_type, resource_id);

ALTER TABLE public.department_resource_assignments ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS department_resource_assignments_org_isolation ON public.department_resource_assignments;
CREATE POLICY department_resource_assignments_org_isolation
  ON public.department_resource_assignments
  FOR ALL
  USING (
    org_id::text = COALESCE(
      auth.jwt() ->> 'org_id',
      auth.jwt() -> 'app_metadata' ->> 'org_id',
      ''
    )
  )
  WITH CHECK (
    org_id::text = COALESCE(
      auth.jwt() ->> 'org_id',
      auth.jwt() -> 'app_metadata' ->> 'org_id',
      ''
    )
  );
