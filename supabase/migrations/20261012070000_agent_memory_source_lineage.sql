-- Memory lineage: name the connector an agent memory or customer observation was
-- learned from, so that a disconnect removes them along with the rest of the
-- connector's data.
--
-- NOT APPLIED TO PRODUCTION. Needs the owner's separate authorization and the
-- checkpoints in docs/delivery/memory-lineage-migration-checkpoint-plan-2026-10-12.md.
--
-- Depends on 20260708160300 (agent_memories.expires_at), 20260903120000 (memory_key,
-- is_current, valid_until, superseded_by, source_class) and 20261012024200
-- (source_purge_receipts, purge_connector_derived_data). Uses 20261012040000
-- (entity_observations, entity_behavior_signals) when present. Additive only;
-- safe to apply while the backend runs; every statement can be re-run.
--
-- What it adds:
--   * agent_memories.source_connector_id uuid / source_record_ref text (nullable).
--   * entity_observations.source_connector_id uuid (nullable), when that table exists.
--     No foreign keys: connectors are soft-deleted and may be hard-deleted later, and
--     the lineage must outlive the row so the purge can still find what it fed.
--     The backend writes them only when MEMORY_SOURCE_LINEAGE_ENABLED=true; turn it
--     on after this migration is applied. Rows written before that stay untagged
--     (see "Untagged rows" below and the legacy audit).
--   * purge_connector_memories(org, connector, disconnected_at, dry_run, vendor): the
--     memory half of the Phase 2B purge. The source.disconnected handler calls it
--     right after purge_connector_derived_data, with the same dry-run setting.
--
-- What purge_connector_memories removes, for one org and one connector, only rows
-- created at or before the disconnect (rows from a later reconnect are kept):
--   * agent_memories tagged with the connector (hard delete, as the per-agent memory
--     API does: history rows cascade, superseded_by / promotion-audit links are set
--     NULL by their foreign keys).
--   * entity_observations tagged with the connector. Untagged observations whose
--     source_system is the connector's vendor are removed only when no other live
--     connector of that vendor remains in the org (and this connector is not live
--     again); otherwise they cannot be told apart from the other connection's rows,
--     are kept, and are counted as entity_observations_unattributed. Observations of
--     another vendor, another connector or another org are never touched. User
--     corrections of a removed observation go with it (the quote is source content).
--   * entity_behavior_signals of every entity that lost an observation. Signals are
--     aggregates over all of an entity's observations and cannot be split by source,
--     so they are dropped and the daily rule run (compute_entity_behavior_signals)
--     rebuilds them from what survives. Signals of other entities are kept.
-- Not touched: org_entity_resolution_records (vendor bindings and aliases are
-- purge_connector_derived_data's; user-confirmed email recipients (integration
-- 'email') and Slack channels (integration 'conversation') written by
-- promote_confirmed_ledger_slots are user statements and persist).
--
-- Superseded values. A removed memory may have replaced an older value of the same
-- memory_key. That older value becomes current again only when all of these hold:
--   * it is not itself removed, and no surviving row is current for the key;
--   * valid provenance: either it names a connector that is still connected in the
--     same org (not this one), or it is untagged and independently sourced
--     (source_class user_direct or workflow_outcome, and a provenance that does not
--     name a connector, document, RAG, ingest, tool result, web fetch or external
--     source). Untagged legacy rows of any other class are not revealed;
--   * retention allows it: is_active, not expired (expires_at), and, for a value from
--     a still-connected connector, younger than that vendor's
--     sourceDataGovernance.retentionDays when the org set one.
-- Counted as agent_memories_restored; candidates that fail are left superseded and
-- counted as agent_memories_not_restored. Only one level is considered.
--
-- Receipt. The counts are merged into the receipt purge_connector_derived_data wrote
-- for the same disconnect and mode; the first counts stay (a redelivery after a real
-- purge finds 0). Dry run counts only; nothing is written but the receipt counts.
--
-- Index builds scan each table once under a SHARE lock (writes wait; the columns are
-- all NULL, so the partial indexes are empty and quick to build).
--
-- Supabase applies each migration file in one transaction (no explicit BEGIN/COMMIT).
--
-- Preflight (read-only; run before applying):
--   SELECT to_regclass('public.source_purge_receipts');                       -- expect not NULL
--   SELECT count(*) FROM information_schema.columns
--    WHERE table_schema = 'public' AND table_name = 'agent_memories'
--      AND column_name IN ('is_current', 'superseded_by', 'valid_until', 'memory_key',
--                          'source_class', 'expires_at', 'is_active');        -- expect 7
--   SELECT count(*) FROM information_schema.columns
--    WHERE table_schema = 'public' AND table_name IN ('agent_memories', 'entity_observations')
--      AND column_name IN ('source_connector_id', 'source_record_ref');        -- expect 0
--   SELECT proname FROM pg_proc WHERE pronamespace = 'public'::regnamespace
--     AND proname = 'purge_connector_memories';                                -- expect 0 rows
--   SELECT count(*) FROM public.agent_memories;                                -- size of the index scan
--
-- Rollback (manual; safe at any time, discards lineage tags only):
--   DROP FUNCTION IF EXISTS public.purge_connector_memories(uuid, uuid, timestamptz, boolean, text);
--   DROP INDEX IF EXISTS public.idx_entity_observations_org_source_connector;
--   ALTER TABLE IF EXISTS public.entity_observations DROP COLUMN IF EXISTS source_connector_id;
--   DROP INDEX IF EXISTS public.idx_agent_memories_org_source_connector;
--   ALTER TABLE public.agent_memories DROP COLUMN IF EXISTS source_record_ref,
--     DROP COLUMN IF EXISTS source_connector_id;
--   (Set MEMORY_SOURCE_LINEAGE_ENABLED=false first; writers then stop sending the columns.)

