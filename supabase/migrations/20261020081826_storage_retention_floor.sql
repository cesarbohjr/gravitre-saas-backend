-- Part 3 of the storage migration (see 20261020081535_storage_retention_metering.sql).

-- -----------------------------------------------------------------------------
-- 3) Retention functions
-- -----------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION public.data_retention_floor_days(p_table text)
RETURNS int
LANGUAGE sql
IMMUTABLE
SET search_path = public, pg_temp
AS $$
  SELECT CASE p_table
    WHEN 'audit_logs' THEN 365
    WHEN 'audit_events' THEN 365
    WHEN 'model_calls' THEN 400
    WHEN 'ai_pipeline_latency' THEN 30
    WHEN 'cognitive_turn_traces' THEN 30
    ELSE NULL
  END;
$$;

-- Extra predicate on alias t: approval / rejection rows of the audit trail are kept.
CREATE OR REPLACE FUNCTION public.data_retention_where(p_table text)
RETURNS text
LANGUAGE sql
IMMUTABLE
SET search_path = public, pg_temp
AS $$
  SELECT CASE
    WHEN p_table IN ('audit_logs', 'audit_events')
      THEN ' AND t.action !~* ''(approv|reject)'''
    ELSE ''
  END;
$$;

REVOKE ALL ON FUNCTION public.data_retention_floor_days(text) FROM PUBLIC, anon, authenticated;
REVOKE ALL ON FUNCTION public.data_retention_where(text) FROM PUBLIC, anon, authenticated;
GRANT EXECUTE ON FUNCTION public.data_retention_floor_days(text) TO service_role;
GRANT EXECUTE ON FUNCTION public.data_retention_where(text) TO service_role;
