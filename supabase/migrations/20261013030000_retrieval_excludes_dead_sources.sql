-- Retrieval never returns content from a deleted source or a disconnected connector.
--
-- Before: DELETE /sources/{id} only set rag_sources.deleted_at, and disconnecting a
-- connector only soft-deleted the connector row. Their rag_documents stayed
-- is_active, and rag_search (and the keyword arm) checked only d.is_active, so the
-- content stayed retrievable in Chat and Voice indefinitely. The purge that removes
-- it is held off (DOMAIN_EVENT_RELAY_ENABLED=false, SOURCE_PURGE_DRY_RUN=true).
--
-- After, one invariant enforced in the database: documents of a dead source are
-- inactive.
--   * rag_sources.deleted_at set   -> that source's documents become inactive.
--   * connectors.deleted_at set    -> documents of the sources that connector created
--     at or before the disconnect become inactive (same source match as
--     purge_connector_derived_data: metadata connector_id, or a "<vendor>_rag_source_id"
--     key in the connector config).
--   * rag_search also requires s.deleted_at IS NULL (belt and braces).
-- Both happen in the same transaction as the delete, whichever code path does it.
-- Nothing is deleted; the purge still owns removal. A reconnect re-syncs and writes
-- new active versions (checksum skip only compares against active versions).
--
-- Backfill: documents that already belong to a soft-deleted source or a
-- disconnected connector are deactivated once, with counts in a NOTICE.
--
-- Preflight (read-only):
--   select count(*) from rag_documents d join rag_sources s on s.id = d.source_id
--    where d.is_active and s.deleted_at is not null;
--   select c.id, c.type, c.deleted_at, count(d.id) filter (where d.is_active) as active_docs
--     from connectors c
--     join rag_sources s on s.org_id = c.org_id and s.metadata->>'connector_id' = c.id::text
--                       and s.created_at <= c.deleted_at
--     join rag_documents d on d.source_id = s.id
--    where c.deleted_at is not null group by 1, 2, 3 order by 3 desc;
--
-- Rollback: drop the two triggers and functions, and restore rag_search from
-- 20260602130000_department_scoped_rag.sql. Deactivated documents stay inactive;
-- reactivate only by re-syncing the source (do not flip is_active by hand, it would
-- also revive superseded versions).

-- -----------------------------------------------------------------------------
-- 1) Vector search: also require a live source
-- -----------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION public.rag_search(
  p_org_id uuid,
  p_query_embedding text,
  p_top_k int,
  p_source_id uuid DEFAULT NULL,
  p_document_id uuid DEFAULT NULL,
  p_environment text DEFAULT 'default',
  p_department_id uuid DEFAULT NULL,
  p_agent_id uuid DEFAULT NULL
)
RETURNS TABLE (
  chunk_id uuid,
  content text,
  source_id uuid,
  document_id uuid,
  chunk_index int,
  score float,
  source_title text,
  document_title text
)
LANGUAGE sql
STABLE
AS $$
  SELECT
    c.id AS chunk_id,
    c.content,
    c.source_id,
    c.document_id,
    c.chunk_index,
    (1 - (e.embedding <=> (p_query_embedding::vector(1536))))::float AS score,
    s.title AS source_title,
    d.title AS document_title
  FROM public.rag_embeddings e
  JOIN public.rag_chunks c ON c.id = e.chunk_id
  JOIN public.rag_documents d ON d.id = c.document_id
  JOIN public.rag_sources s ON s.id = c.source_id
  WHERE e.org_id = p_org_id
    AND d.is_active IS TRUE
    AND s.deleted_at IS NULL
    AND e.environment = p_environment
    AND c.environment = p_environment
    AND d.environment = p_environment
    AND s.environment = p_environment
    AND (p_source_id IS NULL OR c.source_id = p_source_id)
    AND (p_document_id IS NULL OR c.document_id = p_document_id)
    AND (
      p_department_id IS NULL
      OR s.department_id IS NULL
      OR s.department_id = p_department_id
    )
    AND (
      p_agent_id IS NULL
      OR s.agent_id IS NULL
      OR s.agent_id = p_agent_id
    )
  ORDER BY e.embedding <=> (p_query_embedding::vector(1536))
  LIMIT p_top_k;
