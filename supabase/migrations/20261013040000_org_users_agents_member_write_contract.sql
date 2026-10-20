-- Field-level write contract for organizations, users and agents through PostgREST.
--
-- These three tables keep member-scoped FOR ALL policies because the web app's
-- settings and agent pages write them with the caller's token. Row scope alone let
-- any member, for their own org:
--   organizations  rename it, change status / data_region, delete it, and rewrite
--                  settings wholesale: billing, enterprise (HIPAA etc.),
--                  isolated_conversation_test_org, memoryEntityEmbeddings consent,
--                  approvalRules, onboarding ...
--   users          change anyone's role or status, delete teammates, insert rows
--   agents         re-home an agent to another org id or rewrite created_by; viewers
--                  could edit agents although the role matrix says they cannot
--
-- Contract (org_role_permissions.py: org settings & billing and team roles are
-- admin-only; members create agents and workflows; viewers do not):
--   organizations  authenticated UPDATE only by an owner/admin of that org, only
--                  name, slug, logo_url and settings; inside settings only
--                  notificationPreferences and approvalRules. INSERT and DELETE are
--                  backend-only (create/delete org go through FastAPI).
--   users          a member may edit their own full_name, avatar_url, job_title,
--                  department; an owner/admin may also edit those for others in the
--                  org plus role (the display copy synced after the backend changes
--                  the membership) and status/is_active. Nobody changes org_id,
--                  auth_user_id, email, external_id or provisioned_via through
--                  PostgREST. INSERT is backend-only; DELETE needs an owner/admin.
--   agents         members and admins create and edit agents in their org; viewers
--                  cannot; org_id and created_by never change after insert.
-- The backend (service role) is unaffected. anon loses write grants (RLS already gave
-- it no rows; its SELECT grant is left so anonymous reads still return empty, not errors).
--
-- Not decided here (product owner): whether members, not only admins, may change
-- an agent's tool authority (systems, guardrails, config.guardrail_limits). Today's
-- role matrix lets members create agents, so this migration keeps that.
--
-- Production preflight (read-only):
--   select tablename, policyname, cmd from pg_policies
--    where schemaname = 'public' and tablename in ('organizations','users','agents');
--   select table_name, grantee, string_agg(privilege_type, ',') from information_schema.role_table_grants
--    where table_schema = 'public' and table_name in ('organizations','users','agents')
--      and grantee in ('anon','authenticated') group by 1, 2;
--
-- Rollback: DROP TRIGGER organizations_member_write_contract ON public.organizations;
-- DROP TRIGGER users_member_write_contract ON public.users; DROP TRIGGER
-- agents_member_write_contract ON public.agents; GRANT INSERT, DELETE ON
-- public.organizations, public.users TO authenticated. Do not roll back to restore
-- a demo; seed demo data with the service role instead.

-- Caller's role in an org ('' when not a member). Reads the caller's own
-- membership row, which RLS already lets them see.
CREATE OR REPLACE FUNCTION public.caller_org_role(p_org_id uuid)
RETURNS text
LANGUAGE sql
STABLE
SET search_path = public, pg_temp
AS $$
  SELECT coalesce((
    SELECT lower(om.role) FROM public.organization_members om
     WHERE om.org_id = p_org_id AND om.user_id = auth.uid()
     LIMIT 1
  ), '');
$$;

REVOKE ALL ON FUNCTION public.caller_org_role(uuid) FROM PUBLIC, anon;
GRANT EXECUTE ON FUNCTION public.caller_org_role(uuid) TO authenticated, service_role;

-- Column names whose values differ between two rows of the same table.
CREATE OR REPLACE FUNCTION public.changed_columns(p_old jsonb, p_new jsonb)
RETURNS text[]
LANGUAGE sql
IMMUTABLE
AS $$
  SELECT coalesce(array_agg(n.key ORDER BY n.key), '{}')
    FROM jsonb_each(p_new) n
   WHERE n.value IS DISTINCT FROM (p_old -> n.key);
