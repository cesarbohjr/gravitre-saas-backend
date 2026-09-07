# GRAVITRE — NODUS PRODUCT UI RECONSTRUCTION · GATE AUDIT

**Date:** 2026-09-07  
**Status:** **APPROVED** (2026-09-07) · P1–P3 implementation authorized and shipped separately  
**Scope:** Product application reconstruction from Nodus product imagery (not marketing-only parity)

Related prior Gate 0 (marketing): `docs/delivery/ui-3-0-nodus-full-match-gate-0-audit-2026-09-06.md`

---

## 1. Exact purchased Nodus source location

| Field | Path |
|-------|------|
| **NODUS SOURCE ROOT** | `C:\Users\Cesar\Downloads\Gravitre Operator AI\vendor\nodus-agent-template\` |
| Purchase zip (OneDrive) | `C:\Users\Cesar\OneDrive\Gravitre\nodus-agent-template.zip` |
| Purchase zip (Downloads) | `C:\Users\Cesar\Downloads\nodus-agent-template.zip` |
| Archive root name | `manuarora700-notus-agent-marketing-template-1aa99c8edb6d6c1eb7567dfa15cf114db741bd2e` |
| Git | `vendor/nodus-agent-template/` is **gitignored** (licensed; on disk only) |
| File inventory | `vendor/nodus-file-inventory.txt` (~155 files excl. lock/node_modules) |

### Source tree (present)

```
vendor/nodus-agent-template/
  app/           # marketing routes only (home, pricing, about, blog, careers, contact, sign-in/up, playground)
  components/    # marketing sections + FX (47 TSX)
  icons/         # general, bento, card SVG packs
  fonts/         # Inter Display + DM Mono
  public/        # PRODUCT IMAGES live here (dashboard*, logos, avatars, team, banner)
  constants/, data/, hooks/, context/, lib/, config/
  package.json   # motion ^12.42.2 (no GSAP; no shadcn app shell)
