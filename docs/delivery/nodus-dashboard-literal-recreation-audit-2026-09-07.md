# Gravitre Dashboard — Literal Nodus Recreation + Configurable KPI System

**Date:** 2026-09-07  
**Status:** **IMPLEMENTATION IN PROGRESS (Cesar approved 2026-09-08)** — configurable Nodus-faithful dashboard on `/home`  
**References:** `apps/web/public/nodus/dashboard@3x.png` (3312×1860), live `/home`, Gate `nodus-product-ui-reconstruction-gate-audit-2026-09-07.md`  
**Canvas:** `nodus-dashboard-literal-recreation-audit.canvas.tsx`

---

## A–C. Visual comparison (Nodus vs current Gravitre)

### Measured Nodus geometry (`dashboard@3x.png`)

| Element | @3x image px | ≈ CSS @1x | Notes |
|---------|--------------|-----------|--------|
| Frame | 3312×1860 | 2209×1241 | Soft chrome |
| Sidebar / content divider | ~302 from left | **~200–220px** rail | Matches `--np-sidebar: 220px` |
| Page title band | Top ~80–110 | Compact | “Dashboard” + search — **not** marketing H1 |
| KPI strip | 4 equal cards | `--np-kpi-gap` 12–16px | Hairline borders, soft radius |
| Workflow monitor | Mid full width | Dense table | ~3 demo rows |
| Charts row | Bottom dual | Donut + stacked bars | Equal panels |

### Current Gravitre `/home` deltas

| Issue | Evidence |
|-------|----------|
| Oversized title / welcome | `TYPE.pageTitle` = `text-2xl md:text-3xl` (24→30px); header “Welcome back, {role}” + Open Gravitre AI |
| Extra status chip strip | Approvals / confidence / learning / last cycle above KPIs — Nodus has none |
| Extra learning progress row | Two progress surfaces between KPI and monitor — not in Nodus |
| Field-name mismatches | Home reads snake (`total_runs`, `avg_run_duration_ms`); live overview is camel (`totalRuns`, `avgDuration`) → many “—” |
| Workflow monitor | Generic Item/Status/Detail — not Agent/Model/Status/Latency/Last run |
| Charts | Agents-by-status + runs bars exist but density/spacing looser than PNG |
| Static layout | Hardcoded sections; no Add KPI / drag / persist |

### Fidelity scorecard (current → target)

| Dimension | Current /10 | Target |
|-----------|-------------|--------|
| Title scale | 4 | 9 |
| Sidebar relationship | 7 | 9 |
| KPI geometry | 6 | 9 |
| KPI density | 5 | 9 |
| Table density | 5 | 9 |
| Chart style | 6 | 9 |
| Spacing / whitespace | 4 | 9 |
| Typography | 5 | 9 |
| Borders / radius | 7 | 9 |
| Color | 8 | 9 |
| **Overall structural** | **~5.5** | **≥9** |

---

## D–G. Real metrics inventory (summary)

**Full classification:** AVAILABLE NOW / DERIVABLE / REQUIRES TELEMETRY — see canvas + agent inventory.

### Already on home (intent)

| Slot | Intended | Live fix needed |
|------|----------|-----------------|
| Active agents | `agentsApi.list` status | Works |
| Task success | overview success | Remap camel `successRate`/`totalRuns` |
| Avg execution | duration | Remap `avgDuration` |
| Active workflows | count | Remap `activeWorkflows` |
| Runs chart | `runs_by_day` | Use `trends.totalRuns` or `/api/metrics/runs` |
| Approvals / trust / learning | matching APIs | Mostly OK |

### Strong AVAILABLE NOW packs (for KPI library)

- `/api/metrics/overview` + `/runs` + `/workflows` + `/rag` + `/connectors` + `/timeseries` + `/insights`
- `agentsApi.list`, `approvalsApi.list`, `workflowsApi.list` + failure predictions + outcomes ops
- GIBE: learning progress, trust, business impact, learning live, visibility, evaluations
- Billing usage (incl. voice minutes), enterprise workforce / integration health / cost
- Audit summary; voice golden-signals (admin)

