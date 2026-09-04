# GRAVITRE UI 2.0 — Pilot B (Dashboard / home hub) delivery

**Date:** 2026-09-04  
**Scope:** Authenticated `/home` shell — PageHeader, status chips, elevation, honesty cleanup  
**Depends on:** Pilots E + A

---

## What shipped

| Item | Change |
|------|--------|
| **PageHeader + TYPE** | Replaced hand-rolled hero with shared `PageHeader` (`TYPE` via component) |
| **Status chips** | Approvals clear/pending · confidence when trust API has avg · learning snapshot/warming — **no** invented “Command surface · Live” |
| **Stats** | `StatsGrid` / `StatCard` for the four real counters |
| **Surfaces** | `RADIUS.panel` / `tile` / `card` + `shadow-sm` (elevation-1) / semantic borders |
| **Removed fabricated UI** | Synthetic 7-day confidence AreaChart + fake “+% this week”; decorative ParticleField/GlowOrbs; invented predictive bar heights `[42,58,…]` |
| **Honesty empties** | Confidence / predictive / revenue-risk empty states when API has no data |
| **KEEP** | Same props + SWR data from `app/home/page.tsx` (approvals, trust, learning, aiOs, etc.) |

---

## Customer-surface declaration

**(a)** No new prices, TRAINED badges, Enable toggles, or invented ROI/%.  
Confidence chip only when `trust` avg exists; otherwise “not yet available”.

---

## Verification

| Check | Result |
|-------|--------|
| Lints `home-dashboard.tsx` | Clean |
| Live Class A screenshot of header + live approval chip | **NOT RUN** (needs authenticated `/home` in browser) |
| Data path | Unchanged — `approvalsApi.list()` → pending chip; `intelligenceApi.trustSummary` → confidence |

---

## Files

- `apps/web/components/home/home-dashboard.tsx` (primary)
- Data wiring unchanged: `apps/web/app/home/page.tsx`
