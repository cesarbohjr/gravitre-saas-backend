# Workflow schema dual-write audit (STA-271 Phase C)

**Status:** Inventory complete — canonical decision in `docs/platform-reconciliation/CANONICAL_SCHEMA_DECISION.md` (STA-272)  
**Date:** 2026-06-21  
**Spec:** `docs/ai/UNIVERSAL_INTELLIGENCE_LAYER_SPEC.md` L206 / Phase C  
**Contract reference:** `docs/SUPABASE_SCHEMA_CONTRACT.md` L7–18 (canonical), L63–68 (legacy)

## Summary

| Table pair | Canonical (frontend contract) | Legacy (FastAPI execution) | Drift risk |
|------------|------------------------------|----------------------------|------------|
| Workflows | `workflows` | `workflow_defs` | **High** — split create/update paths |
| Runs | `runs` | `workflow_runs` (+ `workflow_steps`) | **High** — execution writes legacy only |
| Steps | `run_steps` | `workflow_steps` | **High** — not mirrored on execute |

**Execution source of truth today:** `workflow_defs` + `workflow_runs` + `workflow_steps` (+ `workflow_nodes` / `workflow_connections` for builder graphs).

**Frontend list/detail source of truth today:** `workflows` (Next.js Supabase routes). Runs UI uses FastAPI proxy → legacy tables.

Existing one-time backfill: `supabase/migrations/legacy/20260425_backfill_contract_tables.sql` + `supabase/scripts/legacy/verify_backfill.sql` (non-destructive, idempotent).

---

## Inventory — `workflow_defs` / `workflow_runs`

### Active writes (legacy — production-critical)

| Path | File | Operation | Notes |
|------|------|-----------|-------|
| Workflow CRUD | `backend/app/workflows/repository.py` | R/W defs, runs, steps | Core execution repository |
| Builder compile | `backend/app/workflows/builder_sync.py` L360 | UPDATE `workflow_defs.definition` | After graph sync; **does not** write `workflows` |
| Builder save | `backend/app/routers/workflows.py` L583, L588 | UPDATE defs + sync graph | Primary builder API |
| Create workflow | `backend/app/routers/workflows.py` L3590 | INSERT `workflow_defs` | Admin POST — **no** `workflows` row |
| From-goal create | `backend/app/routers/workflows.py` L3459 | INSERT `workflow_defs` | **Split-write hotspot** (STA-259 evidence) |
| Execute / dry-run | `backend/app/workflows/repository.py` | INSERT/UPDATE `workflow_runs`, steps | All run lifecycle |
| Lite API | `backend/app/routers/lite.py` | INSERT/UPDATE runs + read defs | Demo/lite flows |
| Meson | `backend/app/services/meson_service.py` L412 | INSERT defs | Goal-generated workflows |
| Integration suggestions | `backend/app/services/integration_suggestion_service.py` L538, L614 | INSERT defs | Auto-provisioned flows |
| Assistant create_workflow | `backend/app/services/assistant_tools.py` L430 | INSERT defs | Tool-created flows |
| Inbound triggers | `hubspot_trigger_service.py`, `salesforce_trigger_service.py`, `segment_trigger_service.py`, `pagerduty_trigger_service.py` | READ defs, UPDATE runs | Trigger execution |
| Webhook trigger | `backend/app/routers/webhooks/workflow_triggers.py` | READ defs, UPDATE runs | |
| Interrupts | `backend/app/services/agent_interrupt_service.py` | UPDATE runs | Pause/cancel |
| ExecutionService | `backend/app/services/execution_service.py` L83 | READ run snapshot | Phase B now uses façade |
| Schedules | `backend/app/services/workflow_schedule_service.py` | READ runs | |

### Dual-write (legacy + contract — intentional today)

| Path | File | Tables |
|------|------|--------|
| Org seed | `backend/app/services/org_seed_service.py` L264–267 | `workflows`, `workflow_defs`, `runs` |
| Marketplace install | `backend/app/marketplace/service.py` L394–408 | `workflow_defs`, `workflows` |
| Marketplace sandbox | `backend/app/services/marketplace_sandbox_service.py` L201–203 | all four |
| Vertical packs | `healthcare_vertical_service.py`, `legal_vertical_service.py`, `real_estate_vertical_service.py`, `marketing_workflow_service.py`, `devops_workflow_service.py`, `marketo_workflow_service.py`, `council_workflow_service.py`, `agent_role_marketplace_service.py` | `workflow_defs` + `workflows` (same pattern as marketplace) |

### Read-only (legacy)

| Path | File | Use |
|------|------|-----|
| Metrics | `backend/app/metrics/service.py`, `routers/metrics.py` | Dashboards, rollups source |
| Search | `backend/app/routers/search.py` | Knowledge search entity index |
| Assistant tools | `backend/app/services/assistant_tools.py` | `getWorkflowRuns` tool |
| Context packs | `backend/app/operator_module/services/context_packs.py` | Operator context |
| Optimization | `backend/app/services/optimization_service.py` | Recommendations input |
| Failure predictions | `backend/app/services/workflow_failure_prediction_service.py` | Alerts |
| Policy | `backend/app/workflows/policy.py` | Concurrency guard |
| Marketplace adoption | `backend/app/marketplace/adoption.py` | Install tracking |
| User intelligence | `backend/app/services/user_intelligence.py` | Profiling |
| Org context | `backend/app/services/org_context_service.py` | Snapshot |

---

## Inventory — `workflows` / `runs`

### Active writes (contract only — drift risk)