$$;

-- -----------------------------------------------------------------------------
-- organizations
-- -----------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION public.organizations_member_write_contract()
RETURNS trigger
LANGUAGE plpgsql
SET search_path = public, pg_temp
AS $$
DECLARE
  cols text[];
  bad text[];
  settings_keys text[];
BEGIN
  IF current_user NOT IN ('anon', 'authenticated') THEN
    RETURN NEW;
  END IF;
  cols := array_remove(public.changed_columns(to_jsonb(OLD), to_jsonb(NEW)), 'updated_at');
  IF cardinality(cols) = 0 THEN
    RETURN NEW;
  END IF;
  IF public.caller_org_role(NEW.id) NOT IN ('owner', 'admin') THEN
    RAISE EXCEPTION 'Only an org owner or admin can change organization settings' USING ERRCODE = '42501';
  END IF;
  bad := ARRAY(SELECT c FROM unnest(cols) c WHERE c NOT IN ('name', 'slug', 'logo_url', 'settings'));
  IF cardinality(bad) > 0 THEN
    RAISE EXCEPTION 'These organization fields are managed by Gravitre: %', array_to_string(bad, ', ')
      USING ERRCODE = '42501';
  END IF;
  IF 'settings' = ANY (cols) THEN
    settings_keys := ARRAY(
      SELECT k FROM (
        SELECT jsonb_object_keys(coalesce(OLD.settings, '{}'::jsonb)) AS k
        UNION
        SELECT jsonb_object_keys(coalesce(NEW.settings, '{}'::jsonb))
      ) keys
      WHERE (coalesce(OLD.settings, '{}'::jsonb) -> k) IS DISTINCT FROM (coalesce(NEW.settings, '{}'::jsonb) -> k)
        AND k NOT IN ('notificationPreferences', 'approvalRules')
    );
    IF cardinality(settings_keys) > 0 THEN
      RAISE EXCEPTION 'These organization settings are managed by Gravitre: %', array_to_string(settings_keys, ', ')
        USING ERRCODE = '42501';
    END IF;
  END IF;
  RETURN NEW;
END;
$$;

-- -----------------------------------------------------------------------------
-- users
-- -----------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION public.users_member_write_contract()
RETURNS trigger
LANGUAGE plpgsql
SET search_path = public, pg_temp
AS $$
DECLARE
  cols text[];
  bad text[];
  is_admin boolean;
  is_self boolean;
BEGIN
  IF current_user NOT IN ('anon', 'authenticated') THEN
    RETURN COALESCE(NEW, OLD);
  END IF;
  IF TG_OP = 'DELETE' THEN
    IF public.caller_org_role(OLD.org_id) NOT IN ('owner', 'admin') THEN
      RAISE EXCEPTION 'Only an org owner or admin can remove team members' USING ERRCODE = '42501';
    END IF;
    RETURN OLD;
  END IF;
  cols := array_remove(public.changed_columns(to_jsonb(OLD), to_jsonb(NEW)), 'updated_at');
  IF cardinality(cols) = 0 THEN
    RETURN NEW;
  END IF;
  bad := ARRAY(
    SELECT c FROM unnest(cols) c
     WHERE c IN ('id', 'org_id', 'auth_user_id', 'email', 'external_id', 'provisioned_via', 'created_at')
  );
  IF cardinality(bad) > 0 THEN
    RAISE EXCEPTION 'These user fields are managed by Gravitre: %', array_to_string(bad, ', ') USING ERRCODE = '42501';
  END IF;
  is_admin := public.caller_org_role(NEW.org_id) IN ('owner', 'admin');
  is_self := OLD.auth_user_id IS NOT NULL AND OLD.auth_user_id = auth.uid();
  IF is_admin THEN
    RETURN NEW;
  END IF;
  IF NOT is_self THEN
    RAISE EXCEPTION 'Only an org owner or admin can edit another team member' USING ERRCODE = '42501';
  END IF;
  bad := ARRAY(
    SELECT c FROM unnest(cols) c WHERE c NOT IN ('full_name', 'avatar_url', 'job_title', 'department')
  );
  IF cardinality(bad) > 0 THEN
    RAISE EXCEPTION 'Only an org owner or admin can change: %', array_to_string(bad, ', ') USING ERRCODE = '42501';
  END IF;
  RETURN NEW;
