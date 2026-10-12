-- Memory lineage: name the connector an agent memory was learned from, so that a
-- disconnect can remove those memories along with the rest of the connector's data.
--
-- Depends on 20260903120000_memory_hardening_temporal.sql (memory_key, is_current,
-- valid_until, superseded_by) and 20261012010000_source_lifecycle_purge.sql
-- (source_purge_receipts). Additive only; safe to apply while the backend runs.
--
-- What it adds:
--   * agent_memories.source_connector_id uuid / source_record_ref text (nullable).
--     No foreign key: connectors are soft-deleted and may be hard-deleted later, and
--     the lineage must outlive the row so the purge can still find the memories.
--     The backend writes them only when MEMORY_SOURCE_LINEAGE_ENABLED=true; turn it
--     on after this migration is applied. Rows written before that stay untagged
--     and are not purged by connector.
--   * purge_connector_memories(org, connector, disconnected_at, dry_run): the memory
--     half of the Phase 2B purge. The source.disconnected handler calls it right
--     after purge_connector_derived_data, with the same dry-run setting.
--
-- Deletion choice. Memories are hard-deleted, as the per-agent memory API does
-- (agent_memory_service.delete_agent_memory): agent_memory_history rows of a
-- deleted memory cascade, superseded_by / agent_memory_promotion_audit.memory_id
-- links to it are set NULL by their foreign keys. Deactivating instead
-- (is_active=false, as turn retraction does) would leave the connector's content
-- stored, which is what a disconnect must not do.
-- A purged memory that had superseded an older value of the same memory_key (one
-- not itself learned from this connector) gives that value back: the older row is
-- made current again, unless another surviving row is current for the key. The
-- purge removes what was learned from the source; it does not also erase what was
-- known before it. Counted as agent_memories_restored.
--
-- Scope: org_id = p_org_id AND source_connector_id = p_connector_id AND
-- created_at <= p_disconnected_at (memories from a later reconnect are kept).
-- Idempotent: delete-by-filter; a second delivery removes nothing more, and the
-- receipt keeps its first agent_memories count.
--
-- The index build scans agent_memories once under a SHARE lock (writes wait for
-- it; the column is all NULL, so the partial index is empty and quick to build).
--
-- Supabase applies each migration file in one transaction (no explicit BEGIN/COMMIT).
--
-- Preflight (read-only; run before applying):
--   SELECT to_regclass('public.source_purge_receipts');                       -- expect not NULL
--   SELECT count(*) FROM information_schema.columns
--    WHERE table_schema = 'public' AND table_name = 'agent_memories'
--      AND column_name IN ('is_current', 'superseded_by', 'valid_until', 'memory_key'); -- expect 4
--   SELECT count(*) FROM information_schema.columns
--    WHERE table_schema = 'public' AND table_name = 'agent_memories'
--      AND column_name IN ('source_connector_id', 'source_record_ref');        -- expect 0
--   SELECT proname FROM pg_proc WHERE pronamespace = 'public'::regnamespace
--     AND proname = 'purge_connector_memories';                                -- expect 0 rows
--   SELECT count(*) FROM public.agent_memories;                                -- size of the index scan
--
-- Rollback (manual; safe at any time, discards lineage tags only):
--   DROP FUNCTION IF EXISTS public.purge_connector_memories(uuid, uuid, timestamptz, boolean);
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

-- -----------------------------------------------------------------------------
-- 2) Purge
-- -----------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION public.purge_connector_memories(
  p_org_id uuid,
  p_connector_id uuid,
  p_disconnected_at timestamptz,
  p_dry_run boolean DEFAULT true
) RETURNS jsonb
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public, pg_temp
AS $$
DECLARE
  v_ids uuid[];
  v_restore_ids uuid[];
  n_memories int := 0;
  n_restored int := 0;
  n_receipts int := 0;
  v_counts jsonb;
BEGIN
  IF p_org_id IS NULL OR p_connector_id IS NULL OR p_disconnected_at IS NULL THEN
    RAISE EXCEPTION 'purge_connector_memories: org, connector and disconnected_at are required';
  END IF;

  SELECT coalesce(array_agg(m.id), '{}') INTO v_ids
    FROM public.agent_memories m
   WHERE m.org_id = p_org_id
     AND m.source_connector_id = p_connector_id
     AND m.created_at <= p_disconnected_at;
  n_memories := coalesce(array_length(v_ids, 1), 0);

  IF n_memories > 0 THEN
    -- Older values these memories replaced, to be made current again: not purged
    -- themselves, and no surviving current row for their key. One per key.
    SELECT coalesce(array_agg(p.id), '{}') INTO v_restore_ids
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
    n_restored := coalesce(array_length(v_restore_ids, 1), 0);
  END IF;

  IF NOT p_dry_run AND n_memories > 0 THEN
    IF n_restored > 0 THEN
      UPDATE public.agent_memories
         SET is_current = true, valid_until = NULL, superseded_by = NULL, updated_at = now()
       WHERE id = ANY (v_restore_ids);
    END IF;
    -- Cascades to agent_memory_history of these rows; other links are set NULL.
    DELETE FROM public.agent_memories WHERE id = ANY (v_ids);
  END IF;

  -- Merge into the receipt purge_connector_derived_data wrote for this disconnect
  -- and mode. The first count stays (a redelivery after a real purge finds 0).
  IF to_regclass('public.source_purge_receipts') IS NOT NULL THEN
    UPDATE public.source_purge_receipts r
       SET counts = r.counts || jsonb_build_object(
             'agent_memories', n_memories,
             'agent_memories_restored', n_restored)
     WHERE r.connector_id = p_connector_id
       AND r.disconnected_at = p_disconnected_at
       AND r.dry_run = p_dry_run
       AND r.org_id = p_org_id
       AND NOT (r.counts ? 'agent_memories');
    GET DIAGNOSTICS n_receipts = ROW_COUNT;
  END IF;

  v_counts := jsonb_build_object(
    'agent_memories', n_memories,
    'agent_memories_restored', n_restored,
    'receipt_merged', n_receipts > 0
  );
  RETURN v_counts;
END;
$$;

REVOKE ALL ON FUNCTION public.purge_connector_memories(uuid, uuid, timestamptz, boolean)
  FROM PUBLIC, anon, authenticated;
GRANT EXECUTE ON FUNCTION public.purge_connector_memories(uuid, uuid, timestamptz, boolean)
  TO service_role;
