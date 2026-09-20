# Gravitre UX/UI 3.0 Plus — Harness Review Guide

**Date:** 2026-09-20  
**Status:** STOP FOR CESAR — harness prototypes ready for review  
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
| default | Field topology; change stream closed |
| selected | Node selection + focus |
| inspector | Inspector open |
| ai-context | Ask-about-this chip |
| loading | Skeleton |
| empty | Honest empty |
| error | Retry |
| mobile | 390-width layout |
| reduced | No spring animation |

### Activity (A1 + A2)
| Scene | Shows |
|-------|--------|
| default | List + TRACE rail + story |
| timeline | A2 temporal bar chart (real fixture durations) |
| fail | Failed outcome — failure scoped to Tool stage |
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
- Authenticated journey results (separate doc when staging session available)

---

## Approval gate

After review, confirm:

- [ ] Shared grammar sufficient for Intelligence + Activity
- [ ] I2 change stream interaction (not 50/50 split)
- [ ] A1 TRACE rail + optional A2 timeline
- [ ] Navigation B click/pin behavior
- [ ] Ready to implement Activity A1 pilot on `/activity` (single route scope)

**No production rollout until this checklist is signed.**
