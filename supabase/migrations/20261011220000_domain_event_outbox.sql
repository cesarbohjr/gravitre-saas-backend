-- Phase 2A: durable domain events (transactional outbox in Postgres).
--
-- What this adds (additive only; no existing row, column, policy or function changes):
--   1. public.domain_event_outbox: one row per domain event. Service role only (RLS on,
--      no policies; anon/authenticated have no privileges).
--   2. Producers as AFTER triggers, so the event row commits in the SAME transaction as
--      the business change (or not at all). No application call can forget to write it:
--        - workflow_runs: a run entering a terminal status -> 'execution.outcome_finalized'
--        - connectors: deleted_at set, or a connected row hard-deleted
--          (organisation deletion cascade)                  -> 'source.disconnected'
--      Trigger functions are SECURITY DEFINER so a write made under a user JWT can still
--      insert into the service-only outbox. ON CONFLICT DO NOTHING makes re-delivery of
--      the same transition a no-op (idempotency_key per transition).
--   3. Relay RPCs (service_role only): claim_domain_events (FOR UPDATE SKIP LOCKED with a
--      lease, safe across replicas), complete_domain_event / fail_domain_event (lease-owner
--      checked, retries with backoff, dead-letter after max_attempts),
--      domain_event_outbox_stats, prune_domain_events.
--
-- Nothing consumes events until the backend relay is enabled
-- (DOMAIN_EVENT_RELAY_ENABLED=true, default false). Rows simply accumulate as 'pending'.
--
-- Supabase applies each migration file in one transaction (no explicit BEGIN/COMMIT).
--
-- Preflight (read-only; run before applying):
--   -- names must be free
--   SELECT to_regclass('public.domain_event_outbox');                       -- expect NULL
--   SELECT proname FROM pg_proc WHERE pronamespace = 'public'::regnamespace
--     AND proname IN ('claim_domain_events','complete_domain_event','fail_domain_event',
--                     'domain_event_outbox_stats','prune_domain_events',
--                     'emit_workflow_run_terminal_event','emit_connector_disconnected_event');
--                                                                               -- expect 0 rows
--   SELECT tgname FROM pg_trigger WHERE tgname IN
--     ('workflow_runs_emit_terminal_event','connectors_emit_disconnected_event'); -- expect 0 rows
--   -- columns the triggers read must exist
--   SELECT table_name, column_name FROM information_schema.columns
--    WHERE table_schema = 'public'
--      AND ((table_name = 'workflow_runs' AND column_name IN ('id','org_id','workflow_id','status','completed_at'))
--        OR (table_name = 'connectors'    AND column_name IN ('id','org_id','type','deleted_at')));
--                                                                               -- expect 9 rows
--   -- expected event volume (terminal runs and disconnects per day, last 30 days)
--   SELECT date_trunc('day', completed_at) d, count(*) FROM public.workflow_runs
--    WHERE completed_at > now() - interval '30 days' GROUP BY 1 ORDER BY 1 DESC;
--   SELECT count(*) FROM public.connectors WHERE deleted_at > now() - interval '30 days';
--
-- Rollback (manual; safe at any time, business tables are untouched):
--   DROP TRIGGER IF EXISTS workflow_runs_emit_terminal_event ON public.workflow_runs;
--   DROP TRIGGER IF EXISTS connectors_emit_disconnected_event ON public.connectors;
--   DROP FUNCTION IF EXISTS public.emit_workflow_run_terminal_event();
--   DROP FUNCTION IF EXISTS public.emit_connector_disconnected_event();
--   DROP FUNCTION IF EXISTS public.claim_domain_events(text, integer, integer);
--   DROP FUNCTION IF EXISTS public.complete_domain_event(bigint, text, text[]);
--   DROP FUNCTION IF EXISTS public.fail_domain_event(bigint, text, text, text[], integer);
--   DROP FUNCTION IF EXISTS public.domain_event_outbox_stats();
--   DROP FUNCTION IF EXISTS public.prune_domain_events(integer, integer);
--   DROP TABLE IF EXISTS public.domain_event_outbox;   -- discards undelivered events
--   Dropping only the two triggers stops new events and keeps the backlog.

