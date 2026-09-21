# Gravitre UX/UI 3.0 Plus — Harness Review Guide

**Date:** 2026-09-21  
**Status:** **HARNESS APPROVED** (2026-09-21) — Activity A1 pilot authorized  
**Route:** `/dev/ai-workspace-preview` (local/staging only · `noindex`)

---

## Cesar design selections (locked)

| Area | Selection |
|------|-----------|
| Intelligence | **I1 Field Topology** + contextual **I2 change stream** (collapsible) |
| Activity | **A1 TRACE Rail + Story** + optional **A2 timeline** view |
| Navigation | **B Expandable labeled rail** (click/pin, not hover-only) |
| First production pilot | **Activity A1** — after harness approval only |
| Journey tests | Staging first, then controlled prod smoke |

---

## How to review

1. Run web app locally: `pnpm --filter web dev`
2. Open harness surfaces in order:
   - `?s=foundation&scene=default`
   - `?s=intelligence&scene=default` → cycle scenes
   - `?s=activity&scene=default` → include `timeline`, `fail`, `ai-context`
   - `?s=navigation&scene=compact` → `expanded`, `pinned`, `keyboard`, `mobile`
3. Toggle **Reduce motion** in OS settings and re-open `reduced` scenes.
4. Compare **before/after** panels at bottom of Intelligence, Activity, Navigation.

---

## Surface → scene matrix

### Foundation
| Scene | Shows |
|-------|--------|
| default | Canvas, semantic color, type roles, node/edge/evidence, motion sample |
| reduced | Static motion |

### Intelligence (I1 + I2)
| Scene | Shows |
|-------|--------|
| default | **I1 field primary** — change stream closed; click “What changed?” to open I2 |
| change | I2 change stream open; selecting event focuses topology + evidence |
| compare | CURRENT production stub vs PROPOSED I1/I2 side-by-side + data contract |
| selected | Node selection + focus |
| inspector | Inspector open |
| ai-context | Ask-about-this chip |
| loading | Skeleton |
| empty | Honest empty (incl. sparse entity ids) |
| error | Retry |
| mobile | 390-width layout |
| reduced | No spring animation |

### Activity (A1 + A2)
| Scene | Shows |
|-------|--------|
| default | List + TRACE rail + story (A1 default) |
| timeline | A2 temporal bar chart — **toggle Story/Timeline in header** |
| fail | Failed outcome — failure scoped to Tool stage only |
| selected / inspector / ai-context | Selection + contextual AI |
| loading / empty / error / mobile / reduced | Same pattern as Intelligence |

### Navigation (B)
| Scene | Shows |
|-------|--------|
| compact | 64px icon rail |
| expanded | 220px labeled rail |
| pinned | Persist expanded |
| keyboard | Arrow key focus ring |
| mobile | Drawer overlay |

---

## Fixture honesty

All data labeled **Harness fixture · Northwind Logistics · not live telemetry**.  
Shapes match production contracts (`IntelligencePageContextResponse` graph, `BusinessOutcomeDto` timeline).

---

## Not in this harness

- Production route changes
- Global top bar redesign (shown coupled in nav prototype only)
- Connectors, Sources, Marketplace
- Authenticated journey results → `GRAVITRE_3.0_JOURNEY_RESULTS.md`

---

## Automated smoke (harness-only)

**Spec:** `e2e/visual/ux30-plus-harness.spec.ts`  
**Gate status:** `GRAVITRE_3.0_HARNESS_GATE_STATUS.md`

Re-run against production harness (no auth):

```bash
PLAYWRIGHT_BASE_URL=https://gravitre.app \
PLAYWRIGHT_SKIP_BACKEND=1 \
PLAYWRIGHT_REUSE_SERVER=1 \
npx playwright test e2e/visual/ux30-plus-harness.spec.ts
```

Captures 29 PNGs under `e2e/artifacts/ux30-plus-harness/`. Each scene asserts `[data-review-surface]` for `foundation`, `intelligence`, `activity`, or `navigation`.

---

## Reference alignment (Cesar review images)

| Reference | Harness mapping |
|-----------|-----------------|
| Linear expandable labeled rail | Navigation B — `expanded` / `pinned` scenes |
| Trace waterfall / span inspector | Activity A1 rail + story; A2 timeline for duration analysis |
| Activity stream side panel | Activity story panel + evidence chips (not a second product) |
| Knowledge graph field (Oiya-style) | Intelligence I1 entity/relationship field — real KG contract, not dept décor |

---

## Approval gate — SIGNED 2026-09-21

- [x] Shared grammar sufficient for Intelligence + Activity
- [x] I2 change stream contextual (field primary — not permanent 50/50 split)
- [x] A1 TRACE rail + optional A2 timeline toggle
- [x] Navigation B click/pin behavior (no disruptive hover expand)
- [x] Activity A1 pilot on `/activity` authorized

**Next gate:** Staging journey J7 PASS before production PASS claim. See `GRAVITRE_3.0_HARNESS_GATE_STATUS.md`.
