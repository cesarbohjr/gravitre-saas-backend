# Supabase migration replay reliability — isolated recovery

## Scope
This work is independent of BE21 / PR #544. No production DDL, migration-history mutation, data copy, or paid Supabase branch is authorized by this PR.

## Evidence
Two clean Supabase preview branches failed migration replay after approximately 18–19 migrations; both were deleted. Production migration version `20250220000006_phase7_multi_environment` contains 20 stored statements and omits `DROP FUNCTION IF EXISTS public.claim_rag_ingest_job();` before replacing that function with a changed RETURNS TABLE signature. The GitHub migration already contains the DROP. This is a **candidate failure**, not a confirmed Postgres error; the deleted branch's logs are unavailable.

Original production history checksums (MD5 of array_to_string(statements, newline)):
- 20250220000005: 4210947ecc2025dc59d6b99641c0b785 (1 statement)
- 20250220000006: 1739e74b43d228c6395ee1dc3f907327 (20 statements)
- 20250220000007: 7ce83e88db59afe16dc0a6b4bf3095a3 (4 statements)

## Mandatory gates before any production history correction
1. Export **complete original SQL statement arrays** and metadata for all migration versions into a restricted, off-database, restorable backup. Do not commit customer data or confidential SQL into a public repository. Capture a checksum and test restoring the backup to an isolated local database.
2. Use the installed Supabase CLI and local Docker stack to fetch remote migration history, compare it against GitHub, and reproduce migration replay from a clean database. Capture the **exact failing SQL and PostgreSQL error**; do not assume version 20250220000006 is the sole blocker.
3. Inventory production schema, extensions, RLS policies, grants, triggers, functions, and relevant auth/storage dependencies. Generate a candidate baseline using documented Supabase `db pull`/migration workflow; preserve audit history. Do not blindly rename or delete historical migrations.
4. Confirm with Supabase documentation/support the exact supported reconciliation method for the **stored SQL statements** used by API/Dashboard branch creation. `supabase migration repair --status applied` updates tracking, not stored SQL; do not treat it as a statement rewrite. Never directly UPDATE `supabase_migrations.schema_migrations` without a separately reviewed, vendor-confirmed procedure and tested rollback.
5. Validate local clean replay and schema/security parity, including RLS tenant isolation, grants, function signatures and dependent objects. Record evidence and rollback drill.
6. Only after all preceding gates pass, obtain fresh hourly-cost approval and create **one data-free, nonpersistent** Supabase validation branch. Confirm complete replay, run BE21 acceptance tests separately, and delete the branch immediately, verifying it is absent.
7. Do not merge/deploy this PR or BE21 until CI, security review, migration replay and production change gates pass.

## Rollback
Before any authorized history modification, retain original statements for each affected version and a tested restoration script. Verify exact versions, statement counts and checksums before/after. If verification fails, stop and restore the saved original metadata using the reviewed procedure. A hash alone is **not** a backup.

## References
- https://supabase.com/docs/guides/troubleshooting/branch-in-migrations-failed-status
- https://supabase.com/docs/guides/troubleshooting/new-branch-doesnt-copy-database
- https://supabase.com/docs/guides/deployment/branching/troubleshooting
