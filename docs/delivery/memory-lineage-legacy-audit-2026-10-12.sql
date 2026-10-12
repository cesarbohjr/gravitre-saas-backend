-- Memory lineage: legacy (untagged) memories and observations. READ-ONLY.
-- Run in the Supabase SQL editor for smyeexlrqdpymwjmgzqu, or with psql. Nothing here
-- writes; it is safe to run inside BEGIN READ ONLY ... ROLLBACK (the Postgres test
-- tests/db/test_memory_lineage_legacy_audit_pg.py runs it exactly that way).
--
-- Why: purge_connector_memories (20261012070000) removes agent memories and customer
-- observations by the connector they name. Rows written before
-- MEMORY_SOURCE_LINEAGE_ENABLED was turned on name no connector, so a disconnect can
-- never remove them (untagged observations are removed by vendor only when no other
-- connection of that vendor is live).
--
-- Decision (2026-10-12, owner): legacy rows are neither auto-retired nor auto-accepted,
-- and never guessed onto a connector. This audit classifies them into groups; the
-- proposed handling per group is in
-- docs/delivery/memory-lineage-legacy-handling-proposal-2026-10-12.md, and the owner
-- decides each group before customer ingestion is enabled.
--
-- Works before and after 20261012070000: the groups use provenance and source_class
-- only. Query 4 needs the lineage columns and is commented out until then.

-- 1) Lineage columns present? (expect 3 once 20261012070000 is applied:
--    agent_memories.source_connector_id, agent_memories.source_record_ref,
--    entity_observations.source_connector_id)
SELECT count(*) AS lineage_columns
  FROM information_schema.columns
 WHERE table_schema = 'public'
   AND ((table_name = 'agent_memories' AND column_name IN ('source_connector_id', 'source_record_ref'))
     OR (table_name = 'entity_observations' AND column_name = 'source_connector_id'));

-- 2) Every agent memory, by legacy group. First matching rule wins; groups G1-G3 may
--    hold connector content, G4-G7 should not, G8 is unknown.
--    G1 probe              synthetic probe / smoke rows
--    G2 connector_confirm  confirmed connector actions ("Confirmed action: ...")
--    G3 external_content   untrusted_external: connector or document content
--    G4 outcome            workflow / turn outcome status (outcome_learning, learn_outcome:)
--    G5 promotion_v4       promoted org patterns (glossary, workflow, decisions)
--    G6 user_direct        user statements and user-confirmed facts
--    G7 model_inference    the model's reading of a conversation turn
--    G8 unclassified       no source_class (written before 20260903120000)
SELECT
  CASE
    WHEN coalesce(m.source_class, '') = 'probe' OR coalesce(m.provenance, '') ~* '(probe|smoke)' THEN 'G1 probe'
    WHEN m.provenance LIKE 'connector_confirm%' THEN 'G2 connector_confirm'
    WHEN m.source_class = 'untrusted_external' THEN 'G3 external_content'
    WHEN m.source_class = 'workflow_outcome'
      OR m.provenance LIKE 'learn_outcome:%' OR m.provenance LIKE 'outcome_learning%' THEN 'G4 outcome'
    WHEN m.provenance LIKE 'v4:%' THEN 'G5 promotion_v4'
    WHEN m.source_class = 'user_direct' THEN 'G6 user_direct'
    WHEN m.source_class = 'model_inference' THEN 'G7 model_inference'
    ELSE 'G8 unclassified'
  END AS legacy_group,
  count(*) AS rows,
  count(*) FILTER (WHERE m.is_active) AS active,
  count(*) FILTER (WHERE m.is_active AND m.is_current IS NOT FALSE) AS active_current,
  count(*) FILTER (WHERE m.memory_key IS NOT NULL) AS keyed,
  count(DISTINCT m.org_id) AS orgs,
  min(m.created_at) AS oldest,
  max(m.created_at) AS newest
  FROM public.agent_memories m
 GROUP BY 1
 ORDER BY 1;

-- 3) Per org, the groups that may hold connector content (G2, G3), so the owner can
--    see whose data a decision touches. Counts only, no content.
SELECT m.org_id,
       count(*) FILTER (WHERE m.provenance LIKE 'connector_confirm%') AS g2_connector_confirm,
       count(*) FILTER (WHERE m.source_class = 'untrusted_external'
                          AND m.provenance NOT LIKE 'connector_confirm%') AS g3_external_content,
       count(*) FILTER (WHERE m.is_active) AS active
  FROM public.agent_memories m
 WHERE (m.provenance LIKE 'connector_confirm%' OR m.source_class = 'untrusted_external')
   AND NOT (coalesce(m.source_class, '') = 'probe' OR coalesce(m.provenance, '') ~* '(probe|smoke)')
 GROUP BY m.org_id
 ORDER BY count(*) DESC;

-- 4) After 20261012070000 only: tagged vs untagged, per group and table.
--    (Fails with "column does not exist" before the migration; skip it then.)
-- SELECT 'agent_memories' AS tbl,
--        CASE WHEN provenance LIKE 'connector_confirm%' THEN 'G2' WHEN source_class = 'untrusted_external' THEN 'G3'
--             ELSE 'other' END AS grp,
--        count(*) FILTER (WHERE source_connector_id IS NULL) AS untagged,
--        count(*) FILTER (WHERE source_connector_id IS NOT NULL) AS tagged
--   FROM public.agent_memories GROUP BY 1, 2
-- UNION ALL
-- SELECT 'entity_observations', lower(source_system),
--        count(*) FILTER (WHERE source_connector_id IS NULL),
--        count(*) FILTER (WHERE source_connector_id IS NOT NULL)
--   FROM public.entity_observations GROUP BY 1, 2
--  ORDER BY 1, 2;

-- 5) Customer observations by source system and whether a disconnect could still
--    remove them by vendor today (no other live connector of that vendor in the org).
--    Skip if entity_observations does not exist yet.
SELECT lower(o.source_system) AS source_system,
       count(*) AS rows,
       count(DISTINCT o.org_id) AS orgs,
       count(*) FILTER (WHERE (
         SELECT count(*) FROM public.connectors c
          WHERE c.org_id = o.org_id AND c.deleted_at IS NULL
            AND lower(o.source_system) IN (lower(coalesce(c.vendor, '')), lower(coalesce(c.type, '')))
       ) > 1) AS shared_vendor_rows
  FROM public.entity_observations o
 GROUP BY 1
 ORDER BY 1;
