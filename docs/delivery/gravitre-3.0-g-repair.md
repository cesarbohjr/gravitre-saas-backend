# Gravitre 3.0-G — classed F2 repair + in-task error memory (2026-09-20)

**Status:** Source **UNIT_TEST**. Bounded F2 budgets unchanged. LIVE repair traces **NOT RUN**.

## What shipped

| Piece | Behavior |
|-------|----------|
| Error memory | action, args, resource, reason, error_class on `RepairBudget` |
| Secrets | stripped (`api_key` / tokens not stored) |
| Scope | in-task only — not a durable learning store |
| WRITE | not repaired / not speculative |
| Audit | `f2.read.repair` on accepted repair (`provider_write: false`) |
| Probe | `scripts/verify-f2-repair-live.py` |

## Gate

- UNIT_TEST: `test_in_task_error_memory_strips_secrets`, `test_emit_f2_repair_audit_writes_without_secrets`
- LIVE repair traces: **NOT RUN** — conv `93a17de2-4497-4b04-8733-9541256eb6ab` @ `2026-09-20T06:23:41Z` SHA `28c4591e` (HTTP 200, no `f2.read.repair` row)
