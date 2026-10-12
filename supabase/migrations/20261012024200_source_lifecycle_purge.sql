-- Phase 2B: source lifecycle. When a connector is disconnected, remove the customer data
-- Gravitre derived from it, in one transaction, and keep a receipt that proves it.
--
-- Depends on 20261011220000_domain_event_outbox.sql (the 'source.disconnected' event the
-- backend handler consumes). Nothing runs until the relay is enabled
-- (DOMAIN_EVENT_RELAY_ENABLED=true); even then the handler only plans (dry run) until
-- SOURCE_PURGE_DRY_RUN=false.
--
-- What purge_connector_derived_data removes for (org, connector, vendor, disconnected_at):
--   * rag_sources created by that connector at or before the disconnect (metadata
--     connector_id, or a "<vendor>_rag_source_id" key in the connector config), which
--     cascades to rag_documents, rag_chunks, rag_embeddings and rag_ingest_jobs.
--     Sources created after the disconnect (a reconnect) are kept.
--   * agent_knowledge_references pointing at the connector (summaries of its records).
--   * queued/running knowledge_sync_jobs for the connector are marked skipped.
--   * only when no other live connector of the same vendor remains in the org:
--     org_business_entity_bindings and org_entity_resolution_records for that vendor,
--     then org_business_entities left with no binding by this purge.
-- Kept on purpose: connector configuration, agent_knowledge_assignments (which agent may
-- read which source), audit history, agent_memories (no source tag exists yet).
--
-- Idempotent: every step is delete-by-filter, so a second delivery removes nothing more;
-- the receipt keeps the first counts (ON CONFLICT DO NOTHING per disconnect and mode).
--
-- Supabase applies each migration file in one transaction (no explicit BEGIN/COMMIT).
--
-- Preflight (read-only; run before applying):
--   SELECT to_regclass('public.source_purge_receipts');                      -- expect NULL
--   SELECT to_regclass('public.domain_event_outbox');                         -- expect not NULL
--   SELECT proname FROM pg_proc WHERE pronamespace = 'public'::regnamespace
--     AND proname = 'purge_connector_derived_data';                           -- expect 0 rows
--   -- what a purge would touch today, per disconnected connector (no writes):
--   SELECT c.id, c.type, c.deleted_at,
--          (SELECT count(*) FROM public.rag_sources s
--            WHERE s.org_id = c.org_id AND s.metadata->>'connector_id' = c.id::text) AS sources
--     FROM public.connectors c WHERE c.deleted_at IS NOT NULL ORDER BY c.deleted_at DESC LIMIT 50;
--
-- Rollback (manual; safe at any time):
--   DROP FUNCTION IF EXISTS public.purge_connector_derived_data(uuid, uuid, text, timestamptz, boolean, uuid);
--   DROP TABLE IF EXISTS public.source_purge_receipts;   -- discards receipts only

-- -----------------------------------------------------------------------------
-- 1) Receipts
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.source_purge_receipts (
  id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  -- No FK: the receipt must outlive the connector and, for offboarding, the org.
  org_id uuid NOT NULL,
  connector_id uuid NOT NULL,
  vendor text NOT NULL,
  disconnected_at timestamptz NOT NULL,
  dry_run boolean NOT NULL,
  event_id uuid,
  counts jsonb NOT NULL DEFAULT '{}'::jsonb,
  provider_revoke jsonb,
  created_at timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT source_purge_receipts_once UNIQUE (connector_id, disconnected_at, dry_run)
);

CREATE INDEX IF NOT EXISTS idx_source_purge_receipts_org_created
  ON public.source_purge_receipts (org_id, created_at DESC);

ALTER TABLE public.source_purge_receipts ENABLE ROW LEVEL SECURITY;
-- No policies: service role only.
REVOKE ALL ON public.source_purge_receipts FROM anon, authenticated;
GRANT SELECT, INSERT ON public.source_purge_receipts TO service_role;

COMMENT ON TABLE public.source_purge_receipts IS
  'Proof of removal of connector-derived data after a disconnect (Phase 2B). dry_run rows are plans.';

-- -----------------------------------------------------------------------------
-- 2) Purge
-- -----------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION public.purge_connector_derived_data(
  p_org_id uuid,
  p_connector_id uuid,
  p_vendor text,
  p_disconnected_at timestamptz,
  p_dry_run boolean DEFAULT true,
  p_event_id uuid DEFAULT NULL
) RETURNS jsonb
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public, pg_temp
AS $$
DECLARE
  v_vendor text := lower(coalesce(nullif(trim(p_vendor), ''), 'unknown'));
  v_source_ids uuid[];
  v_entity_ids uuid[];
  v_vendor_shared boolean;
  n_sources int := 0;
  n_documents int := 0;
  n_chunks int := 0;
  n_refs int := 0;
  n_jobs int := 0;
  n_bindings int := 0;
  n_aliases int := 0;
  n_entities int := 0;
  v_counts jsonb;
