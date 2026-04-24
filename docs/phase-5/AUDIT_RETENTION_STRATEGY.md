# Audit Retention Strategy

## Risk identified
- Unbounded `audit_events` growth leads to higher storage costs and slower queries.
- Deleting audit data without guardrails can harm incident response and compliance.

## Current state
- No retention or rollup strategy implemented.
- Metrics read directly from raw `audit_events`.

## Recommended fix
- Keep 180 days of raw audit data hot.
- Roll up older data into daily aggregates and retain for 12–24 months.
- Implement guarded deletion with dry-run support and export verification.

## Implementation details
- No deletion code yet (design only).
- Rollup table shape: `org_id`, `date`, `action`, `count`, `created_at`.
- Retention guardrails:
  - Require explicit cutoff date and org scope.
  - Export snapshots before deletion.
  - Log deletion batches without payload data.

## Future scaling notes
- Partition `audit_events` by month for faster pruning.
- Move long-term aggregates to cheaper storage or a dedicated analytics store.
