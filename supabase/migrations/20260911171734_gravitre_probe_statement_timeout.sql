-- Isolated-org Response Composer proof: real SQLSTATE 57014.
-- Function-level SET applies on entry (SET inside plpgsql does not cancel the
-- remainder of the same function). Called from composer_failure_triggers.py.

CREATE OR REPLACE FUNCTION public.gravitre_probe_statement_timeout()
RETURNS void
LANGUAGE sql
SET statement_timeout = '120ms'
AS $$
  SELECT pg_sleep(3);
$$;

REVOKE ALL ON FUNCTION public.gravitre_probe_statement_timeout() FROM PUBLIC;
GRANT EXECUTE ON FUNCTION public.gravitre_probe_statement_timeout() TO service_role;
