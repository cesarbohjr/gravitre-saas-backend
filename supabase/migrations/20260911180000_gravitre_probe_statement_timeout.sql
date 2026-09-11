-- Isolated-org Response Composer proof: real SQLSTATE 57014.
-- Called only from backend/app/services/composer_failure_triggers.py via service role.

CREATE OR REPLACE FUNCTION public.gravitre_probe_statement_timeout()
RETURNS void
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
BEGIN
  PERFORM set_config('statement_timeout', '120ms', true);
  PERFORM pg_sleep(3);
END;
$$;

REVOKE ALL ON FUNCTION public.gravitre_probe_statement_timeout() FROM PUBLIC;
GRANT EXECUTE ON FUNCTION public.gravitre_probe_statement_timeout() TO service_role;
