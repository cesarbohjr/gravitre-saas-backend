-- Role contract for org settings and shared workspace tables written by the web app.
--
-- These tables keep member-scoped FOR ALL policies because Settings and builder
-- pages write them with the caller's token. Row scope alone let any member,
-- viewers included, change org-level settings and shared work. The contract
-- follows backend/app/auth/org_role_permissions.py:
--   org settings (admin only)        webhooks, model_settings, api_keys
--   manage connectors (not viewers)  connected_systems
--   create agents & workflows        workflows
--   approve writes (not viewers)     council_sessions (resolve / override)
-- org_id never changes after insert. The backend (service role) is unaffected;
-- anon loses its write grants (RLS already gave it no rows).
--
-- Production preflight (read-only):
--   select tablename, policyname, cmd from pg_policies where schemaname = 'public'
--    and tablename in ('webhooks','model_settings','api_keys','connected_systems','workflows','council_sessions');
--   select tgname, tgrelid::regclass from pg_trigger where tgname like '%role_contract%';
--
-- Rollback: DROP TRIGGER <table>_role_contract ON public.<table> for each table.
-- Do not roll back to restore a demo.

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

-- TG_ARGV: the roles allowed to write, e.g. 'owner,admin'.
CREATE OR REPLACE FUNCTION public.enforce_org_role_write_contract()
RETURNS trigger
LANGUAGE plpgsql
SET search_path = public, pg_temp
AS $$
DECLARE
  allowed text[] := string_to_array(TG_ARGV[0], ',');
  target_org uuid;
BEGIN
  IF current_user NOT IN ('anon', 'authenticated') THEN
    RETURN COALESCE(NEW, OLD);
  END IF;
  target_org := CASE WHEN TG_OP = 'DELETE' THEN OLD.org_id ELSE NEW.org_id END;
  IF NOT (public.caller_org_role(target_org) = ANY (allowed)) THEN
    RAISE EXCEPTION 'Your role cannot change % in this organization', TG_TABLE_NAME
      USING ERRCODE = '42501';
  END IF;
  IF TG_OP = 'UPDATE' AND NEW.org_id IS DISTINCT FROM OLD.org_id THEN
    RAISE EXCEPTION 'A row''s organization cannot change' USING ERRCODE = '42501';
  END IF;
  RETURN COALESCE(NEW, OLD);
END;
$$;

REVOKE ALL ON FUNCTION public.enforce_org_role_write_contract() FROM PUBLIC, anon, authenticated;

DO $$
DECLARE
  spec record;
BEGIN
  FOR spec IN
    SELECT * FROM (VALUES
      ('webhooks', 'owner,admin'),
      ('model_settings', 'owner,admin'),
      ('api_keys', 'owner,admin'),
      ('connected_systems', 'owner,admin,member'),
      ('workflows', 'owner,admin,member'),
      ('council_sessions', 'owner,admin,member')
    ) AS t(tbl, roles)
  LOOP
    IF to_regclass(format('public.%I', spec.tbl)) IS NULL THEN
      CONTINUE;
    END IF;
    EXECUTE format('DROP TRIGGER IF EXISTS %I ON public.%I', spec.tbl || '_role_contract', spec.tbl);
    EXECUTE format(
      'CREATE TRIGGER %I BEFORE INSERT OR UPDATE OR DELETE ON public.%I '
      'FOR EACH ROW EXECUTE FUNCTION public.enforce_org_role_write_contract(%L)',
      spec.tbl || '_role_contract', spec.tbl, spec.roles
    );
    EXECUTE format('REVOKE INSERT, UPDATE, DELETE, TRUNCATE ON public.%I FROM anon', spec.tbl);
    EXECUTE format('REVOKE TRUNCATE ON public.%I FROM authenticated', spec.tbl);
  END LOOP;
END;
$$;
