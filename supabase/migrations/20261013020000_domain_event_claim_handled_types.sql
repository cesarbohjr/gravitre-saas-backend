-- Relay claims only event types that have a registered handler.
--
-- Before: claim_domain_events took every due event, and the relay marked an event
-- 'delivered' when no handler was registered for its type (nothing ran, nothing
-- failed). Turning DOMAIN_EVENT_RELAY_ENABLED on while OUTCOME_LEARNING_HANDLER
-- was off would have consumed every pending execution.outcome_finalized event,
-- including the ones already waiting in production, with no handler run.
--
-- After:
--   claim_domain_events(..., p_event_types)  claims only those types. NULL keeps the
--     old any-type behaviour for callers that have not been updated; an empty
--     array claims nothing.
--   release_domain_event(p_id, p_worker)  puts a claimed event back to pending
--     without using an attempt, for an event whose handler is not registered.
--   domain_event_outbox_stats() also reports pending counts per event type, so the
--     backlog for a type can be checked before its handler is switched on.
--
-- Unhandled events stay 'pending' with their attempts untouched until a handler
-- for their type is registered.
--
-- Deploy order: this migration before the backend that passes p_event_types.
-- A backend that passes p_event_types against the old function gets an error and
-- claims nothing (it does not fall back to claiming every type).

DROP FUNCTION IF EXISTS public.claim_domain_events(text, integer, integer);

CREATE OR REPLACE FUNCTION public.claim_domain_events(
  p_worker text,
  p_limit integer DEFAULT 50,
  p_lease_seconds integer DEFAULT 120,
  p_event_types text[] DEFAULT NULL
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

  IF p_event_types IS NOT NULL AND cardinality(p_event_types) = 0 THEN
    RETURN;
  END IF;

  -- Claim due pending events of the handled types (index: idx_domain_event_outbox_due).
  RETURN QUERY
  WITH due AS (
    SELECT id FROM public.domain_event_outbox
     WHERE status = 'pending'
       AND available_at <= now()
       AND (p_event_types IS NULL OR event_type = ANY (p_event_types))
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

-- Hand a claimed event back without spending an attempt. Only the lease owner can.
CREATE OR REPLACE FUNCTION public.release_domain_event(
  p_id bigint,
  p_worker text,
  p_retry_seconds integer DEFAULT 60
)
RETURNS boolean
LANGUAGE plpgsql
SET search_path = public, pg_temp
AS $$
DECLARE
  n integer;
BEGIN
  UPDATE public.domain_event_outbox
     SET status = 'pending',
         attempts = greatest(attempts - 1, 0),
         available_at = now() + make_interval(secs => greatest(1, least(coalesce(p_retry_seconds, 60), 86400))),
         lease_owner = NULL,
         lease_expires_at = NULL
   WHERE id = p_id AND status = 'processing' AND lease_owner = p_worker;
  GET DIAGNOSTICS n = ROW_COUNT;
  RETURN n = 1;
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
      coalesce(extract(epoch FROM now() - min(created_at) FILTER (WHERE status = 'pending')), 0)::bigint,
    'pending_by_type', coalesce((
      SELECT jsonb_object_agg(event_type, n)
      FROM (
        SELECT event_type, count(*) AS n
        FROM public.domain_event_outbox
        WHERE status = 'pending'
        GROUP BY event_type
      ) per_type
    ), '{}'::jsonb)
  )
  FROM public.domain_event_outbox;
$$;

REVOKE ALL ON FUNCTION public.claim_domain_events(text, integer, integer, text[]) FROM PUBLIC, anon, authenticated;
REVOKE ALL ON FUNCTION public.release_domain_event(bigint, text, integer) FROM PUBLIC, anon, authenticated;
REVOKE ALL ON FUNCTION public.domain_event_outbox_stats() FROM PUBLIC, anon, authenticated;
GRANT EXECUTE ON FUNCTION public.claim_domain_events(text, integer, integer, text[]) TO service_role;
GRANT EXECUTE ON FUNCTION public.release_domain_event(bigint, text, integer) TO service_role;
GRANT EXECUTE ON FUNCTION public.domain_event_outbox_stats() TO service_role;