END;
$$;

-- -----------------------------------------------------------------------------
-- agents
-- -----------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION public.agents_member_write_contract()
RETURNS trigger
LANGUAGE plpgsql
SET search_path = public, pg_temp
AS $$
DECLARE
  role_now text;
BEGIN
  IF current_user NOT IN ('anon', 'authenticated') THEN
    RETURN COALESCE(NEW, OLD);
  END IF;
  role_now := public.caller_org_role(COALESCE(NEW.org_id, OLD.org_id));
  IF role_now NOT IN ('owner', 'admin', 'member') THEN
    RAISE EXCEPTION 'Viewers cannot create, edit or delete agents' USING ERRCODE = '42501';
  END IF;
  IF TG_OP = 'UPDATE' THEN
    IF NEW.org_id IS DISTINCT FROM OLD.org_id OR NEW.created_by IS DISTINCT FROM OLD.created_by THEN
      RAISE EXCEPTION 'An agent''s organization and creator cannot change' USING ERRCODE = '42501';
    END IF;
  END IF;
  RETURN COALESCE(NEW, OLD);
END;
$$;

REVOKE ALL ON FUNCTION public.organizations_member_write_contract() FROM PUBLIC, anon, authenticated;
REVOKE ALL ON FUNCTION public.users_member_write_contract() FROM PUBLIC, anon, authenticated;
REVOKE ALL ON FUNCTION public.agents_member_write_contract() FROM PUBLIC, anon, authenticated;
REVOKE ALL ON FUNCTION public.changed_columns(jsonb, jsonb) FROM PUBLIC, anon;
-- Pure helper the invoker-rights triggers call as the signed-in user.
GRANT EXECUTE ON FUNCTION public.changed_columns(jsonb, jsonb) TO authenticated, service_role;

DO $$
BEGIN
  IF to_regclass('public.organizations') IS NOT NULL THEN
    DROP TRIGGER IF EXISTS organizations_member_write_contract ON public.organizations;
    CREATE TRIGGER organizations_member_write_contract
      BEFORE UPDATE ON public.organizations
      FOR EACH ROW EXECUTE FUNCTION public.organizations_member_write_contract();
    REVOKE INSERT, DELETE, TRUNCATE ON public.organizations FROM anon, authenticated;
    REVOKE UPDATE ON public.organizations FROM anon;
  END IF;

  IF to_regclass('public.users') IS NOT NULL THEN
    DROP TRIGGER IF EXISTS users_member_write_contract ON public.users;
    CREATE TRIGGER users_member_write_contract
      BEFORE UPDATE OR DELETE ON public.users
      FOR EACH ROW EXECUTE FUNCTION public.users_member_write_contract();
    REVOKE INSERT, TRUNCATE ON public.users FROM anon, authenticated;
    REVOKE UPDATE, DELETE ON public.users FROM anon;
  END IF;

  IF to_regclass('public.agents') IS NOT NULL THEN
    DROP TRIGGER IF EXISTS agents_member_write_contract ON public.agents;
    CREATE TRIGGER agents_member_write_contract
      BEFORE INSERT OR UPDATE OR DELETE ON public.agents
      FOR EACH ROW EXECUTE FUNCTION public.agents_member_write_contract();
    REVOKE TRUNCATE ON public.agents FROM anon, authenticated;
    REVOKE INSERT, UPDATE, DELETE ON public.agents FROM anon;
  END IF;
END;
$$;