-- -----------------------------------------------------------------------------
-- 1) Table
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.domain_event_outbox (
  id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  event_id uuid NOT NULL DEFAULT gen_random_uuid() UNIQUE,
  -- No FK: an event about an organisation must survive that organisation's deletion
  -- (offboarding and purge consumers need it).
  org_id uuid NOT NULL,
  event_type text NOT NULL
    CHECK (event_type ~ '^[a-z][a-z0-9_]*(\.[a-z][a-z0-9_]*)+$'),
  schema_version smallint NOT NULL DEFAULT 1,
  aggregate_type text NOT NULL,
  aggregate_id text NOT NULL,
  idempotency_key text NOT NULL,
  -- Thin payload: identifiers and the transition. Consumers read current state.
  payload jsonb NOT NULL DEFAULT '{}'::jsonb,
  criticality text NOT NULL DEFAULT 'critical'
    CHECK (criticality IN ('critical', 'best_effort')),
  status text NOT NULL DEFAULT 'pending'
    CHECK (status IN ('pending', 'processing', 'delivered', 'dead')),
  attempts integer NOT NULL DEFAULT 0 CHECK (attempts >= 0),
  max_attempts integer NOT NULL DEFAULT 10 CHECK (max_attempts BETWEEN 1 AND 100),
  available_at timestamptz NOT NULL DEFAULT now(),
  lease_owner text,
  lease_expires_at timestamptz,
  -- Handlers that already succeeded for this event; a retry skips them.
  delivered_handlers text[] NOT NULL DEFAULT '{}'::text[],
  last_error text,
  created_at timestamptz NOT NULL DEFAULT now(),
  delivered_at timestamptz,
  CONSTRAINT domain_event_outbox_idempotency UNIQUE (event_type, idempotency_key),
  CONSTRAINT domain_event_outbox_lease_consistent CHECK (
    (status = 'processing') = (lease_owner IS NOT NULL AND lease_expires_at IS NOT NULL)
  )
);

COMMENT ON TABLE public.domain_event_outbox IS
  'Phase 2A transactional outbox. Producers are triggers (same transaction as the change); '
  'the backend relay claims with SKIP LOCKED leases. Service role only.';

-- Relay scan: next due pending events in id order.
CREATE INDEX IF NOT EXISTS idx_domain_event_outbox_due
  ON public.domain_event_outbox (available_at, id) WHERE status = 'pending';
-- Expired-lease recovery scan.
CREATE INDEX IF NOT EXISTS idx_domain_event_outbox_leases
  ON public.domain_event_outbox (lease_expires_at) WHERE status = 'processing';
-- Retention prune.
CREATE INDEX IF NOT EXISTS idx_domain_event_outbox_delivered
  ON public.domain_event_outbox (delivered_at) WHERE status = 'delivered';
CREATE INDEX IF NOT EXISTS idx_domain_event_outbox_org_created
  ON public.domain_event_outbox (org_id, created_at DESC);

ALTER TABLE public.domain_event_outbox ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON public.domain_event_outbox FROM anon, authenticated;
GRANT ALL ON public.domain_event_outbox TO service_role;

-- -----------------------------------------------------------------------------
-- 2) Producers (triggers)
-- -----------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION public.emit_workflow_run_terminal_event()
RETURNS trigger
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public, pg_temp
AS $$
DECLARE
  terminal constant text[] := ARRAY[
    'completed', 'failed', 'cancelled', 'partial_success',
    'flagged_for_review', 'verification_inconclusive'
  ];
