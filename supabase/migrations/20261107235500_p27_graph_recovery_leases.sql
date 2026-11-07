-- P27-06: atomic, strictly scoped recovery leases for abandoned graph executions.
-- Service role only. No automatic replay of arbitrary workflow runs.
CREATE TABLE IF NOT EXISTS public.workflow_recovery_leases (
    run_id uuid PRIMARY KEY REFERENCES public.workflow_runs(id) ON DELETE CASCADE,
    org_id uuid NOT NULL,
    token uuid NOT NULL,
    owner text NOT NULL,
    claimed_at timestamptz NOT NULL DEFAULT now(),
    lease_expires_at timestamptz NOT NULL,
    attempts integer NOT NULL DEFAULT 1
);
CREATE INDEX IF NOT EXISTS workflow_recovery_leases_expires_idx
  ON public.workflow_recovery_leases (lease_expires_at);
ALTER TABLE public.workflow_recovery_leases ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON public.workflow_recovery_leases FROM PUBLIC, anon, authenticated;
GRANT SELECT, INSERT, UPDATE, DELETE ON public.workflow_recovery_leases TO service_role;

CREATE OR REPLACE FUNCTION public.claim_stale_graph_recovery(
    p_owner text, p_stale_seconds integer DEFAULT 3600,
    p_lease_seconds integer DEFAULT 600)
RETURNS TABLE(run_id uuid, org_id uuid, claim_token uuid, environment_name text, actor_id text)
LANGUAGE plpgsql SECURITY DEFINER SET search_path=public AS $$
DECLARE
    v_run record;
    v_token uuid := gen_random_uuid();
    v_claimed uuid;
BEGIN
    IF p_owner IS NULL OR length(trim(p_owner)) < 3 OR length(p_owner) > 160
       OR p_stale_seconds < 300 OR p_lease_seconds < 30
       OR p_lease_seconds > 3600 THEN
        RAISE EXCEPTION 'invalid recovery lease parameters';
    END IF;
    -- Lock the source run; concurrent claimers cannot select it together.
    -- A checkpoint and a running step are mandatory. Age is measured from
    -- the step, not merely from the creation date of a long-lived workflow.
    SELECT wr.id, wr.org_id, wr.environment, wr.triggered_by INTO v_run
    FROM public.workflow_runs wr
    WHERE jsonb_typeof(wr.parameters->'_graph_execution') = 'object'
      AND (
        -- First takeover: abandoned in-flight action, no recent step activity.
        (wr.status = 'running' AND EXISTS (
          SELECT 1 FROM public.workflow_steps s
          WHERE s.run_id = wr.id AND s.status = 'running'
            AND s.started_at IS NOT NULL
            AND s.started_at <= now() - make_interval(secs => p_stale_seconds)))
        OR
        -- The recovery owner itself died after the atomic running -> paused
        -- transition. Reclaim ONLY a previously leased in-flight run, never
        -- an ordinary human-paused workflow or a deliberately blocked result.
        (wr.status = 'paused'
         AND wr.parameters->'_graph_execution'->>'pause_reason' = 'executor_in_flight'
         AND EXISTS (
           SELECT 1 FROM public.workflow_recovery_leases old
           WHERE old.run_id=wr.id AND old.lease_expires_at <= now()))
      )
      AND NOT EXISTS (
        SELECT 1 FROM public.workflow_recovery_leases active
        WHERE active.run_id = wr.id AND active.lease_expires_at > now())
    ORDER BY wr.created_at, wr.id
    LIMIT 1
    FOR UPDATE OF wr SKIP LOCKED;
    IF NOT FOUND THEN RETURN; END IF;

    INSERT INTO public.workflow_recovery_leases
        (run_id, org_id, token, owner, claimed_at, lease_expires_at, attempts)
    VALUES (v_run.id, v_run.org_id, v_token, p_owner, now(),
            now() + make_interval(secs => p_lease_seconds), 1)
    ON CONFLICT ON CONSTRAINT workflow_recovery_leases_pkey DO UPDATE
       SET token=excluded.token, owner=excluded.owner, claimed_at=excluded.claimed_at,
           lease_expires_at=excluded.lease_expires_at,
           attempts=public.workflow_recovery_leases.attempts + 1
       WHERE public.workflow_recovery_leases.lease_expires_at <= now()
    RETURNING token INTO v_claimed;
    IF v_claimed IS NULL THEN RETURN; END IF;

    -- The claim and status transition commit atomically. The old worker's
    -- next status-conditional write must reject the now-paused run.
    UPDATE public.workflow_runs wr SET status='paused'
    WHERE wr.id=v_run.id AND wr.org_id=v_run.org_id
      AND wr.status IN ('running','paused');
    IF NOT FOUND THEN
        DELETE FROM public.workflow_recovery_leases l WHERE l.run_id=v_run.id AND l.token=v_token;
        RETURN;
    END IF;
    RETURN QUERY SELECT v_run.id::uuid, v_run.org_id::uuid, v_token,
                        coalesce(v_run.environment::text,'default'), v_run.triggered_by::text;
