# Outcome estimate labeling (STA-286)

## Decision

Until the ground-truth measurement path in [STA-289](https://linear.app/staqbot/issue/STA-289) ships, **hours-saved**, **ROI**, and **optimization impact** figures are **estimates** — not measured time-on-task or controlled before/after studies.

**Operational counts** (tasks completed, success rate from runs/jobs) are **measured telemetry** from Gravitre execution records. They count events in the product; they do **not** prove business outcome or hours saved.

## Taxonomy

| Kind | Examples | UI label | Source |
|------|----------|----------|--------|
| **Estimate** | Catalog hours saved, adopted hours, agent ROI hours/labor/multiple, Meson/optimization impact | `Estimate` badge or "Estimated …" in copy | Publisher metadata, catalog math, task-type heuristics |
| **Operational** | Workforce tasks completed/failed, lite results counts, workflow success rate, agent ROI task/action counts | `Operational` badge or "(operational)" in label | `agent_jobs`, `workflow_runs`, audit/tool events |
| **Measured** | Agent COGS (`model_calls.cost_usd`), revenue influenced when outcome metadata has a real monetary amount | `Measured` badge | Billing/COGS tables; verified connector outcome fields |
| **Deferred** | Time-on-task ground truth, before/after pilot ROI | Not shown as live | STA-289 roadmap |

## Implementation

- Shared constants: `apps/web/lib/outcome-labels.ts`
- Marketplace re-exports: `apps/web/lib/marketplace-outcome-labels.ts`
- UI callout: `apps/web/components/outcome/outcome-methodology-callout.tsx`
- Badge: `apps/web/components/outcome/metric-provenance-badge.tsx`

## Surfaces

| Surface | Labeling |
|---------|----------|
| Marketplace ROI (`/marketplace/analytics/roi`) | Estimate methodology in page header; catalog vs adopted hours |
| Marketplace asset detail / org admin | `Est. hours saved / month` |
| Intelligence reports ROI tab (`/intelligence/reports`) | Live `GET /api/enterprise/agent-roi`; Measured / Operational / Estimate badges |
| Enterprise Agent ROI tab (`/settings/enterprise?tab=roi`) | Same agent ROI panel (org-wide + per agent) |
| Enterprise workforce tab | Operational KPI labels + methodology callout |
| Lite results | Operational callout on stats grid |
| Agent profile stats | Operational callout (config fallbacks when telemetry sparse) |
| Optimization / suggested actions | `Estimated impact` prefix |

## Copy rules

1. Never present catalog hours saved as "measured" or "proven" savings.
2. Prefix heuristic optimization strings with **Estimated impact**.
3. Distinguish operational task counts from business outcome hours.
4. Do not use fake trend sparklines without an illustrative disclaimer (workforce tab).

## Related

- [STA-286](https://linear.app/staqbot/issue/STA-286) — estimate labeling (this doc)
- [STA-289](https://linear.app/staqbot/issue/STA-289) — future ground-truth measurement
