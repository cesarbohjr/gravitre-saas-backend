-- Gravitre 3.0 Plus production migration ledger reconciliation (read-only).
-- Project: smyeexlrqdpymwjmgzqu
-- Run via: supabase db query --linked -f docs/audits/gravitre-3plus-prod-reconciliation-2026-10-12/10-final-ledger-check-readonly.sql
-- Do not paste credentials or full connection strings into tickets.

-- 1) Ledger cardinality and tail versions
SELECT count(*) AS ledger_row_count
  FROM supabase_migrations.schema_migrations;

SELECT version, name
  FROM supabase_migrations.schema_migrations
 WHERE version IN (
   '20261007090000',
   '20261012024141',
   '20261012024200',
   '20261012024300',
   '20261012030000',
   '20261012040000',
   '20261012050000',
   '20261012060000'
 )
 ORDER BY version;

-- 2) Exactly-once check for repaired historical version
SELECT version, count(*) AS n
  FROM supabase_migrations.schema_migrations
 WHERE version = '20261007090000'
 GROUP BY version;

-- 3) Pending tail (local files after last applied version) — informational
SELECT version, name
  FROM supabase_migrations.schema_migrations
 ORDER BY version DESC
 LIMIT 8;

-- 4) Preflight: 20261007090000 objects (expect present if SQL was applied OOB)
SELECT to_regclass('public.connector_action_availability') AS connector_action_availability;
SELECT indexname
  FROM pg_indexes
 WHERE schemaname = 'public'
   AND indexname IN (
     'intelligence_outcome_events_play_claim_uniq',
     'intelligence_outcome_events_play_decision_uniq'
   )
 ORDER BY 1;

-- 5) M1–M6 schema presence (expect absent until rollout completes)
SELECT to_regclass('public.source_purge_receipts') AS m1_purge_receipts;
SELECT to_regclass('public.rag_ingest_pilot_claims') AS m2_rag_pilot_claims;
SELECT to_regclass('public.entity_merge_proposals') AS m3_merge_proposals;
SELECT to_regclass('public.entity_observations') AS m4_observations;
SELECT to_regclass('public.goal_work_links') AS m5_goal_work_links;
SELECT to_regclass('public.model_prediction_outcomes') AS m6_prediction_outcomes;

-- 6) M0 outbox (applied per production ledger)
SELECT to_regclass('public.domain_event_outbox') AS m0_outbox;