| Path | File | Operation | Gap |
|------|------|-----------|-----|
| Workflow list create | `apps/web/app/api/workflows/route.ts` POST | INSERT `workflows` | **No** matching `workflow_defs` — invisible to FastAPI execute |
| Workflow update | `apps/web/app/api/workflows/[id]/route.ts` PUT | UPDATE `workflows` | Same |
| Recommendations apply | `apps/web/app/api/workflows/[id]/recommendations/[rec_id]/apply/route.ts` | UPDATE `workflows` | Same |

### Dual-write (see above)

Org seed, marketplace, vertical packs, sandbox.

### Read-only (contract)

| Path | File |
|------|------|
| Workflow GET/list | `apps/web/app/api/workflows/route.ts`, `[id]/route.ts` |
| Versions | `apps/web/app/api/workflows/[id]/versions/route.ts` |
| Health | `apps/web/app/api/workflows/[id]/health/route.ts` (reads `runs`) |
| Goals progress | `apps/web/app/api/goals/[id]/progress/route.ts` |
| Agent performance | `apps/web/app/api/agents/[id]/performance/route.ts` |
| Connector health | `apps/web/app/api/connectors/[id]/health/route.ts` |
| Sessions | `apps/web/app/api/sessions/route.ts` |

### `runs` writes (contract)

| Path | Notes |
|------|-------|
| `org_seed_service.py` | Demo seed only |
| `marketplace_sandbox_service.py` | Sandbox seed only |

**All production execution** writes `workflow_runs`, not `runs`. Frontend `/api/runs` proxies to FastAPI (legacy).

---

## Related tables (not in pair but coupled)

| Table | Used by | Cutover note |
|-------|---------|--------------|
| `workflow_nodes` | Builder graph, Phase B resolver | Keep until defs→workflows stores graph in `nodes`/`edges` JSON |
| `workflow_connections` | Builder edges | Same |
| `workflow_versions` | Versioning (`repository.py`) | FK to `workflow_defs` |
| `workflow_steps` | Execute logging | Map to `run_steps` on cutover |
| `workflow_runs_daily` | Metrics rollups | Repoint rollup source after migration |

---

## Drift hotspots (must fix before cutover)

1. **Next.js POST `/api/workflows`** — creates `workflows` row only; FastAPI list/execute uses `workflow_defs`.
2. **FastAPI POST `/api/workflows` + from-goal** — creates `workflow_defs` only; Next.js list reads `workflows`.
3. **Builder save (`sync_builder_graph`)** — updates `workflow_defs` + graph tables; does not sync `workflows.nodes`/`edges`.
4. **Run execution** — writes `workflow_runs`/`workflow_steps` only; `runs`/`run_steps` stale except seed/sandbox.
5. **Assistant / Meson / integration suggestion creates** — defs only.

---

## Proposed cutover plan (sign-off required)

### Gate 0 — Sign-off checklist (joint prod + migration)

- [ ] Owner confirms **canonical write target** post-cutover: `workflows` + `runs` + `run_steps` (contract)
- [ ] Owner confirms **read fallback window**: legacy tables read-only for N days after cutover
- [ ] Prod row-count parity validated (`verify_backfill.sql` or equivalent)
- [ ] Rollback plan: re-enable legacy writes only (no table drops)

### Phase C.1 — Dual-write helper (code, pre-prod)

Introduce `workflow_schema_sync.upsert_workflow_dual()` called from every **legacy-only** write path to mirror into `workflows` (marketplace pattern). Priority order:

1. `workflows.py` create / from-goal / patch
2. `builder_sync.py` after compile
3. `meson_service`, `integration_suggestion_service`, `assistant_tools.create_workflow`

### Phase C.2 — Reverse dual-write (frontend paths)

Next.js POST/PUT `/api/workflows` also upserts `workflow_defs` (or route through FastAPI create — pick one entry point in sign-off).

### Phase C.3 — Run mirror hook

On `update_run` / execute completion in `workflows/repository.py`, upsert shadow row into `runs` + `run_steps` (map status enum).

### Phase C.4 — Prod backfill

Run `20260425_backfill_contract_tables.sql` in prod (if not already); run `verify_backfill.sql`; log skipped rows from `audit_logs`.

### Phase C.5 — Read path consolidation

- FastAPI `list_workflows` / `get_workflow_def`: read `workflows` first, fallback `workflow_defs`
- Next.js: already on `workflows`

### Phase C.6 — Deprecation (post-stabilization)

- Stop writing legacy tables (feature flag `WORKFLOW_LEGACY_WRITES=false`)
- Keep legacy read fallback 30 days
- Drop legacy tables only after explicit schema migration ticket (out of scope here)

---

## Customer impact (for sign-off)

| Phase | User-visible risk |
|-------|-------------------|
| C.1 dual-write | None if ids match |
| C.2 frontend sync | Workflows created in UI become executable without manual backfill |
| C.3 run mirror | Runs page / health widgets show same data as operator execute view |
| C.4 backfill | Historical workflows appear in UI list |
| C.5 read consolidation | Brief inconsistency if backfill incomplete — mitigate with parity check |
| C.6 legacy off | Broken if any hidden legacy-only writer remains — blocked by inventory above |

---

## References

- Decision 1 / execute façade: `backend/app/workflows/execute.py`
- Phase B resolver: `backend/app/workflows/definition_resolver.py`
- Backfill SQL: `supabase/migrations/legacy/20260425_backfill_contract_tables.sql`
- Verify SQL: `supabase/scripts/legacy/verify_backfill.sql`
- Linear: [STA-271](https://linear.app/staqbot/issue/STA-271)
