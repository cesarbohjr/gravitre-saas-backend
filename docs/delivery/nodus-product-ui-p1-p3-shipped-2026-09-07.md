# Nodus product UI — P1–P3 shipped (2026-09-07)

**Status:** Shipped to `main` (await Vercel Ready + authenticated `/home` visual check)  
**Gate:** `docs/delivery/nodus-product-ui-reconstruction-gate-audit-2026-09-07.md` — Cesar approved 2026-09-07

## What landed

| Phase | Change |
|-------|--------|
| **P1** | Product tokens in `apps/web/app/globals.css` (`--g-brand*`, `--np-sidebar*`, pad/radius/shadow/KPI gap). Fidelity baseline: this note + Gate § Product Image. |
| **P2** | Sidebar widths via `--np-sidebar` / `--np-sidebar-rail`; nav defaults **expanded** (Nodus labeled rail). |
| **P3** | `/home` Dashboard: `GravitreMetric` / `GravitreSurface`; KPI = active agents, task success %, avg execution, active workflows; Workflow monitor; Agents-by-status / runs bars from live APIs. Honest `—` when empty. |

## Data mapping (no invented metrics)

| Nodus PNG label | Gravitre source |
|-----------------|-----------------|
| Active agents | `agentsApi.list()` active/processing/running |
| Task success | `successful_runs / total_runs` from `metricsApi.overview()` |
| Avg execution | `avg_run_duration_ms` |
| Most used model | omitted (no real field) |
| Workflow monitor | Approvals + AI/ML/memory status rows |
| Agents by status | Agent status counts when list non-empty |
| Tasks / 7d bars | `runs_by_day` when present; else learning query/workflow targets |

## Scaffold honesty

**(a)** Explicitly authorized by Gate approval in this conversation. No new prices, claims, badges, or Enable toggles.

## Evidence bar

- Local: code + types for metrics/agents props.
- Production visual PASS: requires Vercel Ready + signed-in `/home` screenshot vs `dashboard@3x.png` (3312×1860). **Not claimed PASS until that check.**