$$;

-- Older overloads still exist in production (5 and 6 arguments). Nothing in the
-- backend calls them (it always passes all 8), but they are reachable through
-- PostgREST and lacked the live-source rule. Where they exist they now delegate
-- to the 8-argument version; where they do not, nothing is created (creating them
-- would make shorter calls ambiguous).
DO $outer$
BEGIN
  IF to_regprocedure('public.rag_search(uuid,text,integer,uuid,uuid)') IS NOT NULL THEN
    EXECUTE $ddl$
CREATE OR REPLACE FUNCTION public.rag_search(
  p_org_id uuid,
  p_query_embedding text,
  p_top_k int,
  p_source_id uuid DEFAULT NULL,
  p_document_id uuid DEFAULT NULL
)
RETURNS TABLE (
  chunk_id uuid,
  content text,
  source_id uuid,
  document_id uuid,
  chunk_index int,
  score float,
  source_title text,
  document_title text
)
LANGUAGE sql
STABLE
AS $$
  SELECT * FROM public.rag_search(
    p_org_id => p_org_id, p_query_embedding => p_query_embedding, p_top_k => p_top_k,
    p_source_id => p_source_id, p_document_id => p_document_id, p_environment => 'default',
    p_department_id => NULL::uuid, p_agent_id => NULL::uuid
  );
$$;
    $ddl$;
  END IF;
  IF to_regprocedure('public.rag_search(uuid,text,integer,uuid,uuid,text)') IS NOT NULL THEN
    EXECUTE $ddl$
CREATE OR REPLACE FUNCTION public.rag_search(
  p_org_id uuid,
  p_query_embedding text,
  p_top_k int,
  p_source_id uuid DEFAULT NULL,
  p_document_id uuid DEFAULT NULL,
  p_environment text DEFAULT 'default'
)
RETURNS TABLE (
  chunk_id uuid,
  content text,
  source_id uuid,
  document_id uuid,
  chunk_index int,
  score float,
  source_title text,
  document_title text
)
LANGUAGE sql
STABLE
AS $$
  SELECT * FROM public.rag_search(
    p_org_id => p_org_id, p_query_embedding => p_query_embedding, p_top_k => p_top_k,
    p_source_id => p_source_id, p_document_id => p_document_id, p_environment => p_environment,
    p_department_id => NULL::uuid, p_agent_id => NULL::uuid
  );
$$;
    $ddl$;
  END IF;
END;
$outer$;

-- -----------------------------------------------------------------------------
-- 2) Sources a connector created at or before a point in time, and that no other
--    live connector still uses
-- -----------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION public.connector_rag_source_ids(
  p_org_id uuid,
  p_connector_id uuid,
  p_as_of timestamptz
)
RETURNS uuid[]
LANGUAGE sql
STABLE
SET search_path = public, pg_temp
AS $$
  SELECT coalesce(array_agg(s.id), '{}')
    FROM public.rag_sources s
   WHERE s.org_id = p_org_id
     AND s.created_at <= p_as_of
     AND (
       s.metadata->>'connector_id' = p_connector_id::text
       OR s.id::text IN (
         SELECT kv.value
           FROM public.connectors c, jsonb_each_text(coalesce(c.config, '{}'::jsonb)) kv
          WHERE c.id = p_connector_id AND c.org_id = p_org_id
            AND kv.key LIKE '%\_rag\_source\_id'
            AND kv.value ~* '^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$'
       )
     )
     -- A source another live connector of the org still points at is not dead.
     AND NOT EXISTS (
       SELECT 1
         FROM public.connectors lc, jsonb_each_text(coalesce(lc.config, '{}'::jsonb)) lkv
        WHERE lc.org_id = p_org_id
          AND lc.id <> p_connector_id
          AND lc.deleted_at IS NULL
          AND lkv.key LIKE '%\_rag\_source\_id'
          AND lkv.value = s.id::text
     );
