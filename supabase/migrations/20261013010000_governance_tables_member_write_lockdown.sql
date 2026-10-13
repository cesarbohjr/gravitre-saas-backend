-- Governance tables: org members read through PostgREST, only the backend writes.
--
-- Why. Several tables that decide who may act, and what was approved, had a
-- FOR ALL policy for any org member, and Supabase grants INSERT/UPDATE/DELETE on
-- public tables to `authenticated` by default. Any member, holding the public
-- anon key and their own session token, could write them directly:
--
--   organization_members   self_insert: add yourself to ANY org (no org check);
--                          self_update: change your own role to owner
--   approvals              set status = 'approved' on your own queued write
--   run_approvals          same, for workflow runs
--   workflow_runs          rewrite run status / approval state
--   agent_identity_records set trust_level = 'autonomous' plus an auto_run
--   agent_delegation_grants override, which skips write approval
--   mcp_servers, mcp_tools register servers (including stdio) and flip tool tiers
--   mcp_tool_executions    rewrite the MCP execution trail
--   connectors             repoint or re-enable connectors
--   connector_secrets      read or replace encrypted credentials
--
-- The web app never writes these tables (checked: apps/web, apps/desktop,
-- apps/extension); the FastAPI backend writes them with the service role, which
-- bypasses RLS and is unaffected. Members keep read access exactly as before:
-- each dropped policy's USING expression is reused for a SELECT-only policy.
-- connector_secrets gets no member access at all.
--
-- organizations stays member-writable (the settings pages update it), but the
-- approvalRules block inside organizations.settings, which can hold customer
-- email for a person even under auto-run, now changes only for an owner/admin
-- or the backend.
--
-- Production preflight (read-only):
--   select tablename, policyname, cmd, qual, with_check from pg_policies
--   where schemaname = 'public' and tablename in (
--     'organization_members','approvals','run_approvals','workflow_runs',
--     'agent_identity_records','agent_delegation_grants','mcp_servers','mcp_tools',
--     'mcp_tool_executions','connectors','connector_secrets') order by 1, 2;
--   select table_name, grantee, privilege_type from information_schema.role_table_grants
--   where table_schema = 'public' and grantee in ('anon','authenticated')
--     and table_name in (... same list ...) order by 1, 2, 3;
--
-- Rollback (restores member writes; only if a client turns out to depend on them):
--   re-run the original CREATE POLICY statements from
--   20260424_gravitre_frontend_contract_schema.sql, 20250204000006, 20250204100001,
--   20260427000200, 20260607100000, 20260710120000 and 20260903140000, then
--   GRANT INSERT, UPDATE, DELETE ON <table> TO authenticated;
--   DROP TRIGGER IF EXISTS organizations_guard_approval_rules ON public.organizations;

DO $$
DECLARE
  read_only_tables text[] := ARRAY[
    'organization_members',
    'approvals',
    'run_approvals',
    'workflow_runs',
    'agent_identity_records',
    'agent_delegation_grants',
    'mcp_servers',
    'mcp_tools',
    'mcp_tool_executions',
    'connectors'
  ];
  t text;
  p record;
  select_name text;
BEGIN
  FOREACH t IN ARRAY read_only_tables LOOP
    IF to_regclass(format('public.%I', t)) IS NULL THEN
      CONTINUE;
    END IF;
    EXECUTE format('ALTER TABLE public.%I ENABLE ROW LEVEL SECURITY', t);

    FOR p IN
      SELECT policyname, cmd, qual
      FROM pg_policies
      WHERE schemaname = 'public' AND tablename = t AND cmd <> 'SELECT'
    LOOP
      EXECUTE format('DROP POLICY %I ON public.%I', p.policyname, t);
      -- A FOR ALL policy also granted reads; keep exactly that read scope.
      IF p.cmd = 'ALL' AND p.qual IS NOT NULL THEN
        select_name := left(p.policyname, 50) || '_read';
        IF NOT EXISTS (
          SELECT 1 FROM pg_policies
          WHERE schemaname = 'public' AND tablename = t AND policyname = select_name
        ) THEN
          EXECUTE format(
            'CREATE POLICY %I ON public.%I FOR SELECT USING (%s)',
            select_name, t, p.qual
          );
        END IF;
      END IF;
    END LOOP;

    EXECUTE format('REVOKE INSERT, UPDATE, DELETE, TRUNCATE ON public.%I FROM anon, authenticated', t);
    EXECUTE format('GRANT SELECT ON public.%I TO authenticated', t);
    EXECUTE format('REVOKE ALL ON public.%I FROM anon', t);
  END LOOP;

  -- Credentials: backend only. No member policy, no grant.
  IF to_regclass('public.connector_secrets') IS NOT NULL THEN
    ALTER TABLE public.connector_secrets ENABLE ROW LEVEL SECURITY;
    FOR p IN
      SELECT policyname FROM pg_policies
      WHERE schemaname = 'public' AND tablename = 'connector_secrets'
    LOOP
      EXECUTE format('DROP POLICY %I ON public.connector_secrets', p.policyname);
    END LOOP;
    REVOKE ALL ON public.connector_secrets FROM anon, authenticated;
  END IF;
END;
$$;

-- organizations.settings.approvalRules: owner/admin or backend only.
CREATE OR REPLACE FUNCTION public.guard_org_approval_rules()
RETURNS trigger
LANGUAGE plpgsql
SET search_path = public, pg_temp
AS $$
BEGIN
  IF current_user NOT IN ('anon', 'authenticated') THEN
    RETURN NEW;  -- service role, postgres, migrations
  END IF;
  IF (NEW.settings -> 'approvalRules') IS NOT DISTINCT FROM (OLD.settings -> 'approvalRules') THEN
    RETURN NEW;
  END IF;
  IF EXISTS (
    SELECT 1 FROM public.organization_members om
    WHERE om.org_id = NEW.id
      AND om.user_id = auth.uid()
      AND lower(om.role) IN ('owner', 'admin')
  ) THEN
    RETURN NEW;
  END IF;
  RAISE EXCEPTION 'Only an org owner or admin can change approval rules'
    USING ERRCODE = '42501';
END;
$$;

REVOKE ALL ON FUNCTION public.guard_org_approval_rules() FROM PUBLIC, anon, authenticated;

DO $$
BEGIN
  IF to_regclass('public.organizations') IS NOT NULL AND EXISTS (
    SELECT 1 FROM information_schema.columns
     WHERE table_schema = 'public' AND table_name = 'organizations' AND column_name = 'settings'
  ) THEN
    DROP TRIGGER IF EXISTS organizations_guard_approval_rules ON public.organizations;
    CREATE TRIGGER organizations_guard_approval_rules
      BEFORE UPDATE OF settings ON public.organizations
      FOR EACH ROW EXECUTE FUNCTION public.guard_org_approval_rules();
  END IF;
END;
$$;
