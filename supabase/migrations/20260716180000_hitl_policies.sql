-- Admin-configurable human-in-the-loop policies.
-- Scope who must seek approval (org / department / user) and which action classes
-- (read / write / delete) require it. Approvers are roles and/or specific users.

CREATE TABLE IF NOT EXISTS public.hitl_policies (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id uuid NOT NULL REFERENCES public.organizations(id) ON DELETE CASCADE,
  name text NOT NULL,
  enabled boolean NOT NULL DEFAULT true,
  scope_type text NOT NULL CHECK (scope_type IN ('org', 'department', 'user')),
  department_id uuid REFERENCES public.departments(id) ON DELETE CASCADE,
  subject_user_id uuid REFERENCES auth.users(id) ON DELETE CASCADE,
  action_kinds text[] NOT NULL DEFAULT '{write,delete}',
  approver_roles text[] NOT NULL DEFAULT '{admin,owner}',
  approver_user_ids uuid[] NOT NULL DEFAULT '{}',
  required_approvals int NOT NULL DEFAULT 1 CHECK (required_approvals >= 1),
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  created_by uuid REFERENCES auth.users(id) ON DELETE SET NULL,
  CONSTRAINT hitl_policies_scope_department_ck CHECK (
    (scope_type <> 'department') OR (department_id IS NOT NULL)
  ),
  CONSTRAINT hitl_policies_scope_user_ck CHECK (
    (scope_type <> 'user') OR (subject_user_id IS NOT NULL)
  ),
  CONSTRAINT hitl_policies_scope_org_ck CHECK (
    (scope_type <> 'org') OR (department_id IS NULL AND subject_user_id IS NULL)
  )
);

CREATE INDEX IF NOT EXISTS idx_hitl_policies_org_id ON public.hitl_policies(org_id);
CREATE INDEX IF NOT EXISTS idx_hitl_policies_org_enabled ON public.hitl_policies(org_id, enabled);
CREATE INDEX IF NOT EXISTS idx_hitl_policies_department ON public.hitl_policies(department_id)
  WHERE department_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_hitl_policies_subject_user ON public.hitl_policies(subject_user_id)
  WHERE subject_user_id IS NOT NULL;

ALTER TABLE public.hitl_policies ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "hitl_policies_org_select" ON public.hitl_policies;
CREATE POLICY "hitl_policies_org_select"
  ON public.hitl_policies FOR SELECT
  USING (
    org_id IN (
      SELECT om.org_id FROM public.organization_members om WHERE om.user_id = auth.uid()
    )
  );

DROP POLICY IF EXISTS "hitl_policies_org_write" ON public.hitl_policies;
CREATE POLICY "hitl_policies_org_write"
  ON public.hitl_policies FOR ALL
  USING (
    org_id IN (
      SELECT om.org_id
      FROM public.organization_members om
      WHERE om.user_id = auth.uid()
        AND lower(om.role) IN ('admin', 'owner')
    )
  )
  WITH CHECK (
    org_id IN (
      SELECT om.org_id
      FROM public.organization_members om
      WHERE om.user_id = auth.uid()
        AND lower(om.role) IN ('admin', 'owner')
    )
  );

COMMENT ON TABLE public.hitl_policies IS
  'Org HITL rules: require approval for read/write/delete by org, department, or user.';
