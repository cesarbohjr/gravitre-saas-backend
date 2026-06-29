# Canonical schema decision (STA-272)

**Status:** Decision recorded — migration execution tracked separately  
**Date:** 2026-06-21  
**Blocks:** [STA-271](https://linear.app/staqbot/issue/STA-271) workflow consolidation only  
**Inventory:** `docs/ai/WORKFLOW_SCHEMA_DUAL_WRITE_AUDIT.md`

## Decision summary

Gravitre adopts a **contract-first canonical model** for customer-facing data, with **legacy execution tables** retained until each migration step ships. No third parallel schema will be introduced.

| Domain | Canonical (UI + API contract) | Execution / legacy (today) | Cutover owner |
|--------|--------------------------------|------------------------------|---------------|
| Workflows | `workflows`, `runs`, `run_steps` | `workflow_defs`, `workflow_runs`, `workflow_steps` | STA-271 |
| Agents | `agents` | `operators`, `operator_versions`, `operator_sessions` | Post–2A migration |
| Audit | `audit_logs` (customer export/UI) | `audit_events` (metrics/rollups) | STA-274 integrity fix first |

**Workflow engine entry (Decision 1 / STA-259):** `backend/app/workflows/execute.py` façade; `execution_engine_runtime.execute_workflow_graph` is the canonical graph runtime. Legacy linear step executor remains for unmigrated defs only.

## Workflows / runs

1. **New writes** from Next.js (`apps/web/app/api/workflows/*`) must eventually dual-write or route through FastAPI so execute never sees orphan `workflows` rows.
2. **New writes** from FastAPI (`routers/workflows.py`, marketplace install, vertical packs) must include contract mirror where feasible — pattern already in `marketplace/service.py` and `org_seed_service.py`.
3. **Reads for execution** stay on legacy until STA-271 ships a single repository façade.
4. **Backfill** remains idempotent via `supabase/migrations/legacy/20260425_backfill_contract_tables.sql`.

## Agents / operators

1. **UI and marketplace browse** use `agents`.
2. **Runtime** uses `operators` + versions; marketplace install already creates both.
3. **Target:** one write path through operator service with contract mirror — no persona duplication in new features.

## Audit logs / events

1. **Customer audit API** (`GET /api/audit`) reads **`audit_logs` only** — this is the contract.
2. **`audit_events`** remains the metrics/rollup source until reads unify; see STA-274 for integrity defects (silent contract write failure, purge scope mismatch).
3. **New audit features** must not add a third table; extend `write_audit_event()` dual-write with hard failure alerting on contract miss.

## What this ticket closes

STA-272 asked for a **canonical schema decision**, not full migration. This document is that decision. Implementation tracking:

- Workflow dual-write elimination → STA-271  
- Audit integrity → STA-274  
- Agent unification → future migration step after 2A retrieval work

## Verification

```bash
# Dual-write inventory (no drift additions)
rg "workflow_defs|workflow_runs" backend/app --glob "*.py" | wc -l

# Contract tables referenced from web
rg "from\\(\"workflows\"\\)" apps/web/app/api
```
