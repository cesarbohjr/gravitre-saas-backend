# Gravitre UX/UI 3.0 Plus — Phase 7 Production Authorization

**Date:** 2026-09-21  
**Status:** **AUTHORIZED by Cesar** — broad production rollout beyond I1 Phase 1 / A1 pilots  
**Precondition met:** Harness APPROVED · Activity A1 J7 PASS · Intelligence I1 Phase 1 J6 PASS

---

## Cesar authorization (2026-09-21)

The following areas are **explicitly authorized for production implementation**. Each remains a **controlled slice** (commit → deploy → journey PASS) — authorization is not a single mega-merge.

| # | Area | Authorization |
|---|------|----------------|
| 1 | **`/intelligence/*` sub-routes** | Learning, predictive, performance, reports, memory, model-studio, models — align with I1/I2/I3 grammar where graph or evidence applies |
| 2 | **Navigation B (prod)** | Expandable labeled rail — click/pin; harness `nav-rail-prototype.tsx` reference |
| 3 | **I3 Matrix Lens default** | Matrix as default Intelligence overview mode (field/I1 available as alternate or secondary tab — exact UX per slice doc) |
| 4 | **I2 Phase 2 mobile polish** | Change stream → top segmented control or bottom sheet on narrow viewports; event → inspector deep link |
| 5 | **Connectors / Sources / Marketplace** | Visual + interaction 3.0 Plus slices on existing routes — **real API data only**; no invented prices, claims, or Enable toggles |

**Standing rules (unchanged):**

- No invented customer-facing product surfaces (`.cursor/rules/no-invented-customer-surfaces.mdc`)
- Evidence-linked PASS before calling any slice shipped (`docs/ENGINEERING_STANDARDS.md`)
- Work on `main`; one slice per delivery wave unless Cesar requests parallel agents

---

## Recommended execution order

Priority balances dependency, user visibility, and risk (same pattern as A1 → I1).

```
Wave 1 — Intelligence completion (overview + mobile) · SHIPPING 2026-09-21
  I2 Phase 2 mobile polish · mobile panel tabs + full-width stream
  I3 Matrix Lens as default on /intelligence overview · Field toggle retained
  ↓
Wave 2 — Intelligence sub-routes (batch or route-by-route)
  /intelligence/learning · /predictive · /performance · /reports · /memory · /models · /model-studio
  (redirect-only routes stay redirect-only)
  ↓
Wave 3 — Global shell · SHIPPED 2026-09-21
  Navigation B on production AppShell / sidebar (`nav-rail-b`, pin, keyboard ↑↓)
  ↓
Wave 4 — Integration surfaces · SHIPPED 2026-09-21
  Connectors hub + detail sections (`connectors-hub-b`, `connector-detail-b`)
  Sources table (`sources-hub-b`, `sources-table-view`)
  Marketplace scan list (`marketplace-catalog-b`, `marketplace-scan-list`)
```

Each wave ships with: slice plan doc · vitest where logic · Playwright journey or surface-matrix extension · append to `GRAVITRE_3.0_JOURNEY_RESULTS.md`.

---

## Per-slice gate template

| Slice | Primary routes | Harness reference | Journey / proof |
|-------|----------------|-------------------|-----------------|
| I2 mobile | `/intelligence` | `intelligence-field-prototype` mobile scene | J6 extension @ 390px |
| I3 default | `/intelligence` | `?s=intelligence&scene=i3` | J6 matrix cell select + inspector |
| Intel sub-routes | `/intelligence/*` | Per-route harness scenes | J6 or sub-route matrix row |
| Nav B | global | `nav-rail-prototype.tsx` | J1 + J11 + nav pin matrix |
| Connectors | `/connectors`, `/connectors/[id]` | Walkthrough §Connectors | J5 |
| Sources | `/sources` | Walkthrough §Sources | Surface matrix |
| Marketplace | `/marketplace/*` | Walkthrough §Marketplace | J10 |

---

## Out of scope (still not authorized by this sign-off)

- Settings / billing / auth redesign
- Lite seat program surfaces
- Workflow builder canvas signature slice
- Wholesale Lucide → Nucleo purge without touching a surface
- Backend API invention for UI filler

---

## Related documents

- `GRAVITRE_3.0_HARNESS_GATE_STATUS.md`
- `GRAVITRE_INTELLIGENCE_I1_PRODUCTION_PLAN.md`
- `GRAVITRE_3.0_PLUS_CESAR_APPROVAL_PACKAGE.md`
- `GRAVITRE_3.0_JOURNEY_TEST_PLAN.md`
