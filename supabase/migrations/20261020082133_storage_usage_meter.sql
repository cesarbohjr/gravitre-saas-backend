-- Part 7 of the storage migration (see 20261020081535_storage_retention_metering.sql).

-- -----------------------------------------------------------------------------
-- 5) Storage meter
-- -----------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION public.compute_org_storage_usage(p_org_id uuid DEFAULT NULL)
RETURNS TABLE (org_id uuid, category text, source text, bytes bigint, row_count bigint)
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public, pg_temp
AS $$
DECLARE
  r record;
  v_size bigint;
BEGIN
  FOR r IN
    SELECT v.category, v.tbl
      FROM (VALUES
        ('knowledge', 'rag_sources'),
        ('knowledge', 'rag_documents'),
        ('knowledge', 'rag_chunks'),
        ('knowledge', 'rag_embeddings'),
        ('memories', 'agent_memories'),
        ('memories', 'agent_memory_history'),
        ('memories', 'org_memory_entity_embeddings'),
        ('conversations', 'conversations'),
        ('conversations', 'conversation_messages'),
        ('audit', 'audit_logs'),
        ('audit', 'audit_events')
      ) AS v(category, tbl)
  LOOP
    IF to_regclass(format('public.%I', r.tbl)) IS NULL THEN
      CONTINUE;
    END IF;
    IF NOT EXISTS (
      SELECT 1 FROM information_schema.columns c
       WHERE c.table_schema = 'public' AND c.table_name = r.tbl AND c.column_name = 'org_id'
    ) THEN
      CONTINUE;
    END IF;
    v_size := pg_total_relation_size(format('public.%I', r.tbl)::regclass);
    RETURN QUERY EXECUTE format(
      'WITH c AS (SELECT t.org_id AS o, count(*)::bigint AS n FROM public.%I t GROUP BY t.org_id),
            s AS (SELECT coalesce(sum(c.n), 0)::numeric AS total FROM c)
       SELECT c.o, %L::text, %L::text,
              CASE WHEN s.total > 0 THEN round($1::numeric * c.n / s.total)::bigint ELSE 0::bigint END,
              c.n
         FROM c CROSS JOIN s
        WHERE c.o IS NOT NULL AND ($2::uuid IS NULL OR c.o = $2)',
      r.tbl, r.category, r.tbl
    ) USING v_size, p_org_id;
  END LOOP;

  IF to_regclass('storage.objects') IS NOT NULL THEN
    RETURN QUERY EXECUTE
      $q$
      SELECT o.id,
             CASE WHEN so.bucket_id = 'audit-archive' THEN 'audit' ELSE 'files' END,
             'storage.objects:' || so.bucket_id,
             coalesce(sum(CASE WHEN (so.metadata->>'size') ~ '^[0-9]+$'
                               THEN (so.metadata->>'size')::bigint ELSE 0 END), 0)::bigint,
             count(*)::bigint
        FROM storage.objects so
        JOIN public.organizations o ON o.id::text = split_part(so.name, '/', 1)
       WHERE ($1::uuid IS NULL OR o.id = $1)
       GROUP BY o.id, so.bucket_id
      $q$
    USING p_org_id;
  END IF;
END;
$$;

REVOKE ALL ON FUNCTION public.compute_org_storage_usage(uuid) FROM PUBLIC, anon, authenticated;
GRANT EXECUTE ON FUNCTION public.compute_org_storage_usage(uuid) TO service_role;

COMMENT ON FUNCTION public.compute_org_storage_usage(uuid) IS
  'Approximate bytes per org and category: table size (incl. TOAST and indexes) split by org row share; files exact from storage.objects.';
