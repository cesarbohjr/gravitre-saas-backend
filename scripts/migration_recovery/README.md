# Migration baseline recovery

All DDL in these scripts is confined to a fresh loopback PostgreSQL database.
Production access is a read-only Management API export of schema definitions and
migration metadata. Application rows, auth users, credentials and sequence current
values are never exported.

The original history reproduces PostgreSQL 42P13 at migration 20250220000006,
statement 20. `candidate.py` corrects the six historical dependency/seed failures
without altering that backup. `reconcile.py` restores the remaining production
schema drift in the isolated database. This candidate is an intermediate, not a
replacement for the final baseline restore test.

Parity covers all public table columns, constraints, RLS settings, table and
function ACLs, function definitions, policies, indexes, views, sequence definitions
and ACLs, application triggers (including auth.users), and postgres-owned default
privileges. **Supabase-managed `supabase_admin` default privileges are excluded:**
they belong to the target platform's bootstrap and cannot be changed by the
application postgres role. All concrete application object privileges still have
to match exactly; this exclusion does not loosen a table, function or policy test.
The initial attempt to alter those managed defaults correctly failed with
`permission denied to change default privileges`; no production operation occurred.

After parity, the supported CLI schema dump is restored into another empty local
database and compared without any repair steps. The shipped confirmation and
claim function bodies then run against real PostgreSQL sessions; only downstream
vendor dispatch is replaced by an isolated durable write probe. This does not
certify live provider authorization, voice cancellation, or provider readback.

The original migration backup is round-tripped through an isolated PostgreSQL
schema, preserving every original statement array and metadata field.

The pinned Supabase CLI v2.121.0 also documents a supported atomic history
baseline operation in `migration squash --linked`: its remote path wraps deletion
of prior records and insertion of the baseline's parsed SQL in BEGIN/COMMIT, with
ROLLBACK on error. It does not run the application migration SQL against the linked
database. Validate that command against a disposable database before any production
history reconciliation. A successful schema replay alone does not authorize or
prove completion of that operation.

Pinned implementation reference:
https://github.com/supabase/cli/blob/v2.121.0/apps/cli/src/commands/migration/squash/SIDE_EFFECTS.md
