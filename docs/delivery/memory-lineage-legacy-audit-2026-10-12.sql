-- Memory lineage: legacy (untagged) connector-derived memories. READ-ONLY.
-- Run in the Supabase SQL editor for smyeexlrqdpymwjmgzqu. Nothing here writes.
--
-- Why: purge_connector_memories (20261012070000) removes only rows whose
-- source_connector_id names the disconnected connector. Rows written before
-- MEMORY_SOURCE_LINEAGE_ENABLED was turned on carry no connector id, so no
-- disconnect can ever remove them. This query sizes that set.
--
-- Decision (2026-10-12): legacy rows are NOT guessed onto a connector. A row
-- cannot be attributed from its text, and a wrong tag would purge the wrong data
-- or keep the right data. Instead, before customer ingestion is enabled:
--   1. run this audit and record the counts in the release report;
--   2. the owner decides, per group below, to retire them (is_active=false and
--      is_current=false, a reviewed one-off statement run by the owner) or to
--      accept them as user-confirmed action history;
--   3. MEMORY_SOURCE_LINEAGE_ENABLED=true from then on, so every new connector
--      memory is tagged, and an untagged connector memory is not written at all.

-- 1) Lineage columns present? (expect 2 once 20261012070000 is applied)
SELECT count(*) AS lineage_columns
  FROM information_schema.columns
 WHERE table_schema = 'public' AND table_name = 'agent_memories'
   AND column_name IN ('source_connector_id', 'source_record_ref');

-- 2) Untagged memories that came from connector actions or external content,
--    grouped so the owner can decide per group. Works before and after the
--    migration (the lineage filter is applied in step 3).
SELECT
  CASE
    WHEN m.provenance LIKE 'connector_confirm%' THEN 'connector_confirm (confirmed connector action)'
    WHEN m.source_class = 'untrusted_external' THEN 'untrusted_external (connector/document content)'
    WHEN m.provenance LIKE 'learn_outcome:%' THEN 'learn_outcome (turn outcome status)'
    ELSE 'other'
  END AS legacy_group,
  m.is_active,
  count(*) AS rows,
  count(DISTINCT m.org_id) AS orgs,
  min(m.created_at) AS oldest,
  max(m.created_at) AS newest
  FROM public.agent_memories m
 WHERE m.provenance LIKE 'connector_confirm%'
    OR m.source_class = 'untrusted_external'
    OR m.provenance LIKE 'learn_outcome:%'
 GROUP BY 1, 2
 ORDER BY 1, 2;

-- 3) After 20261012070000 only: of the rows above, how many are still untagged.
--    (Fails with "column does not exist" before the migration; skip it then.)
-- SELECT count(*) FILTER (WHERE source_connector_id IS NULL) AS untagged,
--        count(*) FILTER (WHERE source_connector_id IS NOT NULL) AS tagged
--   FROM public.agent_memories
--  WHERE provenance LIKE 'connector_confirm%' OR source_class = 'untrusted_external';
