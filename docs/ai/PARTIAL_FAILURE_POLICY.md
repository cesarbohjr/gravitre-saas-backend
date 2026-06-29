# Partial-failure policy (STA-287)

**Status:** Decision recorded — code in `partial_failure_policy.py`  
**Date:** 2026-06-21  
**Distinct from:** STA-107 HubSpot/Zendesk compensating transactions

## Product decision

Gravitre uses **context-specific** failure policies — not a single global rollback mode.

| Context | Policy | Run / response status | Rationale |
|---------|--------|----------------------|-----------|
| Workflow graph (parallel branches) | **Fail-fast** | `failed` | Branch isolation; no silent partial graph success |
| Workflow graph (sequential batch) | **Fail-fast** | `failed` | Downstream steps assume prior outputs |
| Autonomous CRM/ticket writes | **Compensate** | `failed` + compensation records | STA-107 undo where vendor API allows |
| Department pack install | **Partial success** | `completed` + `failures[]` | Install what we can; surface blockers |
| Marketplace bulk asset install | **Partial success** | `completed` + `failures[]` | Same as dept packs |
| Digital twin / dry-run | **Fail-fast** | `failed` | No side effects to compensate |
| HRIS / financial writes | **Fail-fast** | `failed` | Compensation not safe; operator must reconcile |

**Not chosen:** Universal two-phase commit across SaaS APIs (infeasible at connector layer).

## Compensation vs partial success

- **Compensate:** Side effects already committed; system **attempts reversal** (best-effort, audited). Used when forward writes succeeded before a later step failed.
- **Partial success:** Independent sub-items (pack seeds); failures collected without rolling back successful sibling installs.
- **Rollback:** Reserved for future **single-vendor transactional** APIs only — not used in v1.

## Code references

| Component | Behavior |
|-----------|----------|
| `execution_engine_runtime._run_graph_batches` | Returns `failed` on first branch failure |
| `compensation_service.py` | Reverse-order CRM undo on autonomous failure |
| `marketplace/service.py` | `failures` list on department pack install |
| `partial_failure_policy.py` | `resolve_failure_policy(context)`, `resolve_run_status()` |

## Run status: `partial_success`

Added to `workflows/constants.py` for bulk installs and future graph policies. UI should show:

- Green/yellow badge when `status=partial_success`  
- Expand `failures[]` with item + error  
- Never label partial install as full success without disclosure

## Webhook / notify

Partial failure in autonomous runs triggers optional compensation webhook (STA-107). Partial marketplace install does **not** auto-compensate — operator retries failed items.

## Verification

```bash
pytest backend/tests/test_partial_failure_policy.py -q
```