-- -----------------------------------------------------------------------------
-- 1) Lineage columns
-- -----------------------------------------------------------------------------
ALTER TABLE public.agent_memories
  ADD COLUMN IF NOT EXISTS source_connector_id uuid,
  ADD COLUMN IF NOT EXISTS source_record_ref text;

CREATE INDEX IF NOT EXISTS idx_agent_memories_org_source_connector
  ON public.agent_memories (org_id, source_connector_id)
  WHERE source_connector_id IS NOT NULL;

COMMENT ON COLUMN public.agent_memories.source_connector_id IS
  'connectors.id the memory was learned from (no FK: survives connector deletion); purged on disconnect.';
COMMENT ON COLUMN public.agent_memories.source_record_ref IS
  'Record in the source system the memory was learned from (vendor id or URL), when known.';

DO $$
BEGIN
  IF to_regclass('public.entity_observations') IS NOT NULL THEN
    ALTER TABLE public.entity_observations ADD COLUMN IF NOT EXISTS source_connector_id uuid;
    CREATE INDEX IF NOT EXISTS idx_entity_observations_org_source_connector
      ON public.entity_observations (org_id, source_connector_id)
      WHERE source_connector_id IS NOT NULL;
    COMMENT ON COLUMN public.entity_observations.source_connector_id IS
      'connectors.id the observed message was read through (no FK); purged on disconnect.';
  END IF;
END
$$;

-- -----------------------------------------------------------------------------
-- 2) Purge
-- -----------------------------------------------------------------------------
-- An earlier draft of this (never applied) file had a four-argument signature.
DROP FUNCTION IF EXISTS public.purge_connector_memories(uuid, uuid, timestamptz, boolean);

CREATE OR REPLACE FUNCTION public.purge_connector_memories(
  p_org_id uuid,
  p_connector_id uuid,
  p_disconnected_at timestamptz,
  p_dry_run boolean DEFAULT true,
  p_vendor text DEFAULT NULL
) RETURNS jsonb
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public, pg_temp
AS $$
DECLARE
  v_now timestamptz := now();
  v_vendor text := lower(nullif(trim(coalesce(p_vendor, '')), ''));
  v_vendor_shared boolean := true;
  v_retention jsonb := '{}'::jsonb;
  v_ids uuid[] := '{}';
  v_candidate_ids uuid[] := '{}';
  v_restore_ids uuid[] := '{}';
  v_obs_ids uuid[] := '{}';
  v_entity_ids uuid[] := '{}';
  n_memories int := 0;
  n_restored int := 0;
  n_not_restored int := 0;
  n_obs int := 0;
  n_obs_unattributed int := 0;
  n_signals int := 0;
  n_receipts int := 0;
  v_counts jsonb;
