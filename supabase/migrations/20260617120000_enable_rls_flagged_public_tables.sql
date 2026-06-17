-- Enable RLS on tables flagged by Supabase Security Advisor (RLS Disabled in Public).
-- Backend uses service_role (bypasses RLS); policies protect direct PostgREST/client access.

-- ---------------------------------------------------------------------------
-- Org-scoped tables (org_id column)
-- ---------------------------------------------------------------------------

ALTER TABLE public.subscriptions ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "subscriptions_org_scope" ON public.subscriptions;
CREATE POLICY "subscriptions_org_scope"
  ON public.subscriptions FOR ALL
  USING (
    org_id IN (
      SELECT org_id FROM public.organization_members WHERE user_id = auth.uid()
    )
  )
  WITH CHECK (
    org_id IN (
      SELECT org_id FROM public.organization_members WHERE user_id = auth.uid()
    )
  );

ALTER TABLE public.usage_records ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "usage_records_org_scope" ON public.usage_records;
CREATE POLICY "usage_records_org_scope"
  ON public.usage_records FOR ALL
  USING (
    org_id IN (
      SELECT org_id FROM public.organization_members WHERE user_id = auth.uid()
    )
  )
  WITH CHECK (
    org_id IN (
      SELECT org_id FROM public.organization_members WHERE user_id = auth.uid()
    )
  );

ALTER TABLE public.departments ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "departments_org_scope" ON public.departments;
CREATE POLICY "departments_org_scope"
  ON public.departments FOR ALL
  USING (
    org_id IN (
      SELECT org_id FROM public.organization_members WHERE user_id = auth.uid()
    )
  )
  WITH CHECK (
    org_id IN (
      SELECT org_id FROM public.organization_members WHERE user_id = auth.uid()
    )
  );

ALTER TABLE public.org_billing_overrides ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "org_billing_overrides_org_scope" ON public.org_billing_overrides;
CREATE POLICY "org_billing_overrides_org_scope"
  ON public.org_billing_overrides FOR ALL
  USING (
    org_id IN (
      SELECT org_id FROM public.organization_members WHERE user_id = auth.uid()
    )
  )
  WITH CHECK (
    org_id IN (
      SELECT org_id FROM public.organization_members WHERE user_id = auth.uid()
    )
  );

ALTER TABLE public.training_datasets ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "training_datasets_org_scope" ON public.training_datasets;
CREATE POLICY "training_datasets_org_scope"
  ON public.training_datasets FOR ALL
  USING (
    org_id IN (
      SELECT org_id FROM public.organization_members WHERE user_id = auth.uid()
    )
  )
  WITH CHECK (
    org_id IN (
      SELECT org_id FROM public.organization_members WHERE user_id = auth.uid()
    )
  );

ALTER TABLE public.training_records ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "training_records_org_scope" ON public.training_records;
CREATE POLICY "training_records_org_scope"
  ON public.training_records FOR ALL
  USING (
    org_id IN (
      SELECT org_id FROM public.organization_members WHERE user_id = auth.uid()
    )
  )
  WITH CHECK (
    org_id IN (
      SELECT org_id FROM public.organization_members WHERE user_id = auth.uid()
    )
  );

ALTER TABLE public.training_jobs ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "training_jobs_org_scope" ON public.training_jobs;
CREATE POLICY "training_jobs_org_scope"
  ON public.training_jobs FOR ALL
  USING (
    org_id IN (
      SELECT org_id FROM public.organization_members WHERE user_id = auth.uid()
    )
  )
  WITH CHECK (
    org_id IN (
      SELECT org_id FROM public.organization_members WHERE user_id = auth.uid()
    )
  );

ALTER TABLE public.custom_instructions ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "custom_instructions_org_scope" ON public.custom_instructions;
CREATE POLICY "custom_instructions_org_scope"
  ON public.custom_instructions FOR ALL
  USING (
    org_id IN (
      SELECT org_id FROM public.organization_members WHERE user_id = auth.uid()
    )
  )
  WITH CHECK (
    org_id IN (
      SELECT org_id FROM public.organization_members WHERE user_id = auth.uid()
    )
  );

-- Search history: org member may only read/write their own rows.
ALTER TABLE public.search_history ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "search_history_user_org_scope" ON public.search_history;
CREATE POLICY "search_history_user_org_scope"
  ON public.search_history FOR ALL
  USING (
    user_id = auth.uid()
    AND org_id IN (
      SELECT org_id FROM public.organization_members WHERE user_id = auth.uid()
    )
  )
  WITH CHECK (
    user_id = auth.uid()
    AND org_id IN (
      SELECT org_id FROM public.organization_members WHERE user_id = auth.uid()
    )
  );

-- ---------------------------------------------------------------------------
-- department_members (scoped via parent department org)
-- ---------------------------------------------------------------------------

ALTER TABLE public.department_members ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "department_members_org_scope" ON public.department_members;
CREATE POLICY "department_members_org_scope"
  ON public.department_members FOR ALL
  USING (
    department_id IN (
      SELECT d.id
      FROM public.departments d
      WHERE d.org_id IN (
        SELECT org_id FROM public.organization_members WHERE user_id = auth.uid()
      )
    )
  )
  WITH CHECK (
    department_id IN (
      SELECT d.id
      FROM public.departments d
      WHERE d.org_id IN (
        SELECT org_id FROM public.organization_members WHERE user_id = auth.uid()
      )
    )
  );

-- ---------------------------------------------------------------------------
-- Global catalog (read-only for authenticated clients)
-- ---------------------------------------------------------------------------

ALTER TABLE public.meson_addon_catalog ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "meson_addon_catalog_authenticated_read" ON public.meson_addon_catalog;
CREATE POLICY "meson_addon_catalog_authenticated_read"
  ON public.meson_addon_catalog FOR SELECT
  TO authenticated
  USING (true);