BEGIN
  IF NEW.status IS NULL OR NOT (NEW.status = ANY (terminal)) THEN
    RETURN NULL;
  END IF;
  IF TG_OP = 'UPDATE' AND OLD.status IS NOT DISTINCT FROM NEW.status THEN
    RETURN NULL;  -- parameter/metadata edits on an already-terminal run emit nothing
  END IF;

  INSERT INTO public.domain_event_outbox
    (org_id, event_type, aggregate_type, aggregate_id, idempotency_key, payload)
  VALUES (
    NEW.org_id,
    'execution.outcome_finalized',
    'workflow_run',
    NEW.id::text,
    NEW.id::text || ':' || NEW.status,
    jsonb_build_object(
      'run_id', NEW.id,
      'workflow_id', NEW.workflow_id,
      'status', NEW.status,
      'previous_status', CASE WHEN TG_OP = 'UPDATE' THEN OLD.status END,
      'completed_at', NEW.completed_at
    )
  )
  ON CONFLICT ON CONSTRAINT domain_event_outbox_idempotency DO NOTHING;
  RETURN NULL;
END;
$$;

CREATE OR REPLACE FUNCTION public.emit_connector_disconnected_event()
RETURNS trigger
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public, pg_temp
AS $$
DECLARE
  removed_at timestamptz;
  src record;
BEGIN
  IF TG_OP = 'DELETE' THEN
    -- Hard delete (e.g. organisation deletion cascade) of a still-connected source.
    IF OLD.deleted_at IS NOT NULL THEN
      RETURN NULL;  -- its soft disconnect already emitted the event
    END IF;
    src := OLD;
    removed_at := now();
  ELSE
    IF NEW.deleted_at IS NULL THEN
      RETURN NULL;
    END IF;
    IF TG_OP = 'UPDATE' AND OLD.deleted_at IS NOT NULL THEN
      RETURN NULL;  -- already disconnected
    END IF;
    src := NEW;
    removed_at := NEW.deleted_at;
  END IF;

  INSERT INTO public.domain_event_outbox
    (org_id, event_type, aggregate_type, aggregate_id, idempotency_key, payload)
  VALUES (
    src.org_id,
    'source.disconnected',
    'connector',
    src.id::text,
    src.id::text || ':' || to_char(removed_at AT TIME ZONE 'UTC', 'YYYY-MM-DD"T"HH24:MI:SS.US'),
    jsonb_build_object(
      'connector_id', src.id,
      'connector_type', src.type,
      'deleted_at', removed_at,
      'hard_deleted', TG_OP = 'DELETE'
    )
  )
  ON CONFLICT ON CONSTRAINT domain_event_outbox_idempotency DO NOTHING;
  RETURN NULL;
END;
$$;

REVOKE ALL ON FUNCTION public.emit_workflow_run_terminal_event() FROM PUBLIC, anon, authenticated;
REVOKE ALL ON FUNCTION public.emit_connector_disconnected_event() FROM PUBLIC, anon, authenticated;

DROP TRIGGER IF EXISTS workflow_runs_emit_terminal_event ON public.workflow_runs;
CREATE TRIGGER workflow_runs_emit_terminal_event
  AFTER INSERT OR UPDATE OF status ON public.workflow_runs
  FOR EACH ROW EXECUTE FUNCTION public.emit_workflow_run_terminal_event();

DROP TRIGGER IF EXISTS connectors_emit_disconnected_event ON public.connectors;
CREATE TRIGGER connectors_emit_disconnected_event
  AFTER INSERT OR UPDATE OF deleted_at OR DELETE ON public.connectors
  FOR EACH ROW EXECUTE FUNCTION public.emit_connector_disconnected_event();

-- -----------------------------------------------------------------------------
-- 3) Relay RPCs (service_role only)
-- -----------------------------------------------------------------------------

