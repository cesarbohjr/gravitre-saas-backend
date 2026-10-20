-- Existing-source impact audit for EXISTING_INGESTION_REQUIRES_LIFECYCLE (read-only).
--
-- Answers, per organisation: what pre-existing ingestion would stop if the owner set
-- EXISTING_INGESTION_REQUIRES_LIFECYCLE=true. Run it before deciding, against the
-- production database (or a fresh replica) with psql:
--
--   psql "$DATABASE_URL" -X -v ON_ERROR_STOP=1 -f supabase/scripts/existing_ingestion_impact_audit.sql
--
-- It runs inside a READ ONLY transaction and ends with ROLLBACK: any write is refused
-- by PostgreSQL itself. It reads connectors, rag_sources, rag_documents,
-- rag_ingest_jobs and knowledge_sync_jobs.
--
-- Two levels of impact, matching backend/app/services/ingestion_interlock.py:
--
--   *_while_not_ready   With the switch on and lifecycle NOT ready (any configuration
--                       prerequisite off, or no runtime evidence in the process doing
--                       the work), ALL of it is held: every scheduled/manual/webhook
--                       knowledge sync and every standalone-worker ingest job.
--   *_when_ready        With the switch on and lifecycle ready, only work for providers
--                       without a wired revoke call is held. That is decided on
--                       connectors.type (syncs) and rag_sources.type (ingest jobs), so
--                       uploads/URLs ('file', 'url', ...) are held too, not only
--                       Notion/Confluence/Zendesk/Workday.
--
-- Nothing already indexed is deleted by the switch; "documents" counts are what stops
-- being refreshed, not what is removed.
--
-- The provider list below must equal provider_revoke.SUPPORTED_VENDORS (a unit test
-- checks it). Google aliases that canonical_vendor() would normalise are counted as
-- held here, so the *_when_ready numbers can only over-count.

BEGIN TRANSACTION READ ONLY;

