# Gravitre 3.0-G — classed F2 repair + in-task error memory (2026-09-20)

**Status:** Source **UNIT_TEST** + **LIVE_USER_PROVEN** sibling repair. Bounded F2 budgets unchanged. WRITE not invoked.

## What shipped

| Piece | Behavior |
|-------|----------|
| Error memory | action, args, resource, reason, error_class on `RepairBudget` |
| Secrets | stripped (`api_key` / tokens not stored) |
| Scope | in-task only — not a durable learning store |
| WRITE | not repaired / not speculative |
| Audit | `f2.read.repair` on accepted repair (`provider_write: false`) |
| Probe | `scripts/verify-f2-repair-live.py` |

## Frontend contract (3.0 Plus — do not redesign the panel)

On repair, `task_state` may include:

- `repair_error_memory`: in-task failed-attempt rows (no secrets)
- `repair_budget`: remaining class budgets + traces
- same `execution_plan.plan_id` as the original task

Audit: `f2.read.repair` with `provider_write: false`. Permission denials and uncertain WRITE outcomes do not mint an alternate path.

- UNIT_TEST: `test_in_task_error_memory_strips_secrets`, `test_emit_f2_repair_audit_writes_without_secrets`
- LIVE: **PASS — `f2.read.repair` @ `2026-09-20T07:24:22.216097Z`** audit `1a393ff1-c5aa-4f01-a606-a3c84f2d8901` (SHA `43570699`, conv `93a17de2-…`, `hubspot.deals.search` → `hubspot.deals.list`, `provider_write: false`)
