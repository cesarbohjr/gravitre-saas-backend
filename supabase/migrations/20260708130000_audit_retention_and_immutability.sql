-- STA-274: Align retention purge with audit_logs UI table; enforce read-only RLS for members.

CREATE OR REPLACE FUNCTION public.retention_purge(p_cutoff timestamptz, p_org_id uuid DEFAULT NULL)
RETURNS int
LANGUAGE plpgsql
AS $$
DECLARE
  v_deleted int := 0;
  v_events int;
  v_logs int;
BEGIN
  IF p_org_id IS NULL THEN
    DELETE FROM public.audit_events
     WHERE created_at < p_cutoff;
  ELSE
    DELETE FROM public.audit_events
     WHERE created_at < p_cutoff
       AND org_id = p_org_id;
  END IF;
  GET DIAGNOSTICS v_events = ROW_COUNT;
  v_deleted := v_deleted + v_events;

  IF to_regclass('public.audit_logs') IS NOT NULL THEN
    IF EXISTS (
      SELECT 1
      FROM information_schema.columns
      WHERE table_schema = 'public'
        AND table_name = 'audit_logs'
        AND column_name = 'timestamp'
    ) THEN
      IF p_org_id IS NULL THEN
        DELETE FROM public.audit_logs
         WHERE COALESCE(created_at, timestamp) < p_cutoff;
      ELSE
        DELETE FROM public.audit_logs
         WHERE COALESCE(created_at, timestamp) < p_cutoff
           AND org_id = p_org_id;
      END IF;
    ELSE
      IF p_org_id IS NULL THEN
        DELETE FROM public.audit_logs
         WHERE created_at < p_cutoff;
      ELSE
        DELETE FROM public.audit_logs
         WHERE created_at < p_cutoff
           AND org_id = p_org_id;
      END IF;
    END IF;
    GET DIAGNOSTICS v_logs = ROW_COUNT;
    v_deleted := v_deleted + v_logs;
  END IF;

  RETURN v_deleted;
END;
$$;

-- audit_logs: org members may read; writes go through service role only.
DROP POLICY IF EXISTS "audit_logs_org_scope" ON public.audit_logs;
CREATE POLICY "audit_logs_org_read"
  ON public.audit_logs FOR SELECT
  USING (public.auth_org_accessible(org_id));

-- audit_events: same immutability posture (metrics/rollups source table).
DO $$
BEGIN
  IF to_regclass('public.audit_events') IS NOT NULL THEN
    EXECUTE 'DROP POLICY IF EXISTS "audit_events_org_residency" ON public.audit_events';
    EXECUTE 'DROP POLICY IF EXISTS "audit_events_org" ON public.audit_events';
    EXECUTE $policy$
      CREATE POLICY "audit_events_org_read"
        ON public.audit_events FOR SELECT
        USING (public.auth_org_accessible(org_id))
    $policy$;
  END IF;
END $$;
