-- Privilege hygiene: TRUNCATE and security-definer EXECUTE for client roles.
--
-- 1) TRUNCATE ignores row level security. anon and authenticated held it on public
--    tables (Supabase default grants). PostgREST never issues TRUNCATE, so this was
--    not reachable through the API, but nothing a client does needs it.
-- 2) Seven SECURITY DEFINER functions were executable by anon and authenticated
--    (Supabase security advisor, confirmed 2026-10-13):
--      increment_marketplace_asset_counter(uuid,text)  writes counters; anyone could
--                                                     inflate install/clone counts
--      is_restricted_test_credential_actor(uuid)       reads auth.users email
--      is_isolated_test_org(uuid)                       reads org settings
--      deployment_data_region()                         configuration
--      handle_new_user(), enforce_test_credential_isolated_org(),
--      mirror_workflow_run_status_to_contract()         trigger functions
--    The backend calls the counter with the service role; triggers run as the
--    table owner whatever the caller's EXECUTE grant. auth_org_accessible(uuid) is
--    left as is: 10 RLS policies call it, so revoking it from anon would turn an
--    anonymous read's empty result into a permission error (it returns false for
--    anon, since auth.uid() is null).
--
-- Preflight (read-only):
--   select p.oid::regprocedure, has_function_privilege('anon', p.oid, 'EXECUTE'),
--          has_function_privilege('authenticated', p.oid, 'EXECUTE')
--     from pg_proc p join pg_namespace n on n.oid = p.pronamespace
--    where n.nspname = 'public' and p.prosecdef;
--
-- Rollback: GRANT EXECUTE ON FUNCTION <fn> TO anon, authenticated for a function a
-- client turns out to need (review why first).

REVOKE TRUNCATE ON ALL TABLES IN SCHEMA public FROM anon, authenticated;

DO $$
BEGIN
  -- Future tables too, where the migration role may change default privileges.
  BEGIN
    ALTER DEFAULT PRIVILEGES IN SCHEMA public REVOKE TRUNCATE ON TABLES FROM anon, authenticated;
  EXCEPTION WHEN insufficient_privilege THEN
    RAISE NOTICE 'default privileges unchanged (insufficient privilege)';
  END;
END;
$$;

DO $$
DECLARE
  fn text;
BEGIN
  FOREACH fn IN ARRAY ARRAY[
    'public.increment_marketplace_asset_counter(uuid,text)',
    'public.is_restricted_test_credential_actor(uuid)',
    'public.is_isolated_test_org(uuid)',
    'public.deployment_data_region()',
    'public.handle_new_user()',
    'public.enforce_test_credential_isolated_org()',
    'public.mirror_workflow_run_status_to_contract()'
  ] LOOP
    IF to_regprocedure(fn) IS NOT NULL THEN
      EXECUTE format('REVOKE ALL ON FUNCTION %s FROM PUBLIC, anon, authenticated', fn);
      EXECUTE format('GRANT EXECUTE ON FUNCTION %s TO service_role', fn);
    END IF;
  END LOOP;
END;
$$;