BEGIN
  IF p_org_id IS NULL OR p_connector_id IS NULL OR p_disconnected_at IS NULL THEN
    RAISE EXCEPTION 'purge_connector_derived_data: org, connector and disconnected_at are required';
  END IF;

  -- A purge for a connector that is live again must be about its earlier life only.
  SELECT coalesce(array_agg(s.id), '{}') INTO v_source_ids
    FROM public.rag_sources s
   WHERE s.org_id = p_org_id
     AND s.created_at <= p_disconnected_at
     AND (
       s.metadata->>'connector_id' = p_connector_id::text
       OR s.id::text IN (
         SELECT kv.value
           FROM public.connectors c, jsonb_each_text(coalesce(c.config, '{}'::jsonb)) kv
          WHERE c.id = p_connector_id AND c.org_id = p_org_id
            AND kv.key LIKE '%\_rag\_source\_id'
            AND kv.value ~* '^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$'
       )
     );

  n_sources := coalesce(array_length(v_source_ids, 1), 0);
  IF n_sources > 0 THEN
    SELECT count(*) INTO n_documents FROM public.rag_documents WHERE source_id = ANY (v_source_ids);
    SELECT count(*) INTO n_chunks FROM public.rag_chunks WHERE source_id = ANY (v_source_ids);
  END IF;

  IF to_regclass('public.agent_knowledge_references') IS NOT NULL THEN
    SELECT count(*) INTO n_refs FROM public.agent_knowledge_references
     WHERE org_id = p_org_id AND connector_id = p_connector_id
       AND created_at <= p_disconnected_at;
  END IF;

  IF to_regclass('public.knowledge_sync_jobs') IS NOT NULL THEN
    SELECT count(*) INTO n_jobs FROM public.knowledge_sync_jobs
     WHERE org_id = p_org_id AND connector_id = p_connector_id
       AND status IN ('queued', 'running') AND created_at <= p_disconnected_at;
  END IF;

  SELECT EXISTS (
    SELECT 1 FROM public.connectors c
     WHERE c.org_id = p_org_id AND c.id <> p_connector_id AND c.deleted_at IS NULL
       AND v_vendor IN (lower(coalesce(c.vendor, '')), lower(coalesce(c.type, '')))
  ) OR EXISTS (
    -- The same connector reconnected: its vendor-level joins belong to the live connection.
    SELECT 1 FROM public.connectors c
     WHERE c.id = p_connector_id AND c.deleted_at IS NULL
  ) INTO v_vendor_shared;

  IF NOT v_vendor_shared THEN
    IF to_regclass('public.org_business_entity_bindings') IS NOT NULL THEN
      SELECT count(*), coalesce(array_agg(DISTINCT entity_id), '{}')
        INTO n_bindings, v_entity_ids
        FROM public.org_business_entity_bindings
       WHERE org_id = p_org_id AND lower(system) = v_vendor;
      SELECT count(*) INTO n_entities FROM public.org_business_entities e
       WHERE e.id = ANY (v_entity_ids)
         AND NOT EXISTS (
           SELECT 1 FROM public.org_business_entity_bindings b
            WHERE b.entity_id = e.id AND lower(b.system) <> v_vendor);
    END IF;
    IF to_regclass('public.org_entity_resolution_records') IS NOT NULL THEN
      SELECT count(*) INTO n_aliases FROM public.org_entity_resolution_records
       WHERE org_id = p_org_id AND lower(integration) = v_vendor;
    END IF;
  END IF;

  IF NOT p_dry_run THEN
    IF n_sources > 0 THEN
      -- Cascades to rag_documents, rag_chunks, rag_embeddings, rag_ingest_jobs.
      DELETE FROM public.rag_sources WHERE id = ANY (v_source_ids);
    END IF;
    IF n_refs > 0 THEN
      DELETE FROM public.agent_knowledge_references
       WHERE org_id = p_org_id AND connector_id = p_connector_id
         AND created_at <= p_disconnected_at;
    END IF;
    IF n_jobs > 0 THEN
      UPDATE public.knowledge_sync_jobs
         SET status = 'skipped', completed_at = now(),
             error_message = 'source disconnected'
       WHERE org_id = p_org_id AND connector_id = p_connector_id
         AND status IN ('queued', 'running') AND created_at <= p_disconnected_at;
    END IF;
    IF NOT v_vendor_shared THEN
      IF n_bindings > 0 THEN
        DELETE FROM public.org_business_entity_bindings
         WHERE org_id = p_org_id AND lower(system) = v_vendor;
        DELETE FROM public.org_business_entities e
         WHERE e.id = ANY (v_entity_ids)
           AND NOT EXISTS (SELECT 1 FROM public.org_business_entity_bindings b WHERE b.entity_id = e.id);
      END IF;
      IF n_aliases > 0 THEN
        DELETE FROM public.org_entity_resolution_records
         WHERE org_id = p_org_id AND lower(integration) = v_vendor;
      END IF;
      -- Open merge proposals about that vendor's records (table added by 20261012030000).
      IF to_regclass('public.org_entity_merge_proposals') IS NOT NULL THEN
        DELETE FROM public.org_entity_merge_proposals
         WHERE org_id = p_org_id AND lower(system) = v_vendor AND status = 'proposed';
      END IF;
    END IF;
  END IF;

  v_counts := jsonb_build_object(
    'rag_sources', n_sources,
    'rag_documents', n_documents,
    'rag_chunks', n_chunks,
    'agent_knowledge_references', n_refs,
    'knowledge_sync_jobs_skipped', n_jobs,
    'entity_bindings', n_bindings,
    'entity_aliases', n_aliases,
    'entities', n_entities,
    'vendor_shared', v_vendor_shared
  );

  INSERT INTO public.source_purge_receipts
    (org_id, connector_id, vendor, disconnected_at, dry_run, event_id, counts)
  VALUES (p_org_id, p_connector_id, v_vendor, p_disconnected_at, p_dry_run, p_event_id, v_counts)
  ON CONFLICT ON CONSTRAINT source_purge_receipts_once DO NOTHING;

  RETURN v_counts;
END;
$$;

REVOKE ALL ON FUNCTION public.purge_connector_derived_data(uuid, uuid, text, timestamptz, boolean, uuid)
  FROM PUBLIC, anon, authenticated;
GRANT EXECUTE ON FUNCTION public.purge_connector_derived_data(uuid, uuid, text, timestamptz, boolean, uuid)
  TO service_role;
