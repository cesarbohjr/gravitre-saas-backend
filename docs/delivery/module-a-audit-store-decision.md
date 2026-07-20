# STA-274 audit store decision (Module A closure)

**Date:** 2026-07-19  
**Decision:** Keep **both** tables. Do not retire either.

| Store | Role | Readers |
|-------|------|---------|
| `audit_logs` | Customer-facing canonical audit (UI, export, `/api/audit`) | Web app, compliance export |
| `audit_events` | Metrics / tool-invoke / rollup stream | Internal metrics, SIEM timing |

**Sole writer:** `write_audit_event()` in `backend/app/workflows/audit.py` dual-writes both (with gap logging). Module A terminal outcomes call this only via `emit_execute_*` inside `finalize_execution_outcome()`.

**Not chosen:** collapsing to a single table — would break existing metrics queries and customer export contracts. Unification of *reads* can happen later; unification of *writers* is already done.