BEGIN
  IF p_org_id IS NULL OR p_connector_id IS NULL OR p_disconnected_at IS NULL THEN
    RAISE EXCEPTION 'purge_connector_memories: org, connector and disconnected_at are required';
  END IF;

  IF v_vendor IS NULL THEN
    SELECT lower(coalesce(nullif(trim(c.vendor), ''), c.type)) INTO v_vendor
      FROM public.connectors c WHERE c.id = p_connector_id AND c.org_id = p_org_id;
  END IF;

  -- Same rule as purge_connector_derived_data: another live connection of the vendor,
  -- or this connector live again, owns the vendor's untagged rows.
  IF v_vendor IS NOT NULL THEN
    SELECT EXISTS (
      SELECT 1 FROM public.connectors c
       WHERE c.org_id = p_org_id AND c.id <> p_connector_id AND c.deleted_at IS NULL
         AND v_vendor IN (lower(coalesce(c.vendor, '')), lower(coalesce(c.type, '')))
    ) OR EXISTS (
      SELECT 1 FROM public.connectors c WHERE c.id = p_connector_id AND c.deleted_at IS NULL
    ) INTO v_vendor_shared;
  END IF;

  -- Per-vendor retention the org configured (sourceDataGovernance.retentionDays).
  SELECT coalesce(o.settings -> 'sourceDataGovernance' -> 'retentionDays', '{}'::jsonb) INTO v_retention
    FROM public.organizations o WHERE o.id = p_org_id;
  IF v_retention IS NULL OR jsonb_typeof(v_retention) <> 'object' THEN
    v_retention := '{}'::jsonb;
  END IF;

  -- 2a) Agent memories tagged with this connector.
  SELECT coalesce(array_agg(m.id), '{}') INTO v_ids
    FROM public.agent_memories m
   WHERE m.org_id = p_org_id
     AND m.source_connector_id = p_connector_id
     AND m.created_at <= p_disconnected_at;
  n_memories := coalesce(array_length(v_ids, 1), 0);

  IF n_memories > 0 THEN
    -- Older values these memories replaced: not removed themselves, and no surviving
    -- current row for their key. One per key (the latest).
    SELECT coalesce(array_agg(p.id), '{}') INTO v_candidate_ids
      FROM (
        SELECT DISTINCT ON (o.memory_key) o.id
          FROM public.agent_memories o
         WHERE o.org_id = p_org_id
           AND o.superseded_by = ANY (v_ids)
           AND NOT (o.id = ANY (v_ids))
           AND o.memory_key IS NOT NULL
           AND NOT EXISTS (
             SELECT 1 FROM public.agent_memories c
              WHERE c.org_id = p_org_id AND c.memory_key = o.memory_key
                AND c.is_current IS TRUE AND NOT (c.id = ANY (v_ids)))
         ORDER BY o.memory_key, o.valid_from DESC, o.created_at DESC
      ) p;

    -- Of those, the ones with valid provenance that retention still allows.
    SELECT coalesce(array_agg(o.id), '{}') INTO v_restore_ids
      FROM public.agent_memories o
     WHERE o.id = ANY (v_candidate_ids)
       AND o.is_active IS TRUE
       AND (o.expires_at IS NULL OR o.expires_at > v_now)
       AND (
         -- From a connector that is still connected in this org.
         (o.source_connector_id IS NOT NULL AND o.source_connector_id <> p_connector_id
          AND EXISTS (
            SELECT 1 FROM public.connectors c
             WHERE c.id = o.source_connector_id AND c.org_id = p_org_id AND c.deleted_at IS NULL
               AND (
                 NOT (v_retention ? lower(coalesce(nullif(trim(c.vendor), ''), c.type)))
                 OR jsonb_typeof(v_retention -> lower(coalesce(nullif(trim(c.vendor), ''), c.type))) <> 'number'
                 OR o.created_at > v_now - make_interval(
                      days => (v_retention ->> lower(coalesce(nullif(trim(c.vendor), ''), c.type)))::numeric::int)
               )))
         OR
         -- Untagged and independently sourced.
         (o.source_connector_id IS NULL
          AND o.source_class IN ('user_direct', 'workflow_outcome')
          AND coalesce(o.provenance, '') !~* '(connector|document|rag:|ingest|tool_result|web_fetch|external|untrusted)')
       );
    n_restored := coalesce(array_length(v_restore_ids, 1), 0);
    n_not_restored := coalesce(array_length(v_candidate_ids, 1), 0) - n_restored;
  END IF;

  -- 2b) Customer observations and the behaviour signals computed from them.
  IF to_regclass('public.entity_observations') IS NOT NULL
     AND EXISTS (SELECT 1 FROM information_schema.columns
                  WHERE table_schema = 'public' AND table_name = 'entity_observations'
                    AND column_name = 'source_connector_id') THEN
    SELECT coalesce(array_agg(o.id), '{}'), coalesce(array_agg(DISTINCT o.entity_id), '{}')
      INTO v_obs_ids, v_entity_ids
      FROM public.entity_observations o
     WHERE o.org_id = p_org_id
       AND o.created_at <= p_disconnected_at
       AND (
         o.source_connector_id = p_connector_id
         OR (o.source_connector_id IS NULL AND NOT v_vendor_shared AND v_vendor IS NOT NULL
             AND lower(o.source_system) = v_vendor)
       );
    n_obs := coalesce(array_length(v_obs_ids, 1), 0);

    IF v_vendor IS NOT NULL AND v_vendor_shared THEN
      SELECT count(*) INTO n_obs_unattributed
        FROM public.entity_observations o
       WHERE o.org_id = p_org_id AND o.source_connector_id IS NULL
         AND o.created_at <= p_disconnected_at AND lower(o.source_system) = v_vendor;
    END IF;

    IF n_obs > 0 AND to_regclass('public.entity_behavior_signals') IS NOT NULL THEN
      SELECT count(*) INTO n_signals
        FROM public.entity_behavior_signals s
       WHERE s.org_id = p_org_id AND s.entity_id = ANY (v_entity_ids);
    END IF;
  END IF;

  IF NOT p_dry_run THEN
    IF n_memories > 0 THEN
      IF n_restored > 0 THEN
        UPDATE public.agent_memories
           SET is_current = true, valid_until = NULL, superseded_by = NULL, updated_at = now()
         WHERE id = ANY (v_restore_ids);
      END IF;
      -- Cascades to agent_memory_history of these rows; other links are set NULL.
      DELETE FROM public.agent_memories WHERE id = ANY (v_ids);
    END IF;
    IF n_obs > 0 THEN
      DELETE FROM public.entity_observations WHERE org_id = p_org_id AND id = ANY (v_obs_ids);
      IF n_signals > 0 THEN
        DELETE FROM public.entity_behavior_signals
         WHERE org_id = p_org_id AND entity_id = ANY (v_entity_ids);
      END IF;
    END IF;
  END IF;

  v_counts := jsonb_build_object(
    'agent_memories', n_memories,
    'agent_memories_restored', n_restored,
    'agent_memories_not_restored', n_not_restored,
    'entity_observations', n_obs,
    'entity_observations_unattributed', n_obs_unattributed,
    'entity_behavior_signals', n_signals
  );

  -- Merge into the receipt purge_connector_derived_data wrote for this disconnect
  -- and mode. The first counts stay (a redelivery after a real purge finds 0).
  IF to_regclass('public.source_purge_receipts') IS NOT NULL THEN
    UPDATE public.source_purge_receipts r
       SET counts = r.counts || v_counts
     WHERE r.connector_id = p_connector_id
       AND r.disconnected_at = p_disconnected_at
       AND r.dry_run = p_dry_run
       AND r.org_id = p_org_id
       AND NOT (r.counts ? 'agent_memories');
    GET DIAGNOSTICS n_receipts = ROW_COUNT;
  END IF;

  RETURN v_counts || jsonb_build_object('receipt_merged', n_receipts > 0);
END;
$$;

REVOKE ALL ON FUNCTION public.purge_connector_memories(uuid, uuid, timestamptz, boolean, text)
  FROM PUBLIC, anon, authenticated;
GRANT EXECUTE ON FUNCTION public.purge_connector_memories(uuid, uuid, timestamptz, boolean, text)
  TO service_role;