-- Claim up to p_limit due events for p_worker. Due = pending and available, or
-- processing with an expired lease (a crashed or stalled replica). SKIP LOCKED lets
-- several replicas claim concurrently without blocking or double-claiming.
-- A reclaimed event that has used all its attempts is dead-lettered instead.
CREATE OR REPLACE FUNCTION public.claim_domain_events(
  p_worker text,
  p_limit integer DEFAULT 50,
  p_lease_seconds integer DEFAULT 120
)
RETURNS SETOF public.domain_event_outbox
LANGUAGE plpgsql
SET search_path = public, pg_temp
AS $$
BEGIN
  IF p_worker IS NULL OR length(p_worker) = 0 THEN
    RAISE EXCEPTION 'p_worker is required';
  END IF;

  UPDATE public.domain_event_outbox o
     SET status = 'dead',
         lease_owner = NULL,
         lease_expires_at = NULL,
         last_error = coalesce(o.last_error, '') || ' [lease expired after final attempt]'
   WHERE o.id IN (
     SELECT id FROM public.domain_event_outbox
      WHERE status = 'processing'
        AND lease_expires_at < now()
        AND attempts >= max_attempts
      ORDER BY id
      LIMIT 500
      FOR UPDATE SKIP LOCKED
   );

  -- Expired leases with attempts left go back to the queue (index: lease scan).
  UPDATE public.domain_event_outbox o
     SET status = 'pending',
         lease_owner = NULL,
         lease_expires_at = NULL,
         available_at = now()
   WHERE o.id IN (
     SELECT id FROM public.domain_event_outbox
      WHERE status = 'processing'
        AND lease_expires_at < now()
        AND attempts < max_attempts
      ORDER BY id
      LIMIT 500
      FOR UPDATE SKIP LOCKED
   );

  -- Claim due pending events (index: idx_domain_event_outbox_due).
  RETURN QUERY
  WITH due AS (
    SELECT id FROM public.domain_event_outbox
     WHERE status = 'pending' AND available_at <= now()
     ORDER BY available_at, id
     LIMIT greatest(1, least(coalesce(p_limit, 50), 500))
     FOR UPDATE SKIP LOCKED
  )
  UPDATE public.domain_event_outbox o
     SET status = 'processing',
         lease_owner = p_worker,
         lease_expires_at = now() + make_interval(secs => greatest(10, least(coalesce(p_lease_seconds, 120), 3600))),
         attempts = o.attempts + 1
    FROM due
   WHERE o.id = due.id
  RETURNING o.*;
END;
$$;

-- Mark delivered. Only the current lease owner can complete; returns false otherwise
-- (the lease expired and another replica took the event).
CREATE OR REPLACE FUNCTION public.complete_domain_event(
  p_id bigint,
  p_worker text,
  p_delivered_handlers text[] DEFAULT '{}'::text[]
)
RETURNS boolean
LANGUAGE plpgsql
SET search_path = public, pg_temp
AS $$
DECLARE
  n integer;
BEGIN
  UPDATE public.domain_event_outbox
     SET status = 'delivered',
         delivered_at = now(),
         lease_owner = NULL,
         lease_expires_at = NULL,
         last_error = NULL,
         delivered_handlers = coalesce(p_delivered_handlers, delivered_handlers)
   WHERE id = p_id AND status = 'processing' AND lease_owner = p_worker;
  GET DIAGNOSTICS n = ROW_COUNT;
  RETURN n = 1;
END;
$$;

-- Record a failed attempt. Keeps the handlers that already succeeded, schedules a
-- retry after p_retry_seconds, or dead-letters once attempts reach max_attempts.
-- Returns the new status, or NULL when p_worker no longer holds the lease.
CREATE OR REPLACE FUNCTION public.fail_domain_event(
  p_id bigint,
  p_worker text,
  p_error text,
  p_delivered_handlers text[] DEFAULT '{}'::text[],
  p_retry_seconds integer DEFAULT 30
)
RETURNS text
LANGUAGE plpgsql
SET search_path = public, pg_temp
AS $$
DECLARE
  new_status text;
