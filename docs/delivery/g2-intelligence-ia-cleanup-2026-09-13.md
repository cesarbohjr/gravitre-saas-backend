# G2 — Intelligence IA Cleanup (Delivery Report)

**Date:** 2026-09-13  
**G2 COMPLETE:** **YES** (IA split + telemetry relocation; no graph rebuild)

---

## Objective

Separate customer business intelligence from org-admin engineering telemetry. Fix navigation/taxonomy collisions without rebuilding the map (G3) or projection layer (G1).

---

## Changes

### 1. Customer Learning surface (P0)

- **`/intelligence/learning`** — new customer page using G1 `pageContext` (`learns` lens)
- Shows business `LearningInsight` cards, learning metrics, `BusinessImpactCard`
- Explicit empty state: no platform telemetry / model readiness masquerading as learning
- Link to **`/admin/intelligence`** for platform telemetry

### 2. Admin platform console (P0)

- **`/admin/intelligence`** — restored as admin-only route (removed redirect to Learning)
- Removed `IntelligenceHubTabs` from admin page
- Renamed surface copy to **Platform intelligence**
- Internal tab **Performance** → **Latency & cache** (avoids collision with hub Performance = business ROI)

### 3. Engineering telemetry removed from customer paths (P0)

| Removed from customer | Relocated to |
|----------------------|--------------|
| Golden signals, TTFT, cognitive turns (via Learning re-export) | `/admin/intelligence` |
| `/metrics` link in Overview advanced drawer | Admin / Settings (route unchanged) |
| Platform Health tab on Reports | Removed (admin platform console) |
| GIBE honesty + training readiness strips on Overview advanced | Removed from customer advanced drawer |

### 4. Semantic / copy fixes (P1)

- LEARNS lens no longer falls back to model training readiness counts
- Hub link: "Business learning" (not "golden signals")
- Predictive page: business language (not "canonical state")
- Breadcrumb: `/intelligence/performance` → "Performance" (not admin "Latency & cache")

---

## Customer vs admin IA (after G2)

```
Customer Intelligence hub
  Overview | Learning | Predictions | Performance | Models | Model Studio | Training | Reports

Admin (org operators)
  /admin/intelligence — Platform intelligence (golden signals, TTFT, engine, cognitive turns)
```

---

## Deferred (G3–G8)

- G3: Semantic graph renderer rebuild
- G4: Conversation ↔ map visualization
- G6: Map hub parallel legacy API fetches on Overview
- G7: Further Learning enrichment off admin snapshot APIs

---

## Files changed

- `apps/web/app/intelligence/learning/page.tsx` (new customer surface)
- `apps/web/app/admin/intelligence/page.tsx`
- `apps/web/app/intelligence/page.tsx`
- `apps/web/app/intelligence/reports/page.tsx`
- `apps/web/app/intelligence/predictive/page.tsx`
- `apps/web/components/intelligence/intelligence-hub-tabs.tsx`
- `apps/web/components/intelligence/map/build-lens-metrics.ts`
- `apps/web/components/gravitre/app-breadcrumbs.tsx`
- `apps/web/lib/surface-copy.ts`
- `apps/web/next.config.mjs`
