-- STA-80 v2: RLS helpers keyed on organizations.data_region + deployment region setting.
-- Set per regional deployment (Supabase SQL editor or pooler init):
--   ALTER DATABASE postgres SET app.deployment_data_region = 'us';  -- or 'eu'

CREATE OR REPLACE FUNCTION public.deployment_data_region()
RETURNS text
LANGUAGE sql
STABLE
AS $$
  SELECT COALESCE(NULLIF(current_setting('app.deployment_data_region', true), ''), 'us');
$$;

CREATE OR REPLACE FUNCTION public.auth_org_accessible(target_org_id uuid)
RETURNS boolean
LANGUAGE sql
STABLE
SECURITY DEFINER
SET search_path = public
AS $$
  SELECT EXISTS (
    SELECT 1
    FROM public.organization_members om
    INNER JOIN public.organizations o ON o.id = om.org_id
    WHERE om.user_id = auth.uid()
      AND om.org_id = target_org_id
      AND o.data_region = public.deployment_data_region()
  );
$$;

COMMENT ON FUNCTION public.auth_org_accessible(uuid) IS
  'True when auth.uid() is a member of target_org_id and org data_region matches deployment region.';

-- Organizations: members see org only when region matches deployment
DROP POLICY IF EXISTS "organizations_org_scope" ON public.organizations;
CREATE POLICY "organizations_org_scope"
  ON public.organizations FOR ALL
  USING (public.auth_org_accessible(id))
  WITH CHECK (public.auth_org_accessible(id));

-- Connectors + secrets
DROP POLICY IF EXISTS "connectors_org" ON public.connectors;
CREATE POLICY "connectors_org"
  ON public.connectors FOR ALL
  USING (public.auth_org_accessible(org_id))
  WITH CHECK (public.auth_org_accessible(org_id));

DROP POLICY IF EXISTS "connector_secrets_org" ON public.connector_secrets;
CREATE POLICY "connector_secrets_org"
  ON public.connector_secrets FOR ALL
  USING (public.auth_org_accessible(org_id))
  WITH CHECK (public.auth_org_accessible(org_id));

-- Audit surfaces
DROP POLICY IF EXISTS "audit_logs_org_scope" ON public.audit_logs;
CREATE POLICY "audit_logs_org_scope"
  ON public.audit_logs FOR ALL
  USING (public.auth_org_accessible(org_id))
  WITH CHECK (public.auth_org_accessible(org_id));

DO $$
BEGIN
  IF to_regclass('public.audit_events') IS NOT NULL THEN
    EXECUTE 'ALTER TABLE public.audit_events ENABLE ROW LEVEL SECURITY';
    EXECUTE 'DROP POLICY IF EXISTS "audit_events_org_residency" ON public.audit_events';
    EXECUTE $policy$
      CREATE POLICY "audit_events_org_residency"
        ON public.audit_events FOR ALL
        USING (public.auth_org_accessible(org_id))
        WITH CHECK (public.auth_org_accessible(org_id))
    $policy$;
  END IF;
END $$;

-- Agent jobs
DROP POLICY IF EXISTS "agent_jobs_tenant_isolation" ON public.agent_jobs;
CREATE POLICY "agent_jobs_tenant_isolation"
  ON public.agent_jobs FOR ALL
  USING (public.auth_org_accessible(org_id))
  WITH CHECK (public.auth_org_accessible(org_id));

-- Workflow runs (BE-20 table name)
DO $$
BEGIN
  IF to_regclass('public.workflow_runs') IS NOT NULL THEN
    EXECUTE 'ALTER TABLE public.workflow_runs ENABLE ROW LEVEL SECURITY';
    EXECUTE 'DROP POLICY IF EXISTS "workflow_runs_org_residency" ON public.workflow_runs';
    EXECUTE $policy$
      CREATE POLICY "workflow_runs_org_residency"
        ON public.workflow_runs FOR ALL
        USING (public.auth_org_accessible(org_id))
        WITH CHECK (public.auth_org_accessible(org_id))
    $policy$;
  END IF;
END $$;

-- Usage / billing events
DO $$
BEGIN
  IF to_regclass('public.usage_events') IS NOT NULL THEN
    EXECUTE 'ALTER TABLE public.usage_events ENABLE ROW LEVEL SECURITY';
    EXECUTE 'DROP POLICY IF EXISTS "usage_events_org_residency" ON public.usage_events';
    EXECUTE $policy$
      CREATE POLICY "usage_events_org_residency"
        ON public.usage_events FOR ALL
        USING (public.auth_org_accessible(org_id))
        WITH CHECK (public.auth_org_accessible(org_id))
    $policy$;
  END IF;
END $$;
