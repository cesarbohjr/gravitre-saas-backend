# Persisted outcomes, outbox delivery and crash recovery

This is a bounded repair/evidence record under the existing 43-finding register,
not a new roadmap or release certificate. Original IDs, owners, order and
closure gates remain authoritative. No workflow, migration, provider call,
runtime flag or deployment is added by this batch.

## Confirmed defects and resulting behavior

- `execution_outcome._persist_run` wrote a terminal status before verification
  metadata, then marked notification delivery/finalization before those channels
  ran. A crash or channel failure could suppress remaining delivery. Output and
  rollup proof now persist before the terminal/outbox boundary. Core run, audit,
  notification and learning acknowledgements are checkpointed after success.
  A fresh finalizer resumes only core channels lacking durable acknowledgements.
- A late caller could return success over an already persisted cancellation or
  failure. Conflicting definite terminals now retain the persisted status.
  Promoting an uncertain outcome to success requires attributable verification.
- Execution-edge telemetry could throw before consumer dispatch or after its
  effect committed, blocking delivery or scheduling a duplicate retry. The three
  telemetry boundaries now return false when the log sink is unavailable.
- Stale-run classification treated a missing/retired invoke-tool action as safe
  to retry. Such steps now require review/reconciliation. Known reads retain the
  existing bounded recovery behavior; no provider work is re-executed here.

Audit acknowledgement means canonical `audit_logs` storage. Dual-write attempts to
`audit_events` remain in place, and gaps retain their existing diagnostics. Optional
SIEM scheduling failure no longer invalidates a committed canonical audit. Notification
acknowledgements require the returned inbox-row ID; learning requires returned insert
rows. Positive test collaborators now return these actual success shapes; missing
acknowledgements are covered explicitly.

## Evidence

- **114 primary focused local checks pass**, covering finalization/effect gates, retry
  receipts, lifecycle fallback contracts, relay, telemetry and stale recovery.
  The lean local runs use `--confcutdir=tests/services` and explicit dummy test
  settings; they do not certify the repository's complete global test fixtures.
- **20 selected regressions fail on pre-repair source**: 12 receipt/terminal-proof,
  six telemetry/consumer and two unknown-action recovery cases.
- Existing PostgreSQL acceptance files now include **five new executable cases**:
  three partial-channel retries with independently queried SQL receipts, an
  actual finalizer subprocess exit after audit acknowledgement followed by
  restart, and a real SQL consumer commit followed by telemetry failure.
  The receipt fixture also installs a database trigger rejecting a terminal
  transition before output persistence. Production repository/mirror/outbox
  code remains real; external channels use explicitly synthetic SQL stand-ins.
- Local PostgreSQL execution is **NOT RUN**: process startup cannot bind its
  Unix socket in this runtime. The existing canonical QA acceptance lane already
  selects both modified PostgreSQL files and requires server availability.

Neighboring workflow recovery/audit-redaction checks also pass (15 cases); the
existing action-lifecycle and outcome-ownership suites pass separately (77 cases).
The combined focused local total is **206 passing cases**.

## Scope and remaining gates

Versioned receipts are restart checkpoints, not concurrent exactly-once claims.
The existing repository parameter merge remains read-modify-write. Consumers
still need idempotency for a crash between a committed effect and its receipt;
concurrent finalization needs a separate fenced/atomic claim. Optional fanout
remains best effort. Historical skip markers retain compatibility but are no
longer reported as proof that audit/learning channels succeeded. Legacy rows
are not silently backfilled or redelivered by this repair.

ECO-010/ECO-014, P27-03 and DEC-006/007/019 receive bounded persistence/delivery
repairs; P27-05/P27-08 receive bounded recovery repairs. Exact-head CI, real
provider/consumer readback, cross-surface concurrency and cancellation, deployed
rollback and owner approval remain open. No finding is closed by this record.