BEGIN
  UPDATE public.domain_event_outbox
     SET status = CASE WHEN attempts >= max_attempts THEN 'dead' ELSE 'pending' END,
         available_at = now() + make_interval(secs => greatest(1, least(coalesce(p_retry_seconds, 30), 86400))),
         lease_owner = NULL,
         lease_expires_at = NULL,
         last_error = left(coalesce(p_error, 'unknown error'), 2000),
         delivered_handlers = coalesce(p_delivered_handlers, delivered_handlers)
   WHERE id = p_id AND status = 'processing' AND lease_owner = p_worker
  RETURNING status INTO new_status;
  RETURN new_status;
END;
$$;

CREATE OR REPLACE FUNCTION public.domain_event_outbox_stats()
RETURNS jsonb
LANGUAGE sql
STABLE
SET search_path = public, pg_temp
AS $$
  SELECT jsonb_build_object(
    'pending', count(*) FILTER (WHERE status = 'pending'),
    'pending_due', count(*) FILTER (WHERE status = 'pending' AND available_at <= now()),
    'processing', count(*) FILTER (WHERE status = 'processing'),
    'expired_leases', count(*) FILTER (WHERE status = 'processing' AND lease_expires_at < now()),
    'delivered', count(*) FILTER (WHERE status = 'delivered'),
    'dead', count(*) FILTER (WHERE status = 'dead'),
    'retrying', count(*) FILTER (WHERE status = 'pending' AND attempts > 0),
    'oldest_pending_age_seconds',
      coalesce(extract(epoch FROM now() - min(created_at) FILTER (WHERE status = 'pending')), 0)::bigint
  )
  FROM public.domain_event_outbox;
$$;

-- Delete delivered events older than p_retention_days, at most p_batch rows per call.
-- Dead events are never pruned automatically (they need a person to look at them).
CREATE OR REPLACE FUNCTION public.prune_domain_events(
  p_retention_days integer DEFAULT 14,
  p_batch integer DEFAULT 5000
)
RETURNS integer
LANGUAGE plpgsql
SET search_path = public, pg_temp
AS $$
DECLARE
  n integer;
BEGIN
  DELETE FROM public.domain_event_outbox
   WHERE id IN (
     SELECT id FROM public.domain_event_outbox
      WHERE status = 'delivered'
        AND delivered_at < now() - make_interval(days => greatest(1, coalesce(p_retention_days, 14)))
      ORDER BY id
      LIMIT greatest(1, least(coalesce(p_batch, 5000), 50000))
   );
  GET DIAGNOSTICS n = ROW_COUNT;
  RETURN n;
END;
$$;

REVOKE ALL ON FUNCTION public.claim_domain_events(text, integer, integer) FROM PUBLIC, anon, authenticated;
REVOKE ALL ON FUNCTION public.complete_domain_event(bigint, text, text[]) FROM PUBLIC, anon, authenticated;
REVOKE ALL ON FUNCTION public.fail_domain_event(bigint, text, text, text[], integer) FROM PUBLIC, anon, authenticated;
REVOKE ALL ON FUNCTION public.domain_event_outbox_stats() FROM PUBLIC, anon, authenticated;
REVOKE ALL ON FUNCTION public.prune_domain_events(integer, integer) FROM PUBLIC, anon, authenticated;
GRANT EXECUTE ON FUNCTION public.claim_domain_events(text, integer, integer) TO service_role;
GRANT EXECUTE ON FUNCTION public.complete_domain_event(bigint, text, text[]) TO service_role;
GRANT EXECUTE ON FUNCTION public.fail_domain_event(bigint, text, text, text[], integer) TO service_role;
GRANT EXECUTE ON FUNCTION public.domain_event_outbox_stats() TO service_role;
GRANT EXECUTE ON FUNCTION public.prune_domain_events(integer, integer) TO service_role;
