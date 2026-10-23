# Supabase migration replay recovery

Independent of BE21 application changes. PR #544 is already merged; this PR repairs
migration reliability and establishes separate database acceptance evidence.

## Verified failure and recovery

- Production has 290 recorded migrations. Replaying the original statements on a
  fresh Supabase PostgreSQL database fails at version `20250220000006`, statement
  20, SQLSTATE `42P13`: the claim function changes its OUT-row type without first
  dropping the old zero-argument signature.
- Further isolated replay exposed earlier references to billing, notifications,
  process inventory and knowledge-source tables, an absent test-org fixture, and
  an index whose `runs.triggered_by` column was introduced out of band.
- The corrected full 290-record replay passes on real Supabase PostgreSQL in CI:
  https://github.com/cesarbohjr/gravitre-saas-backend/actions/runs/39812035270
- Schema replay alone is insufficient. Production also contains 17 additional
  columns, 13 additional application functions, 12 public triggers, changed RLS
  policies and grants, and other schema drift. The recovery reconstructs these
  in a disposable database from read-only catalog snapshots, not customer rows.

## Implementation

`Migration history recovery` runs the scripts in `scripts/migration_recovery/`:

1. Export complete original migration statement arrays and application schema
   metadata through read-only API requests.
2. Reproduce the exact historical failure, then replay the corrected candidate.
3. Restore the original metadata backup in an isolated schema and compare every
   SQL array and metadata field.
4. Reconcile the isolated database and strictly compare application schema and
   security definitions to production. The target platform retains its managed
   `supabase_admin` default privileges; postgres-owned application defaults and
   all concrete object privileges must match.
5. Produce a supported CLI schema dump, retain the application trigger on
   `auth.users`, restore into a fresh local database, and compare without repairs.
6. Run shipped confirmation/claim function bodies against independent PostgreSQL
   sessions with a durable local dispatch probe. No vendor requests are made.
7. Test the pinned CLI's atomic migration-history baseline operation locally,
   including an intentionally rejected INSERT that must roll back the preceding
   history DELETE without losing any original SQL arrays.
8. Always stop disposable compute and remove transient original SQL exports.

## Production gate

Production metadata has not been repaired by merely adding this workflow. Before
adopting the baseline: require baseline restore, schema parity, PostgreSQL
acceptance, supported-command rollback proof and current required CI to pass.
Preserve the complete off-database backup. Verify production has not changed
since the snapshot, use the supported CLI baseline operation, and verify that
only migration metadata changed. Do not replay the baseline DDL on production.

Align Git's active migration source and its audit archive with the adopted
baseline. A final data-free Supabase preview must replay it successfully and be
deleted immediately after validation. Do not describe release as complete until
those operations and required deployment checks have actual evidence.

Pinned supported procedure:
https://github.com/supabase/cli/blob/v2.121.0/apps/cli/src/commands/migration/squash/SIDE_EFFECTS.md
