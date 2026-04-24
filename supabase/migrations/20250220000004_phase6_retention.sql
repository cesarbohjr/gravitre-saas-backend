-- Phase 6: Retention helpers (explicit, operator-invoked)

CREATE OR REPLACE FUNCTION public.retention_purge(p_cutoff timestamptz, p_org_id uuid DEFAULT NULL)
RETURNS int
LANGUAGE plpgsql
AS $$
DECLARE
  v_deleted int;
BEGIN
  IF p_org_id IS NULL THEN
    DELETE FROM public.audit_events
     WHERE created_at < p_cutoff;
  ELSE
    DELETE FROM public.audit_events
     WHERE created_at < p_cutoff
       AND org_id = p_org_id;
  END IF;
  GET DIAGNOSTICS v_deleted = ROW_COUNT;
  RETURN v_deleted;
END;
$$;

CREATE OR REPLACE FUNCTION public.purge_audit_events_before(cutoff timestamptz, p_org_id uuid DEFAULT NULL)
RETURNS int
LANGUAGE plpgsql
AS $$
BEGIN
  RETURN public.retention_purge(cutoff, p_org_id);
END;
$$;

CREATE OR REPLACE FUNCTION public.purge_rag_retrieval_logs_before(cutoff timestamptz, p_org_id uuid DEFAULT NULL)
RETURNS int
LANGUAGE plpgsql
AS $$
DECLARE
  v_deleted int;
BEGIN
  IF p_org_id IS NULL THEN
    DELETE FROM public.rag_retrieval_logs
     WHERE created_at < cutoff;
  ELSE
    DELETE FROM public.rag_retrieval_logs
     WHERE created_at < cutoff
       AND org_id = p_org_id;
  END IF;
  GET DIAGNOSTICS v_deleted = ROW_COUNT;
  RETURN v_deleted;
END;
$$;