$$;

-- -----------------------------------------------------------------------------
-- 3) Triggers: a dead source's documents become inactive in the same transaction
-- -----------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION public.deactivate_documents_of_deleted_source()
RETURNS trigger
LANGUAGE plpgsql
SET search_path = public, pg_temp
AS $$
BEGIN
  UPDATE public.rag_documents
     SET is_active = false
   WHERE source_id = NEW.id
     AND is_active IS TRUE;
  RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS rag_sources_deactivate_documents_on_delete ON public.rag_sources;
CREATE TRIGGER rag_sources_deactivate_documents_on_delete
  AFTER UPDATE OF deleted_at ON public.rag_sources
  FOR EACH ROW
  WHEN (OLD.deleted_at IS NULL AND NEW.deleted_at IS NOT NULL)
  EXECUTE FUNCTION public.deactivate_documents_of_deleted_source();

CREATE OR REPLACE FUNCTION public.deactivate_documents_of_disconnected_connector()
RETURNS trigger
LANGUAGE plpgsql
SET search_path = public, pg_temp
AS $$
DECLARE
  v_source_ids uuid[];
BEGIN
  v_source_ids := public.connector_rag_source_ids(NEW.org_id, NEW.id, NEW.deleted_at);
  IF coalesce(array_length(v_source_ids, 1), 0) > 0 THEN
    UPDATE public.rag_documents
       SET is_active = false
     WHERE source_id = ANY (v_source_ids)
       AND is_active IS TRUE;
  END IF;
  RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS connectors_deactivate_documents_on_disconnect ON public.connectors;
CREATE TRIGGER connectors_deactivate_documents_on_disconnect
  AFTER UPDATE OF deleted_at ON public.connectors
  FOR EACH ROW
  WHEN (OLD.deleted_at IS NULL AND NEW.deleted_at IS NOT NULL)
  EXECUTE FUNCTION public.deactivate_documents_of_disconnected_connector();

REVOKE ALL ON FUNCTION public.connector_rag_source_ids(uuid, uuid, timestamptz) FROM PUBLIC, anon, authenticated;
REVOKE ALL ON FUNCTION public.deactivate_documents_of_deleted_source() FROM PUBLIC, anon, authenticated;
REVOKE ALL ON FUNCTION public.deactivate_documents_of_disconnected_connector() FROM PUBLIC, anon, authenticated;
GRANT EXECUTE ON FUNCTION public.connector_rag_source_ids(uuid, uuid, timestamptz) TO service_role;

-- -----------------------------------------------------------------------------
-- 4) Backfill what is already dead
-- -----------------------------------------------------------------------------
DO $$
DECLARE
  n_deleted_sources integer := 0;
  n_disconnected integer := 0;
  n integer;
  c record;
BEGIN
  UPDATE public.rag_documents d
     SET is_active = false
    FROM public.rag_sources s
   WHERE s.id = d.source_id
     AND s.deleted_at IS NOT NULL
     AND d.is_active IS TRUE;
  GET DIAGNOSTICS n_deleted_sources = ROW_COUNT;

  FOR c IN SELECT id, org_id, deleted_at FROM public.connectors WHERE deleted_at IS NOT NULL LOOP
    UPDATE public.rag_documents
       SET is_active = false
     WHERE source_id = ANY (public.connector_rag_source_ids(c.org_id, c.id, c.deleted_at))
       AND is_active IS TRUE;
    GET DIAGNOSTICS n = ROW_COUNT;
    n_disconnected := n_disconnected + n;
  END LOOP;

  RAISE NOTICE 'retrieval_dead_sources_backfill deleted_source_documents=% disconnected_connector_documents=%',
    n_deleted_sources, n_disconnected;
END;
$$;
