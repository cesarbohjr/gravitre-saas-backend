# Historical projection reconciliation — operator contract

**Implemented candidate; not installed or executed in a hosted database.** This
implements the repair/undo mechanism required by the existing ECO-014 / DEC-007 /
DEC-019 protocol. It does not authorize a backfill or close those findings.

Apply/undo are SECURITY INVOKER and require the existing table privileges for
row locking and projection refresh; installation does not broaden access to
canonical/projection/definition tables.

The staged migration is
`supabase/migrations/20261117060000_guarded_historical_projection_reconciliation.sql`.
It depends on the existing parameter/outcome/projection migrations and canonical
run-status v2 schema. Installation creates service-only functions and an empty
RLS-protected journal. It changes no historical run or projection.

## Scope and prerequisites

Use the existing controlled SQL operator channel. Attest the actual project,
source SHA, deployed schema, consumer compatibility and named operator before
execution. Production migration and data repair require their existing explicit
owner approvals. A supplied `p_approval_ref` is an audit reference, **not evidence
that approval exists**.

Freeze a reviewed per-org run-ID allowlist. Each call names exactly one org/run;
there is no implicit all-tenant or all-history mode. Supported rows are known
terminal **execute** workflow runs with existing same-tenant run projections and
identical source/target step-ID sets. Both step-parent foreign keys must be
validated and immediate. Missing projections/steps, unknown states, different run
families, tenant conflicts and projection-only domains require separate review.
The last recorded QA inventory of 15 metadata gaps and 27 projection-only rows is
historical evidence; re-inventory before preparing an approved hosted batch.

## Preview and review

Read-only preview works in a read-only transaction. The psql variables below are
supplied from the attested, approved operator context; they are not default IDs.

```sql
BEGIN READ ONLY;
SELECT public.reconcile_historical_run_projection(
  :'org_id'::uuid, :'run_id'::uuid
);
COMMIT;
```

Output includes scoped identity, current/proposed status, proposed contract
version, step count and SHA-256 source/projection fingerprints. It does not export
full source parameters or the undo checkpoint. Fingerprints normalize timestamps
to UTC and include canonical steps and the workflow display-name dependency.
Review the proposed effects against the existing consumer inventory and retain
the exact returned fingerprints with the approved allowlist and batch UUID.

## Apply one approved row

```sql
BEGIN;
SET LOCAL lock_timeout = '5s';
SET LOCAL statement_timeout = '30s';
SELECT public.reconcile_historical_run_projection(
  p_org_id => :'org_id'::uuid,
  p_run_id => :'run_id'::uuid,
  p_batch_id => :'batch_id'::uuid,
  p_source_digest => :'reviewed_source_digest',
  p_projection_digest => :'reviewed_projection_digest',
  p_approval_ref => :'apply_approval_reference',
  p_mode => 'apply'
);
COMMIT;
```

The function locks the canonical parent and existing source steps, the display-name
rows, then the target parent and target steps. Parent foreign keys fence new child
inserts while those parent locks are held. After locking, it rechecks reviewed
fingerprints and uses the existing locked-source projection refresh. The same
transaction stores an undo checkpoint and before/after digests in the journal.
Canonical run/step rows and their existing terminal event are not changed. It
creates no source terminal transition, notification, learning effect or new
projection-domain row. Other projection domains are untouched.

A stale review fails with SQLSTATE `40001`; unsupported scope/identity/schema also
fails. Stop and re-preview/re-review rather than retrying with stale fingerprints.
An identical apply with the same batch/ref/digests returns the prior journal ID
without another refresh or journal row. A batch that has been undone cannot be
applied again. Save the returned **after** projection digest for a possible undo.

## Undo a reviewed checkpoint

Use the same explicit function with `p_mode => 'undo'`, original source digest,
the apply result's after-projection digest, matching scope/batch and the appropriate
undo approval reference. It requires current source and target to match that
checkpoint, then restores only projection fields and marks the journal undone in
one transaction. Source history and terminal events remain untouched. Any later
source, step, workflow-name or consumer/projection change blocks undo; never force
an overwrite. Repeating an already completed undo is readback-only when the exact
restored checkpoint still matches. Neither apply nor undo deletes data.

## Evidence and rollback boundary

After any authorized hosted repair, independently verify run/step parity, retained
consumer metadata, unchanged canonical source/event identities, UI status,
metrics and event-consumer behavior. Keep source/deploy identities and per-row
PASS/FAIL evidence. Disposable PostgreSQL tests do not prove hosted consumer/UI
acceptance. New/missing projection creation and old unkeyed external effects are
outside this mechanism.

The journal contains prior projection JSON, which can contain private business
evidence. It is service-only and RLS-protected; keep snapshots in the approved
operator evidence store, with the existing approved retention/access rules. Do
not export them into public PR text or logs. No automatic cleanup or bulk restore
is enabled. Preserve the additive journal/functions while an approved repair or
undo is outstanding; removing an application release does not itself undo data.