### REQUIRES TELEMETRY (examples — do not fake)

- Concurrent agent CPU, inference QPS/GPU, fuzzy memory recall quality  
- Org voice session DAU / MOS  
- Policy violation rate KPI  
- Host CPU/mem; `cache_hit_rate_24h` / `mcp_servers_connected` (null today)  
- Per-workflow `metricsApi.workflowStats(id)` — **client dead end** (no backend route)

### Critical prerequisite before claiming “live KPIs”

**Normalize metrics overview (+ aiOsStatus) field paths** so home stops reading snake keys that live APIs do not return.

---

## H. Preference / persistence architecture

| Lane | Today | Fit for dashboard layout |
|------|-------|--------------------------|
| `localStorage` UI chrome | nav, panels, themes | L1 optimistic cache only |
| `user_preferences` | model/mode/persona | Do not overload unless `ui` jsonb added |
| `notification_preferences` / `meson_user_preferences` | `(org_id, user_id)` jsonb | **Best pattern to copy** |
| Org `settings` | policy/branding | Defaults only, not personal layout |

**Recommendation:** New `user_ui_preferences` (or `dashboard_layouts`) table: `UNIQUE(org_id, user_id)` + jsonb `{ version, widgets[], globalRange }`. Scope = **user within org**. Optional org default layout later.

**No dashboard widget preference schema exists today.**

---

## I. Grid / drag / resize

| Finding | Detail |
|---------|--------|
| Existing deps | **No** `react-grid-layout` / `@dnd-kit`; `react-resizable-panels` unused for grids |
| In-app DnD | Custom workflow canvas; HTML5 on schedules calendar |

**Recommendation:**

1. Phase 1 layout: CSS 12-col grid + edit-mode reorder (HTML5 or Framer) — no new dep if widgets are few fixed sizes.  
2. Phase 2 (resize + breakpoints): add **`react-grid-layout`** (proven collision/reflow).  
3. Mobile: single column + up/down reorder controls (not free-form drag).

---

## J. KPI registry proposal (v0)

```
KpiDefinition {
  id: string                    // e.g. "agents.active"
  category: Category
  name: string
  description: string
  availability: "available" | "derivable" | "requires_telemetry"
  endpoint: string
  fieldPath: string
  defaultViz: VizType
  allowedViz: VizType[]
  hrefTemplate?: string         // deep-link with filters
  adminOnly?: boolean
}
```

Categories: Agents · Workflows · Runs · Approvals · Connectors · AI/Models · GIBE · Memory/RAG · Voice · Governance · Usage · System Health

Seed registry **only** with AVAILABLE NOW + DERIVABLE rows from inventory. Hide REQUIRES TELEMETRY from picker (or show disabled “coming soon” without fake values).

---

## K. Widget model proposal

```
DashboardWidget {
  id: string
  metricId: string
  title?: string                // override
  size: "1x1" | "2x1" | "2x2" | "4x1" | "4x2"
  position: { x: number; y: number; w: number; h: number }  // grid units
  visualization: VizType
  filters?: { range?: "1h"|"24h"|"7d"|"30d"; department?; agentId?; ... }
  refreshSec?: number
  config?: Record<string, unknown>
}

DashboardLayout {
  version: 1
  globalRange: "7d"
  editMode?: boolean            // client-only
  widgets: DashboardWidget[]
}
```

Shared data layer: single SWR/batched fetch map keyed by endpoint+range; widgets subscribe — **no N× independent hammers**.

---

## L. Add KPI menu design

Trigger: restrained `+ Add KPI` (Nucleo plus) in page header actions **only in Edit dashboard mode**.

Drawer / dialog:

1. Search  
2. Tabs: Recommended · Favorites · Displayed · Available  
3. Category accordion  
4. Row: name, short description, category, viz chips, “On dashboard” check  

No prices, badges, or invented claims.

---

## M–N. Default + extended layouts

### Default (Nodus-faithful) — new users

