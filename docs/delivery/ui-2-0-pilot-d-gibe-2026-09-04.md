# GRAVITRE UI 2.0 — Pilot D (GIBE / intelligence) delivery

**Date:** 2026-09-04  
**Scope:** Intelligence landing Module C honesty strip — no WebGL  
**Route:** `/intelligence` (signed in)

---

## Where to see all pilots

| Pilot | Route |
|-------|-------|
| A Marketing | `/` |
| B Dashboard | `/home` |
| C Agents | `/agents`, `/agents/[id]` |
| D GIBE | `/intelligence` |
| E Voice | `/ai` |

---

## What shipped

| Item | Change |
|------|--------|
| **GibeHonestyStrip** | Always on hub; empty state when no org training rows |
| **Labels** | Estimate (heuristic) · Model (artifact loaded) · Insufficient data · Catalog only — **never** bare TRAINED |
| **Logic** | `presentModelRuntime` — catalog TRAINED without artifact ≠ live |
| **Confidence** | Stat uses `ESTIMATED_CONFIDENCE_LABEL` + `ConfidenceBadge` when `confidence_is_estimate` |
| **Routing trace** | Removed fabricated “ok” stages; honesty empty instead |
| **TYPE / RADIUS** | PageHeader eyebrow **GIBE**; panel/card tokens |
| **WebGL** | **Not added** (requires separate approval) |

---

## Evidence

| Check | Result |
|-------|--------|
| `vitest run __tests__/lib/model-runtime-honesty.test.ts` | **PASS** — 5 tests @ 2026-09-04 local |
| Live Class A screenshot | **NOT RUN** |

---

## Customer-surface declaration

**(a)** No new prices, SOC claims, Enable toggles, or catalog TRAINED-as-live. STA-331 estimate labeling only.

---

## Files

- `apps/web/lib/intelligence/model-runtime-honesty.ts`
- `apps/web/components/intelligence/gibe-honesty-strip.tsx`
- `apps/web/app/intelligence/page.tsx`
- `apps/web/__tests__/lib/model-runtime-honesty.test.ts`