-- 1) Per organisation.
WITH revocable(vendor) AS (
  VALUES
    -- revocable-providers:begin
    ('gmail'), ('google_ads'), ('google_analytics'), ('google_calendar'), ('google_docs'),
    ('google_drive'), ('google_search_console'), ('google_sheets'), ('hubspot'),
    ('salesforce'), ('slack')
    -- revocable-providers:end
),
knowledge_vendor(vendor) AS (
  VALUES ('notion'), ('confluence'), ('hubspot'), ('zendesk'), ('workday')
),
live_connectors AS (
  SELECT c.org_id, c.id, lower(coalesce(c.type, '')) AS vendor, c.status
    FROM public.connectors c
   WHERE c.deleted_at IS NULL
     AND lower(coalesce(c.type, '')) IN (SELECT vendor FROM knowledge_vendor)
),
connector_counts AS (
  SELECT org_id,
         count(*) AS live_knowledge_connectors,
         count(*) FILTER (WHERE status = 'active') AS scheduled_syncs_held_while_not_ready,
         count(*) FILTER (WHERE vendor NOT IN (SELECT vendor FROM revocable)) AS connectors_held_when_ready,
         count(*) FILTER (WHERE status = 'active' AND vendor NOT IN (SELECT vendor FROM revocable))
           AS scheduled_syncs_held_when_ready,
         string_agg(DISTINCT vendor, ',' ORDER BY vendor)
           FILTER (WHERE vendor NOT IN (SELECT vendor FROM revocable)) AS held_vendors
    FROM live_connectors
   GROUP BY org_id
),
sources AS (
  SELECT s.org_id, s.id,
         lower(coalesce(s.type, '')) NOT IN (SELECT vendor FROM revocable) AS held_when_ready,
         lower(coalesce(s.type, '')) IN (SELECT vendor FROM knowledge_vendor) AS from_knowledge_sync
    FROM public.rag_sources s
),
source_counts AS (
  SELECT org_id,
         count(*) AS rag_sources,
         count(*) FILTER (WHERE held_when_ready) AS rag_sources_held_when_ready,
         count(*) FILTER (WHERE held_when_ready AND NOT from_knowledge_sync) AS non_connector_sources_held_when_ready
    FROM sources
   GROUP BY org_id
),
document_counts AS (
  SELECT s.org_id,
         count(d.id) AS rag_documents,
         count(d.id) FILTER (WHERE s.held_when_ready) AS rag_documents_in_sources_held_when_ready
    FROM sources s
    JOIN public.rag_documents d ON d.source_id = s.id
   GROUP BY s.org_id
),
job_counts AS (
  SELECT j.org_id,
         count(*) AS queued_ingest_jobs_held_while_not_ready,
         count(*) FILTER (WHERE s.held_when_ready IS NOT FALSE) AS queued_ingest_jobs_held_when_ready
    FROM public.rag_ingest_jobs j
    LEFT JOIN sources s ON s.id = j.source_id
   WHERE j.status = 'queued'
   GROUP BY j.org_id
),
sync_job_counts AS (
  SELECT org_id, count(*) AS open_knowledge_sync_jobs
    FROM public.knowledge_sync_jobs
   WHERE status IN ('queued', 'running')
   GROUP BY org_id
),
orgs AS (
  SELECT org_id FROM connector_counts
  UNION SELECT org_id FROM source_counts
  UNION SELECT org_id FROM job_counts
  UNION SELECT org_id FROM sync_job_counts
)
SELECT o.org_id,
       coalesce(cc.live_knowledge_connectors, 0) AS live_knowledge_connectors,
       coalesce(cc.scheduled_syncs_held_while_not_ready, 0) AS scheduled_syncs_held_while_not_ready,
       coalesce(cc.connectors_held_when_ready, 0) AS connectors_held_when_ready,
       coalesce(cc.scheduled_syncs_held_when_ready, 0) AS scheduled_syncs_held_when_ready,
       coalesce(cc.held_vendors, '') AS held_vendors,
       coalesce(sc.rag_sources, 0) AS rag_sources,
       coalesce(sc.rag_sources_held_when_ready, 0) AS rag_sources_held_when_ready,
       coalesce(sc.non_connector_sources_held_when_ready, 0) AS non_connector_sources_held_when_ready,
       coalesce(dc.rag_documents, 0) AS rag_documents,
       coalesce(dc.rag_documents_in_sources_held_when_ready, 0) AS rag_documents_in_sources_held_when_ready,
       coalesce(jc.queued_ingest_jobs_held_while_not_ready, 0) AS queued_ingest_jobs_held_while_not_ready,
       coalesce(jc.queued_ingest_jobs_held_when_ready, 0) AS queued_ingest_jobs_held_when_ready,
       coalesce(sj.open_knowledge_sync_jobs, 0) AS open_knowledge_sync_jobs
  FROM orgs o
  LEFT JOIN connector_counts cc ON cc.org_id = o.org_id
  LEFT JOIN source_counts sc ON sc.org_id = o.org_id
  LEFT JOIN document_counts dc ON dc.org_id = o.org_id
  LEFT JOIN job_counts jc ON jc.org_id = o.org_id
  LEFT JOIN sync_job_counts sj ON sj.org_id = o.org_id
 ORDER BY connectors_held_when_ready DESC, queued_ingest_jobs_held_when_ready DESC, o.org_id;

-- 2) Head-of-line check for the standalone worker. claim_rag_ingest_job takes the oldest
--    queued job across ALL orgs; a held job is released and reclaimed on the next poll,
--    so if the oldest queued job is held, no org's job behind it is processed.
WITH revocable(vendor) AS (
  VALUES
    ('gmail'), ('google_ads'), ('google_analytics'), ('google_calendar'), ('google_docs'),
    ('google_drive'), ('google_search_console'), ('google_sheets'), ('hubspot'),
    ('salesforce'), ('slack')
),
head AS (
  SELECT j.id, j.org_id, j.created_at, lower(coalesce(s.type, '')) AS source_type
    FROM public.rag_ingest_jobs j
    LEFT JOIN public.rag_sources s ON s.id = j.source_id
   WHERE j.status = 'queued'
   ORDER BY j.created_at ASC
   LIMIT 1
)
SELECT h.id AS oldest_queued_job_id,
       h.org_id AS oldest_queued_job_org_id,
       h.source_type AS oldest_queued_job_source_type,
       h.source_type NOT IN (SELECT vendor FROM revocable) AS head_of_line_blocked_when_ready,
       (SELECT count(*) FROM public.rag_ingest_jobs WHERE status = 'queued') AS queued_jobs_behind_or_at_head
  FROM head h;

ROLLBACK;