| Row | Widgets |
|-----|---------|
| 1 | 4× `1x1` KPI: Active agents · Task success · Avg execution · Active workflows |
| 2 | `4x1` Workflow monitor (Agent / Model / Status / Duration / Last run — real runs/approvals) |
| 3 | `2x2` Agents by status (donut) · `2x2` Tasks/runs breakdown (stacked bars) |

**Remove from default:** welcome hero emphasis, Open Gravitre AI primary CTA, status chip strip (move to optional widgets), dual learning progress bars (optional GIBE widgets).

### Extended (picker catalog examples — real data only)

Execution health · Approval queue · Connector health · Model catalog live count · GIBE confidence · Learning progress · Memory promotions · Voice minutes remaining · Audit actions · Integration health score · Recent failures · Business impact risks

---

## O–R. Edit mode / reflow / resize / persistence (acceptance for impl)

| Capability | Plan |
|------------|------|
| Edit mode | “Customize dashboard” → handles, remove, Add KPI, Reset, Save |
| Drag | Grid collision + auto reflow; keyboard move alternate |
| Resize | Presets only; progressive reveal (S number → M + trend → L chart) |
| Persist | Save layout jsonb to user+org prefs API; localStorage mirror |
| Empty | “No runs yet” / “Waiting for first execution” — never invent numbers |

---

## S. Responsive

| Breakpoint | Behavior |
|------------|----------|
| Desktop | Full grid + drag |
| Tablet | Auto reflow |
| Mobile | Single column; reorder buttons |

---

## Implementation phases (proposed — **await approval**)

| Phase | Deliverable |
|-------|-------------|
| **D0** | Cesar approval of this audit |
| **D1** | Remap overview/aiOs field paths; compact title token app-wide; strip default header chrome to Nodus scale |
| **D2** | Literal default layout (KPI + monitor + dual charts) ≥9/10 vs PNG |
| **D3** | KPI registry + batched data hooks |
| **D4** | Widget model + Edit mode + Add KPI picker |
| **D5** | Drag/reflow (+ react-grid-layout if needed) + resize presets |
| **D6** | Persistence API + presets (Operations / Executive / …) |
| **D7** | Mobile reorder; a11y; Playwright fidelity scorecard |

---

## Scaffold honesty

**(a)** Audit + implementation explicitly requested and approved (Cesar, 2026-09-08).  
No invented prices, claims, badges, or Enable toggles. No fake metrics.  
KPI registry seeds **AVAILABLE NOW** only. Overview date range UI includes 1h/24h but API maps those to `7d` (backend `_validate_range` accepts `7d|30d|90d` only).

---

## Implementation (2026-09-08)

| Phase | Delivered |
|-------|-----------|
| D1 | camelCase normalize for metrics + aiOs; compact `GravitrePageHeader` on `/home` |
| D2 | Default layout: 4 KPIs · Workflow monitor · Agents donut · Runs breakdown |
| D3 | `KPI_REGISTRY` + `useHomeDashboardData` shared SWR fetches |
| D4 | Edit mode · `+ Add KPI` picker (search/categories) · remove widget |
| D5 | CSS 12-col packer · HTML5 drag reflow · size cycle · mobile ↑↓ |
| D6 | `localStorage` + `/api/settings/dashboard-layout` → `user_ui_preferences` |
| D7 | Vitest pack/normalize; mobile reorder; keyboard-friendly remove/resize |

**Files:** `apps/web/lib/dashboard/*`, `apps/web/components/home/*`, `apps/web/hooks/use-dashboard-layout.ts`, `apps/web/hooks/use-home-dashboard-data.ts`, `supabase/migrations/20260908010000_user_ui_preferences.sql`

---

## Migration applied (2026-09-08)

| Item | Evidence |
|------|----------|
| Project | `smyeexlrqdpymwjmgzqu` (supabase-green-flower) |
| Migration name | `user_ui_preferences` via Supabase MCP `apply_migration` |
| Table | `public.user_ui_preferences` — RLS enabled, unique `(org_id, user_id)` |
| Deploy | App already on `main` @ `6f3557e6` (`dpl_B84q9Z8Zgr5zRwNr1zy7AoPbyZff`) — server persist path live after this apply |