```

### Scope honesty (unchanged from Gate 0, critical for this program)

The licensed package is a **Next.js marketing site**. It does **not** contain:

- Authenticated app shell
- React dashboard / agents / workflows / runs / approvals screens
- Real chat workspace
- Desktop / extension / mobile app shells

→ Marketing = adapt licensed React.  
→ **Product application = reconstruct from Product Images as measured design specs** + Gravitre data/routes.

---

## 2. Complete Product Image inventory

### A. Primary product UI assets (application design SOT)

| FILE | PATH | TYPE | DIMENSIONS | AR | WHERE USED | NODUS COMPONENT | SCREEN DEPICTED |
|------|------|------|------------|-----|------------|-----------------|-----------------|
| `dashboard@3x.png` | `vendor/.../public/dashboard@3x.png` (+ mirrored `apps/web/public/nodus/`) | PNG | **3312×1860** | **1.7806** | Marketing hero product stage | `components/hero-image.tsx` (`src="/dashboard@3x.png"`) | Full app: sidebar + KPI strip + Workflow monitor + Agents-by-status donut + Tasks breakdown bars |
| `dashboard.png` | same dirs | PNG | **2209×1241** | **1.7800** | Fallback / lower-DPI of same art | Same family | Same as above |

**VISIBLE UI (from asset + live preview):**

- Sidebar: Dashboard, Agents, Workflows, Simulations, Tasks, Apps, Notifications (+ logo lockup)
- Header: “Dashboard” title + search (`⌘K`)
- KPI strip (4): Active agents **128**, Task success **96.7%**, Avg execution **12.4s**, Most used model **GPT-4o**
- Workflow monitor table: agent/workflow, model badge, status dot, latency, last run
- Charts: Agents by status (donut), Tasks breakdown (stacked bars, Past 7 days)

**RESPONSIVE / MOTION / FRAME (wrapper, not intrinsic to PNG):**

| Property | Value (from `hero-image.tsx`) |
|----------|-------------------------------|
| Animation | Opacity 0→1, duration **0.3s**, delay **1s**; mouse parallax spring **stiffness 300 / damping 30**, translate ±40px |
| Mask / crop | None on image; full `w-full` |
| Shadow | Via `--shadow-aceternity` on surrounding chrome; image itself flat bitmap |
| Border / radius | Outer container `rounded-lg` + hairline `--pattern-fg`; corner **Dot** ornaments |
| Background | Parent `bg-gray-100` + diagonal Scale pattern under image (`absolute inset-0 … 90%/95%`) |
| Positioning | Centered in `Container` with `border-x`; padding `p-2 md:p-4 lg:p-8` |
| Responsive | Scales with container width; no alternate mobile asset |

**SOURCE TYPE VERDICT:** **C. PNG** (primary). Not React, not SVG, not WebP for the dashboard UI.

### B. Secondary / non-app product-adjacent assets

| FILE | PATH | TYPE | DIMS | ROLE | APP DESIGN SOT? |
|------|------|------|------|------|-----------------|
| `banner.png` | `public/banner.png` | PNG | 1200×630 | OG / social | No (marketing meta) |
| `avatar.webp` | `public/avatar.webp` | WebP | 1000×1000 | Demo avatar | No |
| `avatars/*.png` | alex/manu/tyler | PNG | ~1000² | Testimonials | No (fake people) |
| `team/1–6.png` | `public/team/` | PNG | 672×480 | About/team | No |
| `blog/*.webp` | ace, nextjs | WebP | varies | Blog heroes | No |
| `logos/1–10.png` + press | `public/logos/` | PNG | wordmarks | Logo cloud / press | No (claims risk) |
| `logos/CCPA|GDPR|ISO.png` | compliance | PNG | ~150×250 | Security strip | No (authorize or remove) |
| `illustrations/native-tools-integration.svg` | SVG | vector | Tools illustration | Partial (FX only) |

**No Product Image left unlisted** in `vendor/nodus-agent-template/public` raster set (see measurement pass 2026-09-07).

---

## 3. How the dashboard was created

| Hypothesis | Result |
|------------|--------|
| A. React/HTML components | **FALSE** — no dashboard/app routes or KPI/table React in vendor |
| B. SVG | **FALSE** for shell (only tools illustration SVG exists) |
| **C. PNG** | **TRUE** — `dashboard.png` / `dashboard@3x.png` |
| D. WebP | Not for dashboard |
| E. Figma-export-like | **Likely origin** of the PNG (flat UI mock), but we only possess the raster |
| F. Other | N/A |

**Implication:** There is **no React implementation to reuse** for the in-app dashboard.  
**Plan:** Treat `@3x` PNG as measured visual specification → reconstruct as real React (`GravitreAppShell` + home dashboard) with **live Gravitre metrics**.

Mirrored marketing copies (green-recolored) live at `apps/web/public/nodus/dashboard*.png` — still bitmaps, not components.

---

## 4–5. Visual measurement / Nodus product design tokens (from PNG + CSS)

### Measured geometry (`dashboard@3x.png` 3312×1860)

| Element | Measurement (image px @3x) | ≈ @1x (×2209/3312) | Notes |
|---------|---------------------------|---------------------|--------|
| Outer frame | Full canvas | 2209×1241 | Includes soft chrome; content starts ~x=60 |
| Sidebar / content divider | **~302 px** from left | **~201 px** | Vertical hairline candidate |
| Sidebar width (content) | ~240–250 px | **~160–170 px** tight; visual label rail reads **~200 px @1x** | Use **200–220 CSS px** target for labeled rail |
| Main canvas | Remaining width | — | White / near-white `#fbfbfb`–`#ffffff` |
| Page title band | Top ~80–110 px | — | “Dashboard” + search |
| KPI strip | 4 equal cards under header | — | White cards, hairline borders, soft radius |
| Workflow monitor | Mid band full content width | — | Table header + 3 example rows |
| Charts row | Bottom dual panel | — | Donut left, bars right |

*Fidelity note:* Exact CSS px depends on how tightly we crop chrome; Phase 1 should pin against Playwright overlays at fixed viewport.

### Material / type from Nodus `app/globals.css` (licensed)

| Token | Nodus value | Role |
|-------|-------------|------|
| `--color-brand` | `#f17463` | Accent (→ Gravitre green) |
| charcoal-900/800/700 | `#202020` / `#29292e` / `#343434` | Graphite type |
| gray-100…600 | `#f9f9f9`…`#8b8b8b` | Mineral surfaces / muted |
| `--shadow-aceternity` | layered soft triple | Card / control elevation |
| Fonts | Inter Display + DM Mono | Display / mono |
| Divide | `--color-gray-300` `#eaedf1` | Hairline borders |

### Proposed **NODUS PRODUCT DESIGN TOKENS** (application)

```
Canvas:           --np-canvas: #ffffff | --np-canvas-muted: #f9f9f9 | --np-canvas-inset: #f5f5f5
Surface:          --np-surface: #ffffff | --np-surface-hover: #f9f9f9 | --np-surface-selected: color-mix(brand 6%, white)
Border:           --np-border: #eaedf1 | --np-border-strong: #d7d7d7
Shadow:           --np-shadow: var(--shadow-aceternity)
Radius:           --np-radius-sm: 6px | --np-radius-md: 8px | --np-radius-lg: 12px
Sidebar width:    --np-sidebar: 220px (expanded) | --np-sidebar-rail: 64px (icon)
Page padding:     --np-page-pad: 24px (md+) / 16px (sm)
KPI gap:          --np-kpi-gap: 16px
Table row:        --np-row-h: 44–48px | header: 40px
Icon (nav):       16–18px graphite
Metric numeral:   Inter Display semibold ~28–32px
Body / table:     13–14px / 12–13px muted labels
Chart palette:    pastel brand-green / soft mint / soft violet / soft slate (not neon)
```

**Language (locked):** light canvas · white/mineral surfaces · graphite type · hairline borders · very subtle shadows · controlled radius · compact nav · high information density · generous whitespace · small icons · pastel viz · calm hierarchy.

---

## 6. Gravitre logo-green extraction

| Source | Result |
|--------|--------|
| Official asset | `apps/web/public/images/gravitre-icon-green-1024.png` |
| Documented canonical | **`#16a374`** (`globals.css` comment: from this asset) |
| Raster average of opaque green pixels | `#37b088` (anti-alias / soft fill — **do not use as brand**; keep `#16a374`) |
| Nodus orange replaced | `#f17463` → `#16a374` |

### Semantic brand tokens (to complete / alias)

| Token | Proposed |
|-------|----------|
| `--g-brand` | `#16a374` |
| `--g-brand-hover` | darker ~`#128a63` |
| `--g-brand-active` | `#0f7a58` |
| `--g-brand-soft` | `#e0f3ec` (exists as `--brand-soft`) |
| `--g-brand-muted` | `#5ec49a` |
| `--g-brand-surface` | `color-mix(in srgb, #16a374 6%, white)` |
| `--g-brand-border` | `color-mix(in srgb, #16a374 22%, #eaedf1)` |
| `--g-brand-glow` | soft brand shadow (marketing only; sparse in app) |

### Status palette (preserve; do not paint everything green)

| Role | Color |
|------|-------|
| Brand / success / verified | Green `#16a374` |
| AI / GIBE / intelligence | Violet (selective) |
| Signal / connectivity | Cyan |
| Waiting / approval | Amber |
| Error / failed | Red |
| System / type | Graphite |
| Canvas | Mineral white |

---

## 7. Nucleo icon mapping

| Fact | Evidence |
|------|----------|
| Nucleo assets on disk | **`apps/web/public/icons/nucleo`** ≈ **1080** files |
| Product usage today | **`NucleoIcon` referenced in ~1 TSX**; Lucide in **~280** TSX; Phosphor **~34**; `@/lib/icons` **~29** |
| Nodus template icons | Custom SVG packs in `vendor/.../icons/*` (not Nucleo) |

### Target nav map (Nodus screenshot labels → Gravitre → Nucleo)

| Nodus art | Gravitre route/surface | Nucleo direction |
|-----------|------------------------|------------------|
| Dashboard | `/home` | `dashboard` / solidDashboard (`77980` / `78050`) — verify glyph |
| Agents | `/agents` | team/users glyph from Nucleo catalog (replace Phosphor/Lucide) |
| Workflows | `/workflows` | `bezier` (`77900`) |
| Simulations | Workflow simulate / failure-predictions | flask/play — pick Nucleo id |
| Tasks | `/tasks`, `/assignments` | checklist — pick Nucleo id |
| Apps | `/connectors`, marketplace | `store` (`77920`) / plug |
| Notifications | `/notifications` | bell — pick Nucleo id |
| (Gravitre extras) Chat, Approvals, GIBE, Settings, Audit, Voice… | existing routes | map 1:1; keep vendor logos for Salesforce/HubSpot/etc. |

**Rule:** Nucleo for app chrome/actions/state; **real brand logos** for connectors/services.

---

## 8. Current Gravitre route inventory (product)

**Marketing** (`app/(marketing)/`): ~28 routes (home, pricing, features*, docs, blog, legal, auth pages, …).

**Authenticated product** (selected groups):

| Domain | Routes |
|--------|--------|
| Shell home | `/home`, `/welcome`, `/onboarding` |
| AI Chat | `/ai`, `/chat`, `/assistant` |
| Agents | `/agents`, `/agents/[id]/*`, `/agents/new`, `/agents/swarm` |
| Workflows | `/workflows`, `/workflows/[id]/builder`, schedules, failure-predictions |
| Runs / activity | `/runs`, `/runs/[id]`, `/activity`, `/outcomes`, `/multi-agent-run` |
| Approvals | `/approvals` |
| Connectors | `/connectors`, `/integrations` |
| GIBE / intel | `/intelligence/*`, `/metrics`, `/models`, `/sources` |
| Marketplace | `/marketplace/*` |
| Settings | `/settings/*` (billing, team, enterprise, profile, …) |
| Lite | `/lite/*` |
| Desktop / extension bridges | `/desktop/connect`, `/extension/connect` |
| Admin | `/admin/intelligence` |

Full list captured in audit shell pass (2026-09-07).

---

## 9. Current Gravitre component inventory (product chrome)

| Area | Key paths |
|------|-----------|
| App shell | `components/gravitre/app-shell.tsx`, `sidebar.tsx` (`w-64`), `sidebar-nav-config.ts`, `sidebar-nav-link.tsx`, top-bar / command bar |
| Home | `components/home/home-dashboard.tsx` (Nodus-**inspired**, real metrics; not pixel-matched to PNG) |
| Chat | `components/gravitre/assistant/*`, agent-ui thinking/tool groups |
| Design tokens | `app/globals.css` (Nodus marketing tokens + `--g-*` product tokens partially) |
| Icons | Lucide-dominant; Nucleo underused |
| Motion | `framer-motion` in app; Nodus vendor uses `motion` package |

Phase 8 already applied light Nodus **material** to shell — **not** full dashboard structural fidelity to Product Image.

---

## 10. Nodus → Gravitre application mapping

| Nodus Product Image region | Gravitre destination | Data source |
|----------------------------|----------------------|-------------|
| Sidebar | `GravitreSidebar` / existing sidebar | Nav config (IA may keep Gravitre extras) |
| KPI: Active agents | `/home` metric | Live agent count (active) |
| KPI: Task success rate | `/home` | Verified run/workflow success % |
| KPI: Avg execution time | `/home` | Mean run duration |
| KPI: Most used model | `/home` | Model usage analytics |
| Workflow monitor | Home table / `/runs` preview | Recent runs (real fields only) |
| Agents by status | Home chart | Agent status breakdown |
| Tasks breakdown | Home chart | Task/assignment volume (labeled) |
| Search ⌘K | `global-command-bar` / command palette | Existing |
| Simulations (nav) | Map to workflow simulate / predictions — **do not invent a fake Simulations product** |

---

## 11–19. Reconstruction plans (summary)

### 11. Dashboard
Rebuild `/home` to **9/10 structural fidelity** vs Product Image: sidebar rhythm + 4 KPI cards + operational table + dual charts. Real data only; empty/honest states when metrics missing.

### 12. Agents
List / detail / create / config / activity / tools / memory / permissions / outcomes — same surfaces/spacing/tables as Nodus grammar; content = Gravitre agents.

### 13. Workflows
List / detail / builder / history / errors / approvals — Nodus tables + FLOW/TRACE/RESOLVE motion (not generic spaghetti).

### 14. Runs
List / active / detail timeline / tools / approvals / evidence — calm primary UI; logs secondary.

### 15. Approvals
Queue + detail; amber/green/red status language.

### 16. Connectors
Catalog + detail + health; **vendor logos** + Nucleo controls.

### 17. GIBE / Intelligence
Extend beyond screenshot; violet accents only for intelligence; same mineral shell.

### 18. AI Chat
Same shell, spacing, surfaces; Agent Elements restyled to Nodus×Gravitre; no separate ChatGPT skin.

### 19. Settings / secondary
Same tokens for settings, billing, dialogs, empty/loading/error — **no visual islands**.

---

## 20–22. Desktop / mobile / extension

| Surface | Plan |
|---------|------|
| Desktop | Same tokens; denser panes, shortcuts, context menus — not a website wrapper only |
| Mobile | **Do not shrink sidebar** → drawer / bottom nav; tables → cards/lists; progressive disclosure |
| Extension | Compressed same system: Context / Capture / Agent / Action / Approval / Status |

---

## 23. Shared component architecture

Canonicalize: `GravitreAppShell`, `GravitreSidebar`, `GravitreNavItem`, `GravitrePageHeader`, `GravitreMetric`, `GravitreSurface`, `GravitreTable*`, `GravitreStatus`, `GravitreBadge`, `GravitreSelect`, `GravitreFilter`, `GravitreChart`, empty/loading/error, `GravitreCommand`, `GravitreSearch`, `GravitreApproval`, agent/execution state.

Creative Tim / 21st / shadcn: **structure only**; strip default styling; Nodus tokens win.

---

## 24. Motion architecture

| Source | Extract |
|--------|---------|
| Nodus `hero-image` | spring 300/30; enter 0.3s delay 1s |
| Nodus CTA orbit | 24s linear |
| Nodus how-it-works | 8s dwell; blur 0.5s; pixel fill 2.5s |
| Nodus FAQ | 0.25–0.35s |
| Package | vendor `motion`; app also `framer-motion` — converge |

GSAP: marketing storytelling only; **not** default app controls.  
Add `prefers-reduced-motion` systematically.

Preserve/restyle: Orb, Wave, Voice visualizer, Pulse, Flow, Trace, Resolve, AnimatedMetric/Status, AgentActivityIndicator, WorkflowExecutionPath, ConnectorFlow.

---

## 25. Visual QA plan

- Playwright snapshot suite at fixed viewports (1280, 1440, 390)
- Comparison boards: **Nodus Product Image | Gravitre implementation** (same crop)
- Dashboard Fidelity Scorecard (sidebar, margins, KPI, table, chart, radius, icon size, density) target **≥9/10**
- **No self-certify** without screenshots + scorecard

---

## 26. Before / reference board

| Reference | Location |
|-----------|----------|
| Licensed original | `vendor/nodus-agent-template/public/dashboard@3x.png` |
| Live marketing (green-adapted) | `https://gravitre.app/nodus/dashboard@3x.png` |
| Current product home | `https://gravitre.app/home` (auth) — Nodus-inspired, **not** fidelity-matched |
| Nodus preview | `https://ui.aceternity.com/template-preview/nodus-agent-template` |

---

## 27. Exact implementation phases (proposed — **not started**)

| Phase | Deliverable | Gate |
|-------|-------------|------|
| **P0** | Cesar approval of this audit | **STOP here until approved** |
| **P1** | Product token sheet + Playwright baseline vs PNG overlays | Scorecard v0 |
| **P2** | `GravitreAppShell` / sidebar / page header fidelity | Shell 9/10 |
| **P3** | `/home` dashboard reconstruct (KPI + monitor + charts) | Dashboard 9/10 |
| **P4** | Shared table/metric/chart/status primitives | Library |
| **P5** | Nucleo nav swap (lucide/phosphor purge on chrome) | Icon audit |
| **P6** | Agents + Workflows surfaces | |
| **P7** | Runs + Approvals | |
| **P8** | Connectors + GIBE | |
| **P9** | AI Chat normalize | |
| **P10** | Settings / secondary / dialogs | No islands |
| **P11** | Mobile adapt | |
| **P12** | Desktop densify | |
| **P13** | Extension compress | |
| **P14** | Marketing screenshots ← real product captures | Continuity |
| **P15** | Full Playwright fidelity pack + sign-off | Done |

---

## Scaffold honesty

**(a)** Audit explicitly requested; **no production implementation in this step**.  
No invented prices, claims, badges, or Enable toggles.  
Product Image metrics (128 agents, etc.) are **illustration only** — real app uses live data / honest empties.

---

## STOP

No production code changes were made for this audit.  
Await review / named phase approval before implementation.

---

## Sign-off / Approved (2026-09-07)

Cesar approved Gate audit (“I approve”). Authorization to implement **P1 → P2 → P3** (tokens, shell, `/home` product reconstruction from Product Image + live data). Later phases (P4+) still require separate go-ahead unless expanded in-thread.

---

## Shipped — P1–P3 (2026-09-07)

| Phase | Delivered |
|-------|-----------|
| P1 | `globals.css` product tokens (`--g-brand*`, `--np-*` layout); fidelity note `docs/delivery/nodus-product-ui-p1-p3-shipped-2026-09-07.md` |
| P2 | Sidebar `var(--np-sidebar)` / rail; default nav expanded |
| P3 | `/home` KPI + Workflow monitor + charts via `GravitreMetric`/`GravitreSurface`; live agents + metrics overview; honest empties |

**Not claimed:** production visual PASS (needs Vercel Ready + authenticated `/home` vs PNG).  
**Scaffold:** (a) authorized by Gate approval — no invented prices/claims/Enable toggles.
