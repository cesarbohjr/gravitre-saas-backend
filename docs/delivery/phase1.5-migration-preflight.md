# Phase 1.5 migration preflight — knowledge_pack_cache / external_entities / external_signals

**Migration:** `supabase/migrations/20260713160000_intelligence_pack_shared_plumbing.sql`  
**Prod project:** `smyeexlrqdpymwjmgzqu`  
**Decision:** Option A (apply to prod) — conditional checks below.

## 1. Purely ADDITIVE confirmation — PASS

| Statement | Target | Existing table touched? |
|-----------|--------|-------------------------|
| `CREATE TABLE IF NOT EXISTS knowledge_pack_cache` | new | No |
| `CREATE TABLE IF NOT EXISTS external_entities` | new | No |
| `CREATE TABLE IF NOT EXISTS external_signals` | new | No |
| `CREATE INDEX IF NOT EXISTS …` | indexes on **new** tables only | No |
| `ALTER TABLE … ENABLE ROW LEVEL SECURITY` | **only** the three new tables | No |
| `DROP POLICY IF EXISTS` / `CREATE POLICY` | policies on **new** tables only | No |
| `REFERENCES organizations(id)` | FK from new tables → existing org PK | No ALTER of `organizations` |
| `REFERENCES knowledge_pack_cache(id)` / `external_entities(id)` | FKs among **new** tables | No |

**No** `ALTER TABLE` on `connectors`, `marketplace_*`, or any other pre-existing table.  
**No** `DROP TABLE`, column add/drop, or CHECK rewrite on existing objects.

→ Option A remains appropriate (not switched to C).

## 2. Enum / allowlist preflight (pipedrive-class) — PASS

Scanned migration for hardcoded `CHECK (… IN (…))`, connector_type lists, source_key allowlists, or DROP/ADD of existing constraints.

| Finding | Result |
|---------|--------|
| Connector type CHECK | **None** — `vendor` is unconstrained `text` |
| Status / source_key allowlist | **None** |
| Recreate of `connectors_type_check` / similar | **None** |
| Risk of omitting `pipedrive` (or any live connector) | **N/A** — migration does not touch connector constraints |

→ No structural miss of the Phase 1 pipedrive class.

## 3. Apply / deploy / smoke plan

1. Apply migration to prod (Option A).  
2. Open PR with Phase 1.5 code; merge only after live evidence path is ready (HTTP smoke needs tip on Railway — merge then deploy, then `scripts/smoke-phase15-shared-plumbing-http-live.py`).  
3. Mark Phase 1.5 DONE only when artifact has FRED + NVD + World Bank cache/entity/signal row IDs.

## Gate verdict

| Gate | Verdict |
|------|---------|
| Purely additive | **PASS** |
| Enum/allowlist regression | **PASS** (N/A — no allowlist) |
| Option A vs C | **Stay on A** |