END; $$;

CREATE OR REPLACE FUNCTION public.assert_graph_recovery_lease(
    p_run_id uuid, p_token uuid)
RETURNS boolean
LANGUAGE sql STABLE SECURITY DEFINER SET search_path=public AS $$
    SELECT EXISTS(
        SELECT 1 FROM public.workflow_recovery_leases l
        JOIN public.workflow_runs r ON r.id=l.run_id AND r.org_id=l.org_id
        WHERE l.run_id=p_run_id AND l.token=p_token
          AND l.lease_expires_at > now()
          AND r.status IN ('paused','running')
    );
$$;

CREATE OR REPLACE FUNCTION public.graph_recovery_lease_active(p_run_id uuid)
RETURNS boolean
LANGUAGE sql STABLE SECURITY DEFINER SET search_path=public AS $
    SELECT EXISTS(
        SELECT 1 FROM public.workflow_recovery_leases
        WHERE run_id=p_run_id AND lease_expires_at > now()
    );
$;

CREATE OR REPLACE FUNCTION public.renew_graph_recovery_lease(
    p_run_id uuid, p_token uuid, p_seconds integer DEFAULT 600)
RETURNS boolean
LANGUAGE plpgsql SECURITY DEFINER SET search_path=public AS $$
BEGIN
    IF p_seconds < 30 OR p_seconds > 3600 THEN RETURN false; END IF;
    UPDATE public.workflow_recovery_leases
    SET lease_expires_at=now() + make_interval(secs=>p_seconds)
    WHERE run_id=p_run_id AND token=p_token AND lease_expires_at > now();
    RETURN FOUND;
END; $$;

CREATE OR REPLACE FUNCTION public.release_graph_recovery_lease(
    p_run_id uuid, p_token uuid)
RETURNS boolean
LANGUAGE plpgsql SECURITY DEFINER SET search_path=public AS $$
BEGIN
    DELETE FROM public.workflow_recovery_leases
      WHERE run_id=p_run_id AND token=p_token;
    RETURN FOUND;
END; $$;

REVOKE ALL ON FUNCTION public.claim_stale_graph_recovery(text,integer,integer) FROM PUBLIC, anon, authenticated;
REVOKE ALL ON FUNCTION public.assert_graph_recovery_lease(uuid,uuid) FROM PUBLIC, anon, authenticated;
REVOKE ALL ON FUNCTION public.renew_graph_recovery_lease(uuid,uuid,integer) FROM PUBLIC, anon, authenticated;
REVOKE ALL ON FUNCTION public.graph_recovery_lease_active(uuid) FROM PUBLIC, anon, authenticated;
REVOKE ALL ON FUNCTION public.release_graph_recovery_lease(uuid,uuid) FROM PUBLIC, anon, authenticated;
GRANT EXECUTE ON FUNCTION public.claim_stale_graph_recovery(text,integer,integer) TO service_role;
GRANT EXECUTE ON FUNCTION public.assert_graph_recovery_lease(uuid,uuid) TO service_role;
GRANT EXECUTE ON FUNCTION public.renew_graph_recovery_lease(uuid,uuid,integer) TO service_role;
GRANT EXECUTE ON FUNCTION public.graph_recovery_lease_active(uuid) TO service_role;
GRANT EXECUTE ON FUNCTION public.release_graph_recovery_lease(uuid,uuid) TO service_role;
